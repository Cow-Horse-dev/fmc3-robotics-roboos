---
description: Verify the slaver state machine implementation for the bottle demo (ready/running/finished/failed states, 3x retry, task termination)
allowed-tools: Read, Glob, Grep
---

Verify that the RoboOS slaver implements the correct state machine for the bottle demo atomic skill scheduling.

## Required State Machine

```
                 ┌─────────────────────────────┐
                 │                               │
                 v                               │
  [ready] ──→ [running] ──→ [finished]          │
                 │                               │
                 v                               │
              [failed] ──→ initialization() ──→ [ready]  (retry, max 3x)
                 │
                 v (after 3 consecutive failures)
              [stop] ──→ initialization() ──→ task terminated
```

## Requirements from Spec

### S-1: API Mapping
- S-1.1: Map "put in" subtask → `place_in()` skill
- S-1.1: Map "take out" subtask → `take_out()` skill

### S-2: Skill Scheduling
- S-2.1 (ready): Before `place_in()` — check arm at init position AND cup outside box
- S-2.1 (ready): Before `take_out()` — check arm at init position AND cup inside box
- S-2.2 (running): When ready, start skill execution, set state to running
- S-2.3 (finished): Check head+wrist camera at 1fps, verify skill completion + arm at init
- S-2.4 (failed): Check head+wrist camera at 1fps, detect cup tipped or detached
- S-2.5: Report state to Master every 1 second
- S-2.6: On "stop" signal, set state to stop

### M-3: Task Termination
- M-3.1: 3 consecutive failed attempts → task terminates, arm returns to init
- UC-10: After failure, arm returns to init position, state back to ready, then retry

### Sequencing
- UC-7/UC-8: After skill completes, arm must return to init before next skill
- UC-9: New commands only accepted after current skill finishes
- M-2.1/M-2.2: Multi-step tasks execute sequentially, step N+1 only after step N finishes

## Task

Analyze the following files in `/home/haoanw/workspace/RoboOS/slaver/`:

1. **`run.py`** — Check `_execute_task()` for:
   - State machine integration (vs pure ReAct loop)
   - Retry logic (max 3 attempts)
   - Task termination on 3 consecutive failures
   - Result reporting with skill state

2. **`agents/slaver_agent.py`** — Check for:
   - Skill state tracking
   - Failure detection in observations
   - Sequential execution support

3. **`agents/skill_state_machine.py`** (if exists) — Check for:
   - State enum: ready, running, finished, failed, stop
   - `parse_skill_sequence()` function
   - Retry counter and max retry logic
   - `initialization()` call after failure (return to init before retry)
   - Task termination after 3 failures

4. **`tools/memory.py`** — Check SceneMemory for:
   - Cup position tracking (in box / on desk)
   - Robot arm position tracking (at init / elsewhere)

Produce a compliance report:

### State Machine States
For each state (ready/running/finished/failed/stop), report: implemented | missing | partial

### Retry Logic
- Max retries configured (should be 3)
- initialization() called between retries
- Task termination after max failures

### Status Reporting
- 1-second heartbeat to Master
- Skill state included in reports

### Sequencing
- Multi-step task support (place_in → init → take_out)
- Blocking until current skill finishes

### Gaps & Recommendations
List what's missing and how to implement it.
