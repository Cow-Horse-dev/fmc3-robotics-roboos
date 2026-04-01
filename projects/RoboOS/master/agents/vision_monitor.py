"""
master/agents/vision_monitor.py
───────────────────────────────
VisionMonitor：基于 OpenAI 视觉能力的场景状态判断

功能：
  1. 通过 USB 摄像头 (OpenCV) 抓取 top-view 画面
  2. 将画面发送给 OpenAI (GPT-4o 等)，判断两种场景状态：
     - 瓶子在不在盒子里
     - 瓶子在黄色纸上还是绿色纸上
"""

import base64
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import cv2
import numpy as np
from openai import OpenAI

logger = logging.getLogger("VisionMonitor")


# ─── Data Structures ────────────────────────────────────────────────────────

@dataclass
class SceneState:
    """Scene state judgment result from OpenAI vision."""
    bottle_in_box: Optional[bool] = None        # True = in box, False = not in box, None = unknown
    bottle_on_paper: Optional[str] = None        # "yellow" | "green" | None (unknown)
    reason: str = ""
    confidence: float = 0.0


@dataclass
class MonitorState:
    """Thread-safe shared state between monitor loop and dispatch."""
    lock: threading.Lock = field(default_factory=threading.Lock)
    latest_scene: Optional[SceneState] = None
    should_stop: bool = False

    def update(self, scene: SceneState) -> None:
        with self.lock:
            self.latest_scene = scene

    def stop(self) -> None:
        with self.lock:
            self.should_stop = True

    @property
    def is_stopped(self) -> bool:
        with self.lock:
            return self.should_stop

    def reset(self) -> None:
        with self.lock:
            self.latest_scene = None
            self.should_stop = False


# ─── Vision Monitor ─────────────────────────────────────────────────────────

class VisionMonitor:
    """Top-view camera monitor powered by OpenAI vision."""

    def __init__(self, config: Dict) -> None:
        """
        Args:
            config: vision_monitor section from config.yaml
                - camera_id: int or str (USB device id, default 0)
                - api_key: str (OpenAI API key)
                - base_url: str (optional, for compatible endpoints)
                - model: str (default "gpt-4o")
                - interval_sec: float (capture interval, default 5.0)
                - confidence_threshold: float (default 0.7)
        """
        self._camera_id = config.get("camera_id", 0)
        self._interval = config.get("interval_sec", 5.0)
        self._confidence_threshold = config.get("confidence_threshold", 0.7)
        self._model_name = config.get("model", "gpt-4o")

        client_kwargs = {"api_key": config["api_key"]}
        if config.get("base_url"):
            client_kwargs["base_url"] = config["base_url"]
        self._client = OpenAI(**client_kwargs)

        self._cap: Optional[cv2.VideoCapture] = None
        self._cap_lock = threading.Lock()

        # Event log callback (set by agent)
        self._on_event: Optional[Callable[[str, str], None]] = None

    # ── Camera ──

    def open_camera(self) -> bool:
        """Open the USB camera. Returns True on success."""
        with self._cap_lock:
            if self._cap is not None and self._cap.isOpened():
                return True
            self._cap = cv2.VideoCapture(self._camera_id)
            opened = self._cap.isOpened()
            if opened:
                logger.info(f"Camera {self._camera_id} opened")
            else:
                logger.error(f"Failed to open camera {self._camera_id}")
            return opened

    def close_camera(self) -> None:
        """Release the camera."""
        with self._cap_lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("Camera released")

    def capture_frame(self) -> Optional[np.ndarray]:
        """Capture a single frame from the camera."""
        with self._cap_lock:
            if self._cap is None or not self._cap.isOpened():
                return None
            ret, frame = self._cap.read()
            return frame if ret else None

    @staticmethod
    def _frame_to_base64(frame: np.ndarray) -> str:
        """Encode a CV2 BGR frame to base64 JPEG string for OpenAI vision."""
        _, buffer = cv2.imencode(".jpg", frame)
        return base64.b64encode(buffer).decode("utf-8")

    # ── OpenAI Vision Judgment ──

    SCENE_PROMPT = """\
你是一个机器人场景状态判断器。你正在观看一个 top-view 摄像头的画面。

请判断以下两种场景状态：
1. 瓶子在不在盒子里？（true = 在盒子里, false = 不在盒子里）
2. 瓶子在黄色纸上还是绿色纸上？（"yellow" = 黄色纸上, "green" = 绿色纸上, null = 无法判断或不在纸上）

## 输出格式（严格 JSON，不要任何其他文字）
{"bottle_in_box": true或false, "bottle_on_paper": "yellow"或"green"或null, "reason": "<简要描述你看到的情况>", "confidence": <0.0到1.0的置信度>}
"""

    def judge_scene(self, frame: np.ndarray) -> SceneState:
        """Send a frame to OpenAI and get scene state judgment.

        Args:
            frame: BGR image from OpenCV

        Returns:
            SceneState with bottle_in_box, bottle_on_paper, reason, confidence
        """
        b64_image = self._frame_to_base64(frame)

        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.SCENE_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{b64_image}",
                                },
                            },
                        ],
                    }
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            raw = response.choices[0].message.content.strip()
            return self._parse_scene_state(raw)

        except Exception as e:
            logger.error(f"OpenAI vision call failed: {e}")
            return SceneState(
                reason=f"Vision API error: {e}",
                confidence=0.0,
            )

    def _parse_scene_state(self, raw: str) -> SceneState:
        """Parse OpenAI JSON response into SceneState."""
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()

            data = json.loads(text)

            bottle_in_box = data.get("bottle_in_box")
            if not isinstance(bottle_in_box, bool):
                bottle_in_box = None

            bottle_on_paper = data.get("bottle_on_paper")
            if bottle_on_paper not in ("yellow", "green", None):
                bottle_on_paper = None

            return SceneState(
                bottle_in_box=bottle_in_box,
                bottle_on_paper=bottle_on_paper,
                reason=data.get("reason", ""),
                confidence=float(data.get("confidence", 0.0)),
            )
        except Exception as e:
            logger.warning(f"Failed to parse scene state: {e}, raw={raw}")
            return SceneState(
                reason=f"Parse error: {raw[:100]}",
                confidence=0.0,
            )

    # ── Monitoring Loop ──

    def start_monitoring(
        self,
        subtask_context: str,
        state: MonitorState,
        on_event: Optional[Callable[[str, str], None]] = None,
    ) -> threading.Thread:
        """Start a background monitoring thread for the current subtask.

        Args:
            subtask_context: Description of the subtask (e.g. "place_in")
            state: Shared MonitorState for communication with dispatch loop
            on_event: Optional callback(event_type, message) for logging events

        Returns:
            The monitoring thread (already started)
        """
        self._on_event = on_event
        state.reset()

        thread = threading.Thread(
            target=self._monitor_loop,
            args=(subtask_context, state),
            daemon=True,
            name=f"vision-monitor-{subtask_context[:20]}",
        )
        thread.start()
        return thread

    def _monitor_loop(self, subtask_context: str, state: MonitorState) -> None:
        """Internal monitoring loop — runs every interval_sec until stopped."""
        logger.info(f"Vision monitor started for: {subtask_context}")
        self._emit_event("vision_start", f"开始视觉监控: {subtask_context}")

        cycle = 0
        while not state.is_stopped:
            time.sleep(self._interval)

            if state.is_stopped:
                break

            frame = self.capture_frame()
            if frame is None:
                logger.warning("Failed to capture frame — skipping cycle")
                continue

            cycle += 1
            scene = self.judge_scene(frame)
            state.update(scene)

            box_status = "在盒子里" if scene.bottle_in_box else "不在盒子里" if scene.bottle_in_box is False else "未知"
            paper_status = f"在{scene.bottle_on_paper}色纸上" if scene.bottle_on_paper else "未知"

            logger.info(
                f"[Vision #{cycle}] 瓶子{box_status}, {paper_status} "
                f"(confidence={scene.confidence:.2f}): {scene.reason}"
            )
            self._emit_event(
                "vision_check",
                f"#{cycle} 瓶子{box_status}, {paper_status} "
                f"({scene.confidence:.0%}): {scene.reason}",
            )

        logger.info(f"Vision monitor stopped for: {subtask_context}")

    def judge_final_state(self, subtask_context: str) -> SceneState:
        """Capture one frame and do a final scene state judgment.

        Returns:
            SceneState for the final state
        """
        frame = self.capture_frame()
        if frame is None:
            logger.warning("Cannot capture final frame — returning default")
            return SceneState(
                reason="Cannot capture frame for final judgment",
                confidence=0.0,
            )

        scene = self.judge_scene(frame)
        box_status = "在盒子里" if scene.bottle_in_box else "不在盒子里" if scene.bottle_in_box is False else "未知"
        paper_status = f"在{scene.bottle_on_paper}色纸上" if scene.bottle_on_paper else "未知"
        self._emit_event(
            "vision_final",
            f"终态确认: 瓶子{box_status}, {paper_status} "
            f"({scene.confidence:.0%}): {scene.reason}",
        )
        return scene

    def _emit_event(self, event_type: str, message: str) -> None:
        """Emit event via callback if set."""
        if self._on_event:
            try:
                self._on_event(event_type, message)
            except Exception:
                pass
