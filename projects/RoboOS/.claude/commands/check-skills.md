---
description: Audit all implemented MCP tools in skill.py against the Hikvision camera inspection atomic skill library and report coverage
argument-hint: <robot-folder>
allowed-tools: Read, Glob, Grep
---

Audit the implemented robot skills in skill.py against the full atomic skill library for the Hikvision camera airtightness inspection task.

## Full Atomic Skill Library (20 skills, 7 categories)

| ID | Category | Name | Key Constraint |
|----|----------|------|---------------|
| P1 | Perception | Visual localization | Real-time visual servoing |
| P2 | Perception | Visual inspection (lens damage) | — |
| P3 | Perception | QR code recognition | — |
| P4 | Perception | Read screen result | — |
| M1 | Motion | Point-to-point move | — |
| M2 | Motion | Bimanual synchronized motion | Time offset < 100ms |
| M3 | Motion | Orientation control | — |
| M4 | Motion | Collision-aware path planning | Accounts for fixture/boxes/station |
| G1 | Grasping | Open hand | — |
| G2 | Grasping | Precision pinch (2-finger) | ±0.3mm repeatability |
| G3 | Grasping | Force-controlled grasp | 0.5–2N |
| G4 | Grasping | Lift object | — |
| O1 | Operation | Place object | — |
| O2 | Operation | Simultaneous dual button press | Both index fingers in sync |
| O3 | Operation | Lens cap insert/pull | ±0.3mm alignment |
| O4 | Operation | Fine alignment | ±0.3mm |
| C1 | Coordination | Hand-to-hand transfer | — |
| I1 | Interaction | Wait for signal/event | — |

## Workflow Step Coverage

| Step | Required Skills |
|------|----------------|
| 1 — Pick up camera | P1, M4, M1, G1, G2, G3, G4 |
| 2 — Remove lens cap + inspect | C1, P1, M1, G2, O3, O1, M3, P2 |
| 3 — Scan QR code | M2, M3, M1, O4, P3, I1 |
| 4 — Place into fixture | M3, P1, M4, M1, O4, O1 |
| 5 — Press buttons + wait | P1, M2, O2, I1 |
| 6 — Remove + re-inspect | M1, G2, G4, M3, P2 |
| 7 — Replace lens cap | P1, M1, G2, O3, O1 |
| 8 — Stack into transfer box | P1, M4, M3, O4, O1 |
| 9 — Check screen result | P1, P4, P2 |

## Task

The user has provided: `$ARGUMENTS`
Parse the robot folder (default: demo_robot_local).

1. Read skill.py in the specified robot folder.
2. Extract all `@mcp.tool()` decorated function names and their docstrings.
3. Map each implemented function to the closest atomic skill ID(s) from the library above based on name and docstring.
4. Produce a coverage report with three sections:

### Section 1: Implemented Skills
List each found tool with its mapped skill ID(s) and a one-line summary.

### Section 2: Coverage Matrix
For each of the 20 atomic skills, show: ✅ implemented | ❌ missing

### Section 3: Workflow Readiness
For each of the 9 workflow steps, show:
- ✅ Ready (all required skills implemented)
- ⚠️ Partial (some skills missing — list which)
- ❌ Blocked (no skills implemented yet)

### Section 4: Recommendations
List missing skills in priority order (by how many workflow steps they unblock), and suggest the `/new-skill` command to add each one.
