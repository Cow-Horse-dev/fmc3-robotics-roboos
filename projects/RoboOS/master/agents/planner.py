"""
master/agents/planner.py
─────────────────────────
GlobalTaskPlanner：两阶段 LLM 调用
  1. classify(instruction)  →  intent str（M-1.1 / M-1.2）
  2. plan(intent)           →  subtask_list JSON（M-2.x）
"""

import json
from typing import Any, Dict, Optional, Tuple, Union

import yaml
from agents.prompts import CLASSIFY_PROMPT, PLANNING_PROMPT
from flag_scale.flagscale.agent.collaboration import Collaborator
from openai import AzureOpenAI, OpenAI

# 合法意图白名单
VALID_INTENTS = {
    # Box scenario
    "PUT", "TAKE", "PUT_THEN_TAKE", "TAKE_THEN_PUT",
    # Green-yellow scenario
    "GREEN_TO_YELLOW", "YELLOW_TO_GREEN",
    "GREEN_YELLOW_THEN_YELLOW_GREEN", "YELLOW_GREEN_THEN_GREEN_YELLOW",
}


class GlobalTaskPlanner:
    """
    两阶段规划器：
      Step 1  classify()  ── 用 LLM 判断指令意图，过滤非法指令（M-1.1 / M-1.2）
      Step 2  plan()      ── 用 LLM 将合法意图规划为有序子任务列表（M-2.x）
    """

    def __init__(self, config: Union[Dict, str] = None) -> None:
        self.collaborator = Collaborator.from_config(config["collaborator"])
        self.profiling    = config.get("profiling", False)

        self.global_model: Any
        self.model_name: str
        self.global_model, self.model_name = self._get_model_from_config(config["model"])

    # ------------------------------------------------------------------ #
    #  公开接口                                                            #
    # ------------------------------------------------------------------ #

    def classify(self, instruction: str) -> str:
        """
        M-1.1 / M-1.2：将用户自然语言指令分类为意图。
        返回值为 VALID_INTENTS 之一，或 "INVALID"。

        对接说明（给 GlobalAgent）：
            intent = planner.classify(user_text)
            if intent == "INVALID":
                # 回馈「指令无效」到 UI，不继续执行
        """
        prompt = CLASSIFY_PROMPT.format(user_instruction=instruction)
        raw    = self._call_llm(prompt, max_tokens=64)
        intent = self._parse_intent(raw)
        self._log("classify result", f"{instruction!r} → {intent}")
        return intent

    def plan(self, intent: str) -> Optional[Dict]:
        """
        M-2.x：根据意图规划子任务列表。
        返回 dict（含 subtask_list），或 None（规划失败）。

        对接说明（给 GlobalAgent）：
            plan_result = planner.plan(intent)
            if plan_result is None:
                # 规划失败，终止流程
        """
        all_robots_name = self.collaborator.read_all_agents_name()
        all_robots_info = self.collaborator.read_all_agents_info()
        scene_info      = self.collaborator.read_environment(name=None)

        prompt = PLANNING_PROMPT.format(
            intent=intent,
            robot_name_list=all_robots_name,
            robot_tools_info=all_robots_info,
            scene_info=scene_info,
        )
        raw    = self._call_llm(prompt, max_tokens=1024)
        result = self._parse_json(raw)
        self._log("plan result", result)
        return result

    # ------------------------------------------------------------------ #
    #  内部工具                                                            #
    # ------------------------------------------------------------------ #

    def _call_llm(self, prompt: str, max_tokens: int = 1024) -> str:
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        self._log("LLM input", prompt)

        response = self.global_model.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.2,
            top_p=0.9,
            max_tokens=max_tokens,
            seed=42,
        )
        content = response.choices[0].message.content
        self._log("LLM output", content)
        return content

    def _parse_intent(self, raw: str) -> str:
        """从 LLM 输出解析 intent 字串，失败时返回 INVALID。"""
        try:
            text = raw.strip()
            # 容错：移除 markdown 代码块
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()
            data   = json.loads(text)
            intent = str(data.get("intent", "INVALID")).upper().strip()
            return intent if intent in VALID_INTENTS else "INVALID"
        except Exception:
            return "INVALID"

    def _parse_json(self, raw: str) -> Optional[Dict]:
        """从 LLM 输出解析 JSON dict，失败时返回 None。"""
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("```")[1].lstrip("json").strip()
            # 尝试直接解析
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
            # 容错：找第一个 { ... }
            s = text.find("{")
            e = text.rfind("}")
            if s != -1 and e != -1:
                return json.loads(text[s:e+1])
            return None
        except Exception:
            return None

    def _get_model_from_config(self, config: Dict) -> Tuple[Any, str]:
        candidate = config["model_dict"]
        if candidate["cloud_model"] in config["model_select"]:
            if candidate["cloud_type"] == "azure":
                client = AzureOpenAI(
                    azure_endpoint=candidate["azure_endpoint"],
                    azure_deployment=candidate["azure_deployment"],
                    api_version=candidate["azure_api_version"],
                    api_key=candidate["azure_api_key"],
                )
            elif candidate["cloud_type"] == "default":
                client = OpenAI(
                    base_url=candidate["cloud_server"],
                    api_key=candidate["cloud_api_key"],
                )
            else:
                raise ValueError(f"Unsupported cloud type: {candidate['cloud_type']}")
            return client, config["model_select"]
        raise ValueError(f"Unsupported model: {config['model_select']}")

    def _log(self, label: str, content: Any):
        if self.profiling:
            print(f"[planner] {label}: {content}")
