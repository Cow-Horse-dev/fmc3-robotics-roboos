---
description: Generate a skill execution plan for a given step (1–9) of the Hikvision camera airtightness inspection workflow
argument-hint: <step-number> <robot-folder>
allowed-tools: Read, Glob, Grep
---

Generate a detailed skill execution plan for the specified step of the Hikvision camera airtightness inspection workflow.

## Full Workflow Reference

| Step | Description | Canonical Skill Sequence |
|------|-------------|--------------------------|
| 1 | Pick up camera from transfer box | P1 → M4 → M1 → G1 → G2 → G3 → G4 |
| 2 | Remove lens cap + visual inspection | C1 → P1 → M1 → G2 → O3 → O1 → M3 → P2 |
| 3 | Scan QR code | M2 → M3 → M1 → O4 → P3 → I1 |
| 4 | Place camera into fixture (lens up) | M3 → P1 → M4 → M1 → O4 → O1 |
| 5 | Press start buttons, wait for test | P1 → M2 → O2 → I1 |
| 6 | Remove camera + re-inspect lens | M1 → G2 → G4 → M3 → P2 |
| 7 | Replace lens cap | P1 → M1 → G2 → O3 → O1 |
| 8 | Stack camera into transfer box | P1 → M4 → M3 → O4 → O1 |
| 9 | Read airtightness result on screen | P1 → P4 → P2 |

## Atomic Skill Definitions

- P1: Visual localization | P2: Visual inspection | P3: QR recognition | P4: Read screen result
- M1: Point-to-point move | M2: Bimanual sync (<100ms) | M3: Orientation control | M4: Path planning
- G1: Open hand | G2: Precision pinch (±0.3mm) | G3: Force grasp (0.5–2N) | G4: Lift
- O1: Place | O2: Dual button press | O3: Cap insert/pull | O4: Fine alignment (±0.3mm)
- C1: Hand-to-hand transfer | I1: Wait for signal

## Task

The user has provided: `$ARGUMENTS`
Parse the step number and optional robot folder (default: demo_robot_local).

1. Look up the step in the workflow table above.
2. Read the skill.py in the specified robot folder and identify which skills in the canonical sequence are already implemented and which are missing.
3. Produce a structured plan with:
   - **Step goal**: what the robot needs to achieve
   - **Skill sequence**: the ordered list of atomic skills with a one-line description of each call
   - **Already implemented**: skills found in skill.py (with function name)
   - **Missing skills**: skills not yet in skill.py that need to be added (suggest running `/new-skill <id> <folder>` for each)
   - **Key constraints**: relevant precision/force/timing requirements for this step
   - **Suggested MCP tool call order**: concrete pseudocode showing how the skills chain together with example argument values
