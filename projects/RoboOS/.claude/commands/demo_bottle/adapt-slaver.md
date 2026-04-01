---
description: Adapt the RoboOS slaver for the bottle demo — add state machine, API mapping, skill scheduling with retry/termination
allowed-tools: Read, Edit, Write, Glob, Grep
---

Adapt the RoboOS slaver module for the "grab cup" bottle demo. This is the most critical adaptation — it adds the skill state machine, API mapping, and failure handling.

## Target Architecture

```
Master ──(Redis)──→ Slaver
                      │
                      ├── API Mapping: subtask text → skill name
                      ├── State Machine: ready → running → finished/failed
                      ├── Retry Logic: failed → init → ready (max 3x)
                      └── MCP Client → RoboSkill skill server (place_in, take_out, initialization)
```

## Requirements

### S-1: API Mapping (`_map_subtask_to_skill`)
- "放入" / "place in" / "put in" → `place_in`
- "拿出" / "take out" / "remove" → `take_out`
- "初始化" / "initialization" / "init" → `initialization`

### S-2: Skill State Machine

Create `slaver/agents/skill_state_machine.py`:

```python
class SkillState(Enum):
    READY = "ready"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    STOP = "stop"

class SkillSequenceExecutor:
    MAX_RETRIES = 3

    async def execute_sequence(self, skills: list[str], tool_executor, collaborator):
        for skill_name in skills:
            success = await self._execute_with_retry(skill_name, tool_executor)
            if not success:
                return {"status": "terminated", "failed_skill": skill_name}
        return {"status": "completed"}

    async def _execute_with_retry(self, skill_name, tool_executor):
        for attempt in range(self.MAX_RETRIES):
            self.state = SkillState.RUNNING
            result = await tool_executor(skill_name, {})

            if self._is_success(result):
                self.state = SkillState.FINISHED
                # Call initialization() to return arm to init position
                await tool_executor("initialization", {})
                return True
            else:
                self.state = SkillState.FAILED
                # Return to init position before retry
                await tool_executor("initialization", {})
                self.state = SkillState.READY

        # 3 consecutive failures → terminate
        self.state = SkillState.STOP
        return False
```

### Integration into `slaver/run.py`

Modify `_execute_task()`:
1. Parse subtask text to extract skill name(s)
2. If recognized bottle demo skill → use SkillSequenceExecutor (deterministic)
3. If not recognized → fall back to ReAct loop (ToolCallingAgent)
4. Report state to master every 1 second during execution
5. Include skill state in result payload

### Result Payload Enhancement

```python
payload = {
    "robot_name": robot_name,
    "subtask_handle": task,
    "subtask_result": result,
    "skill_state": state.value,  # "finished", "failed", "stop"
    "tools": tool_calls,
    "task_id": task_id,
    "failure_info": {              # Only when failed/stopped
        "failed_skill": skill_name,
        "attempts": attempt_count,
        "last_error": error_message,
    }
}
```

### Scene Memory Updates

Update `slaver/tools/memory.py` action type prompt to handle bottle demo skills:
- `place_in()` → remove cup from desk, add cup to box
- `take_out()` → remove cup from box, add cup to desk
- `initialization()` → position change only (arm to init), no object movement

## Task

1. Read all current slaver files to understand existing structure.
2. Create `slaver/agents/skill_state_machine.py` with the state machine.
3. Modify `slaver/run.py` to integrate the state machine.
4. Update `slaver/tools/memory.py` if needed for bottle demo scene effects.
5. Ensure backward compatibility — ReAct loop still works for non-bottle-demo tasks.
6. Report all changes made.
