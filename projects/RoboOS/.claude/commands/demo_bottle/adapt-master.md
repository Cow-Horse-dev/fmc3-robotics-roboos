---
description: Adapt the RoboOS master (planner prompt, scene profile, agent logic) for the bottle demo scenario
allowed-tools: Read, Edit, Glob, Grep
---

Adapt the RoboOS master module for the "grab cup" bottle demo. This involves modifying the planning prompt, scene profile, and agent dispatch logic.

## Target Scenario

- **Robot**: Fourier GR2 dual-arm humanoid (`fourier_gr2`)
- **Scene**: Desk with blue Luckin cup + white paper box
- **Skills**: `place_in()`, `take_out()`, `initialization()`
- **Commands**: "put cup in box", "take cup out", combined sequences

## Files to Modify

### 1. `master/agents/prompts.py` — MASTER_PLANNING_PLANNING

Replace the Hikvision camera inspection context with bottle demo context:

```
## Robot Platform
- Robot: Fourier GR2 (dual-arm humanoid, 5-finger dexterous hands)
- Task domain: Cup manipulation demo (Luckin coffee cup + white box)

## Atomic Skills Available
- place_in(): Pick up cup from desk, place into box (Pi0 VLA model)
- take_out(): Take cup out of box, place on desk (Pi0 VLA model)
- initialization(): Return robot arm to initial position (Aurora SDK)

## Command Mapping
- "put cup in box" → place_in
- "take cup out of box" → take_out
- "put in then take out" → place_in, initialization, take_out
- "take out then put in" → take_out, initialization, place_in

## Key Constraints
- Each skill must start with arm at initial position
- initialization() must be called between consecutive skills
- Cup must be upright for place_in; cup must be in box for take_out
- 3 consecutive failures on a single skill → task terminates
```

### 2. `master/scene/profile.yaml`

Replace camera inspection workspace:

```yaml
scene:
  - name: desk
    type: surface
    contains:
      - cup

  - name: box
    type: container
    contains: []
```

### 3. `master/agents/agent.py` — Task Understanding

The master should:
- Parse user commands (Chinese/English) into skill sequences
- Validate preconditions (cup location matches command requirements)
- Dispatch subtasks sequentially (wait for step N to finish before step N+1)
- Handle task termination signals from slaver (3x failure)

Key considerations:
- M-0.1: On startup, send initialization command to slaver
- M-0.2: After init, wait for user commands (state = "waiting")
- M-1.1: Understand 4 command variants (Chinese text with flexible wording)
- M-1.2: Reject invalid commands
- M-1.3: Check preconditions before executing
- M-2.1/M-2.2: Multi-step tasks decompose and execute sequentially
- M-2.4: Report "running" status to UI at 1Hz
- M-3.1: Terminate on 3 consecutive failures from slaver
- M-3.2: Support manual termination
- M-3.3: Report "stop" to UI

## Task

1. Read the current state of all files listed above.
2. Apply the modifications described, preserving existing code structure.
3. Ensure the prompt template still accepts `{robot_name_list}`, `{robot_tools_info}`, `{task}`, `{scene_info}` placeholders.
4. Update scene profile to reflect the bottle demo workspace.
5. Report what was changed and verify the planning flow still works end-to-end.
