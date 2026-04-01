---
description: Audit implemented MCP tools in RoboSkill skill.py against the bottle demo atomic skill library and report coverage
argument-hint: <robot-folder-path>
allowed-tools: Read, Glob, Grep
---

Audit the implemented robot skills against the full atomic skill library for the "grab cup" bottle demo task.

## Atomic Skill Library (3 skills)

| ID | Name | Description | Pi0 Model | Key Constraint |
|----|------|-------------|-----------|----------------|
| Y-1 | `place_in()` | Pick up cup from desk, place into box | Yes (dedicated Pi0) | Precondition: arm at init position, cup outside box and upright |
| Y-2 | `take_out()` | Take cup out of box, place on desk | Yes (dedicated Pi0) | Precondition: arm at init position, cup inside box |
| Y-3 | `initialization()` | Move arm back to initial position via shortest path | No (Aurora SDK only) | Must complete before next skill can start |

## Skill State Machine

Each atomic skill must support these states:
- `ready`: preconditions met, skill can start
- `running`: skill is executing (Pi0 inference active)
- `finished`: skill completed successfully (verified by vision check)
- `failed`: skill failed (cup tipped over or detached from hand)
- `stop`: external termination signal received

## Use Cases to Support

| UC | User Command | Skill Sequence |
|----|-------------|----------------|
| UC-2 | "put cup in box" | `place_in()` |
| UC-3 | "take cup out of box" | `take_out()` |
| UC-4 | "put cup in box, then take it out" | `place_in()` → `initialization()` → `take_out()` |
| UC-5 | "take cup out, then put it back" | `take_out()` → `initialization()` → `place_in()` |
| Challenge | 3+ step long tasks | `place_in()` → `initialization()` → `take_out()` → `initialization()` → `place_in()` → ... |

## Finish/Failure Checks (Slaver responsibility)

- **CheckFinish**: Head camera + wrist camera at 1fps, verify cup placement AND arm back at init position
- **CheckFailed**: Cup tipped over OR cup detached from hand while hand still moving

## Task

The user has provided: `$ARGUMENTS`
Parse the robot folder path (default: `/home/haoanw/workspace/RoboSkill/fmc3-robotics/fourier/gr2`).

1. Read `skill.py` in the specified robot folder.
2. Extract all `@mcp.tool()` decorated function names, their arguments, and docstrings.
3. Map each implemented function to the closest atomic skill ID (Y-1, Y-2, Y-3) from the library above.
4. Produce a coverage report:

### Section 1: Implemented Skills
List each found tool with its mapped skill ID and a one-line summary.

### Section 2: Coverage Matrix
For each of the 3 atomic skills: implemented | missing

### Section 3: Use Case Readiness
For each of the 5 use cases (UC-2 through UC-5, plus Challenge), show:
- Ready (all required skills implemented)
- Partial (some skills missing)
- Blocked (none implemented)

### Section 4: State Machine Compliance
Check if skill functions:
- Return `tuple[str, dict]` with success/failure indication
- Use `skill_success()` and `skill_failure()` helpers
- Include "FAILED" in failure return strings (for state machine detection)
- Have precondition checks documented

### Section 5: Recommendations
List missing skills and suggest what needs to be implemented, including:
- Function signature
- Pi0 model integration requirements
- Aurora SDK control interface needs
- Precondition checks needed
