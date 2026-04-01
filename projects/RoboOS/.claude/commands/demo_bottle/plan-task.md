---
description: Generate a skill execution plan for a given bottle demo user command, showing the full skill sequence with state transitions
argument-hint: <user-command>
allowed-tools: Read, Glob, Grep
---

Generate a detailed execution plan for the given user command in the bottle demo scenario.

## Scene Definition

- **Desk**: Work surface with a blue Luckin coffee cup
- **Box**: White paper box at a fixed position on the desk
- **Robot**: Fourier GR2 dual-arm humanoid with 5-finger dexterous hands
- **Cameras**: Head camera + wrist camera for vision checks

## Atomic Skills

| Skill | Description | Pi0 Model | Preconditions |
|-------|-------------|-----------|---------------|
| `place_in()` | Pick up cup, place into box | Yes | Arm at init, cup on desk upright |
| `take_out()` | Take cup from box, place on desk | Yes | Arm at init, cup in box |
| `initialization()` | Return arm to initial position | No | None |

## Command → Skill Mapping

| Command Pattern | Skill Sequence |
|----------------|----------------|
| "put cup in box" | `place_in()` |
| "take cup out of box" | `take_out()` |
| "put in then take out" | `place_in()` → `initialization()` → `take_out()` |
| "take out then put in" | `take_out()` → `initialization()` → `place_in()` |
| N-step chain | alternating skills with `initialization()` between each |

## State Machine Per Skill

```
ready → running → finished → (next skill or done)
              └→ failed → initialization() → ready (retry, max 3x)
                              └→ stop (after 3 failures)
```

## Task

The user has provided: `$ARGUMENTS`

1. Parse the user command (in Chinese or English).
2. Determine which use case it matches (UC-2 through UC-5, or challenge multi-step).
3. Check the current scene state if available (cup in box or on desk).
4. Generate the execution plan:

### Command Analysis
- Original command: `$ARGUMENTS`
- Matched use case: UC-X
- Precondition check: what must be true before execution

### Skill Sequence
Numbered list of skills to execute, with:
- Skill name and arguments
- Expected state transitions (ready → running → finished)
- What `initialization()` calls are needed between steps
- Scene state after each skill completes

### Failure Handling
- What failures can occur at each step (cup tipped, cup detached)
- Retry behavior: initialization() → retry same skill
- Termination condition: 3 consecutive failures on same skill

### Master-Slaver Communication
- What messages Master sends to Slaver for each step
- What status reports Slaver sends back
- When Master can dispatch the next subtask

### Expected Timeline
- Approximate sequence of events with state transitions
- When cameras check for finish/failure conditions
