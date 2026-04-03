---
description: Scaffold a new atomic skill as an MCP tool in skill.py for the Hikvision camera inspection task
argument-hint: <skill-id> <robot-folder>
allowed-tools: Read, Edit, Glob, Grep
---

Scaffold a new atomic skill implementation based on the Hikvision camera airtightness inspection atomic skill library.

## Atomic Skill Library Reference

### P — Perception
- P1: Visual localization (locate objects/slots/buttons via camera)
- P2: Visual inspection (detect lens damage)
- P3: QR code recognition
- P4: Read result from screen

### M — Motion
- M1: Point-to-point move to target position
- M2: Bimanual synchronized motion (time offset < 100ms)
- M3: Orientation control (rotate object to target angle)
- M4: Collision-aware path planning

### G — Grasping
- G1: Open hand (spread 5 fingers)
- G2: Precision pinch grasp (2-finger, ±0.3mm)
- G3: Force-controlled grasp (0.5–2N)
- G4: Lift object

### O — Operation
- O1: Place object at target location
- O2: Button press (simultaneous dual-finger)
- O3: Cap insert/pull (lens cap)
- O4: Fine alignment (±0.3mm)

### C — Coordination
- C1: Hand-to-hand object transfer

### I — Interaction
- I1: Wait for external signal/event completion

## Task

The user has provided: `$ARGUMENTS`
Parse the skill ID (e.g. P1, M2, G3) and the robot folder (e.g. demo_robot_local).

1. Read the existing `skill.py` in the specified robot folder to understand the current structure and avoid duplication.
2. Based on the skill ID, implement the corresponding `@mcp.tool()` function following the conventions already used in that file.
3. The function must:
   - Have a clear docstring explaining what it does and when NOT to call it (follow the existing pattern)
   - Accept appropriate typed arguments for the skill
   - Return a result string and a state dict describing the robot state change
   - Include the design constraints relevant to that skill category:
     - G/O skills: mention force range (0.5–2N) or alignment precision (±0.3mm) in docstring
     - M2 skills: note bimanual sync requirement (<100ms offset)
     - P skills: note visual servoing dependency
4. Insert the new tool function into skill.py before the `if __name__ == "__main__":` block.
5. Report what was added and which step(s) of the 9-step workflow it supports.
