# Repository Guidelines

## Project Structure & Module Organization
This repository is a Python robotics monorepo centered on the workflow: data collection -> dataset conversion -> model training/inference -> RoboOS execution.

- `projects/RoboOS/`: orchestration stack (`master/`, `slaver/`, `deploy/`, `test/`, `assets/`).
- `projects/RoboBrain2.0/`: vision-language model service (`startup.sh`, `inference.py`, `assets/`).
- `projects/RoboSkill/`: MCP skill servers by vendor/model (for example `fmc3-robotics/fourier/gr2/`).
- `projects/fourier/Robot/`: GR-2 SDK wrapper (`gr2_robot.py`, `example.py`).
- `projects/scripts/convert_tools/`: Dora-Record -> LeRobot conversion scripts.
- `projects/lerobot/demo_scripts/`: training/eval/teleop shell examples.

## Build, Test, and Development Commands
Run from repository root unless noted.

- `pip install -r projects/RoboOS/requirements.txt`: install RoboOS dependencies.
- `pip install -r projects/RoboBrain2.0/requirements.txt`: install RoboBrain runtime dependencies.
- `bash projects/RoboBrain2.0/startup.sh`: start model service (default port `4567`).
- `python projects/RoboOS/master/run.py`
- `python projects/RoboOS/slaver/run.py`
- `python projects/RoboOS/deploy/run.py`: run Master/Slaver/Web UI (`:5000`, Redis-backed, UI `:8888`).
- `bash start_roboos.sh`: launch the common tmux multi-service workflow.
- `python projects/scripts/convert_tools/convert_dora_to_lerobot.py ...`: convert demonstration data.

## Coding Style & Naming Conventions
- Use Python 3.10+ and 4-space indentation.
- Follow standard naming: `snake_case` for functions/files, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- Keep modules focused and explicit; place project-specific scripts in their existing subproject folders.
- `ruff` is included in RoboOS deps; run `ruff check projects/RoboOS` before PRs when touching that stack.

## Testing Guidelines
- Current tests are mostly integration scripts. Use:
- `python projects/RoboOS/test/test.py`
- `python projects/RoboSkill/fmc3-robotics/fourier/gr2/test_connection.py`
- `python projects/RoboSkill/fmc3-robotics/fourier/gr2/test_pi0_inference.py health`
- Add new tests as `test_*.py` near the changed module. For hardware-dependent changes, include a safe mock/dry-run path where possible.

## Commit & Pull Request Guidelines
- History uses short, prefix-style subjects (`docs: ...`, `chore: ...`, or `name: ...`). Keep this pattern and write imperative, scoped summaries.
- Keep commits single-purpose and include config changes in the same commit when required.
- PRs should include: affected subprojects, environment used, commands run, and key logs/screenshots for deploy UI or robot behavior changes.

## Security & Configuration Tips
- Do not commit real credentials/endpoints in `projects/RoboOS/master/config.yaml` or `projects/RoboOS/slaver/config.yaml`; prefer local overrides/env vars.
- Avoid committing generated datasets, model weights, logs, or temp files (already broadly covered by `.gitignore`).
