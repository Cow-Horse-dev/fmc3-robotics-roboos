---
description: Scaffold a new atomic skill for the bottle demo as an MCP tool in RoboSkill's skill.py
argument-hint: <skill-name> <robot-folder-path>
allowed-tools: Read, Edit, Glob, Grep
---

Scaffold a new atomic skill implementation for the bottle demo scenario.

## Atomic Skill Library Reference

### Y-1: `place_in()`
- **Purpose**: Pick up cup from desk, place into white box
- **Model**: Dedicated Pi0 VLA model
- **Input**: Head camera, wrist camera, third-person camera, robot state, "place_in" text instruction
- **Output**: 50-step action chunk (29-dim action vector) at 15Hz
- **Preconditions**: Arm at init position, cup on desk and upright
- **Success**: Cup in box, arm returned to init
- **Failure**: Cup tipped over OR cup detached from hand

### Y-2: `take_out()`
- **Purpose**: Take cup out of box, place on desk
- **Model**: Dedicated Pi0 VLA model
- **Input**: Same as place_in
- **Output**: Same as place_in
- **Preconditions**: Arm at init position, cup in box
- **Success**: Cup on desk, arm returned to init
- **Failure**: Cup tipped over OR cup detached from hand

### Y-3: `initialization()`
- **Purpose**: Return robot arm to initial position via shortest path
- **Model**: None (Aurora SDK direct control)
- **Input**: Current joint angles
- **Output**: Joint trajectory to init position
- **Preconditions**: None
- **Success**: Arm at init position
- **Failure**: Arm unreachable or collision

## MCP Tool Convention

```python
@mcp.tool()
async def skill_name(args...) -> tuple[str, dict]:
    """Docstring explaining what the skill does.
    Do not call when [guard condition].
    Args:
        arg: Type, description.
    """
    # Precondition check
    # Execute skill (Pi0 inference or Aurora SDK)
    # Return result
    return skill_success("skill_name", "message", {"state": "data"})
    # or
    return skill_failure("skill_name", "reason for failure")
```

## Task

The user has provided: `$ARGUMENTS`
Parse the skill name (place_in, take_out, or initialization) and robot folder path (default: `/home/haoanw/workspace/RoboSkill/fmc3-robotics/fourier/gr2`).

1. Read the existing `skill.py` to understand current structure and avoid duplication.
2. Based on the skill name, implement the `@mcp.tool()` function following existing conventions.
3. The function must:
   - Have a clear docstring with "Do not call when..." guard
   - Accept appropriate typed arguments
   - Return `tuple[str, dict]` using `skill_success()` / `skill_failure()` helpers
   - Include Pi0 model integration placeholder (for place_in/take_out) or Aurora SDK placeholder (for initialization)
   - Document the preconditions in the docstring
4. Insert the new tool function into skill.py in the appropriate section.
5. Report what was added and which use cases (UC-2 through UC-5) it supports.
