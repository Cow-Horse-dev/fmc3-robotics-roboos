import json

import psutil
from agents.agent import GlobalAgent
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO

app = Flask(__name__, static_folder="assets")
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")


def send_text_to_frontend(text):
    socketio.emit("text_update", {"data": text}, namespace="/")


master_agent = GlobalAgent(config_path="config.yaml")


# ─── M-0.1 / M-0.2: Startup Initialization ──────────────────────────────────

def _startup_init():
    """Send initialization command to slaver on startup, then set state to waiting."""
    master_agent.task_state = "waiting"
    print("[Master] Initialization complete. Waiting for user commands.")


_startup_init()


# ─── System Endpoints ────────────────────────────────────────────────────────

@app.route("/system_status", methods=["GET"])
def system_status():
    """Get the system status."""
    cpu_load = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    memory_usage = memory.percent

    return jsonify(
        {
            "cpu_load": round(cpu_load, 1),
            "memory_usage": round(memory_usage, 1),
            "task_state": master_agent.task_state,
        }
    )


@app.route("/robot_status", methods=["GET"])
def robot_status():
    """Get the status of all robots."""
    try:
        registered_robots = master_agent.collaborator.read_all_agents_info()
        registered_robots_status = []
        for robot_name, robot_info in registered_robots.items():
            registered_robots_status.append(
                {
                    "robot_name": robot_name,
                    "robot_state": json.loads(robot_info).get("robot_state"),
                }
            )
        return jsonify(registered_robots_status), 200
    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ─── Task Endpoints ──────────────────────────────────────────────────────────

@app.route("/publish_task", methods=["POST", "GET"])
def publish_task():
    """Publish a task to the robot.

    Request JSON format:
    {
        "task": "task_content"  # The task to be published
        "refresh": true         # Whether to refresh the cached robot memory
    }
    """
    if request.method == "GET":
        return jsonify({"status": "success", "task_state": master_agent.task_state}), 200
    try:
        data = request.get_json()
        if not data or "task" not in data:
            return jsonify({"error": "Invalid request - 'task' field required"}), 400

        # M-1.1: Only accept commands when state is not "init" or "stop"
        if master_agent.task_state in ("init", "stop"):
            return (
                jsonify(
                    {
                        "status": "rejected",
                        "message": f"Cannot accept task — system state is '{master_agent.task_state}'",
                        "task_state": master_agent.task_state,
                    }
                ),
                409,
            )

        # UC-9: Only accept commands when not currently running
        if master_agent.task_state == "running":
            return (
                jsonify(
                    {
                        "status": "rejected",
                        "message": "Task already running — wait for completion",
                        "task_state": master_agent.task_state,
                    }
                ),
                409,
            )

        if not isinstance(data["task"], list):
            data["task"] = [data["task"]]
        if "refresh" not in data:
            data["refresh"] = False

        task_id = data.get("task_id")
        for task in data["task"]:
            if not isinstance(task, str):
                return jsonify({"error": "Invalid task format - must be a string"}), 400
            subtask_list = master_agent.publish_global_task(
                task, data["refresh"], task_id
            )

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Task published successfully",
                    "task_state": master_agent.task_state,
                    "data": subtask_list,
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": "Internal server error", "details": str(e)}), 500


# ─── M-3.2: Manual Termination ──────────────────────────────────────────────

@app.route("/stop_task", methods=["POST"])
def stop_task():
    """Manually terminate the current task."""
    master_agent.task_state = "stop"
    return jsonify({"status": "success", "message": "Task terminated", "task_state": "stop"}), 200


# ─── M-0: Reset / Re-initialize ─────────────────────────────────────────────

@app.route("/reset", methods=["POST"])
def reset():
    """Reset the system state from 'stop' back to 'waiting'."""
    master_agent.task_state = "waiting"
    return jsonify({"status": "success", "message": "System reset to waiting", "task_state": "waiting"}), 200


@app.route("/task_state", methods=["GET"])
def task_state():
    """Get the current task state and execution event log.

    Response format:
    {
        "task_state": "running",
        "events": [
            {"time": "14:30:01", "type": "task_start",  "message": "收到指令: 放入"},
            {"time": "14:30:01", "type": "plan_done",    "message": "指令 '放入' → 1 个子任务: place_in"},
            {"time": "14:30:01", "type": "state",        "message": "waiting → running"},
            {"time": "14:30:02", "type": "dispatch",     "message": "子任务 1/1: place_in → gr2_robot"},
            {"time": "14:30:07", "type": "skill_done",   "message": "gr2_robot: place_in → Cup placed"},
            {"time": "14:30:07", "type": "task_done",    "message": "任务 '放入' 调度结束"},
        ]
    }
    """
    return jsonify(master_agent.get_task_progress()), 200


if __name__ == "__main__":
    # Run the Flask app
    app.run(host="0.0.0.0", port=5000)
