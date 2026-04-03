from typing import Any, Dict, Union

import yaml
from agents.prompts import MASTER_PLANNING_PLANNING
from agents.prompt_repair import PromptRepairEngine
from flag_scale.flagscale.agent.collaboration import Collaborator
from openai import AzureOpenAI, OpenAI


class GlobalTaskPlanner:
    """A tool planner to plan task into sub-tasks."""

    def __init__(
        self,
        config: Union[Dict, str] = None,
    ) -> None:
        self.collaborator = Collaborator.from_config(config["collaborator"])

        self.global_model: Any
        self.model_name: str
        self.global_model, self.model_name = self._get_model_info_from_config(
            config["model"]
        )

        self.profiling = config["profiling"]
        self.repair_engine = PromptRepairEngine(
            max_replan=config.get("model", {}).get("max_replan", 3)
        )

    def _get_model_info_from_config(self, config: Dict) -> tuple:
        """Get the model info from config."""
        candidate = config["model_dict"]
        if candidate["cloud_model"] in config["model_select"]:
            if candidate["cloud_type"] == "azure":
                model_name = config["model_select"]
                model_client = AzureOpenAI(
                    azure_endpoint=candidate["azure_endpoint"],
                    azure_deployment=candidate["azure_deployment"],
                    api_version=candidate["azure_api_version"],
                    api_key=candidate["azure_api_key"],
                )
            elif candidate["cloud_type"] == "default":
                model_client = OpenAI(
                    base_url=candidate["cloud_server"],
                    api_key=candidate["cloud_api_key"],
                )
                model_name = config["model_select"]
            else:
                raise ValueError(f"Unsupported cloud type: {candidate['cloud_type']}")
            return model_client, model_name
        raise ValueError(f"Unsupported model: {config['model_select']}")

    def _init_config(self, config_path="config.yaml"):
        """Initialize configuration"""
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config

    def display_profiling_info(self, description: str, message: any):
        """
        Outputs profiling information if profiling is enabled.

        :param message: The content to be printed. Can be of any type.
        :param description: A brief title or description for the message.
        """
        if self.profiling:
            module_name = "master"  # Name of the current module
            print(f" [{module_name}] {description}:")
            print(message)

    def forward(self, task: str) -> str:
        """Get the sub-tasks from the task."""

        all_robots_name = self.collaborator.read_all_agents_name()
        all_robots_info = self.collaborator.read_all_agents_info()
        all_environments_info = self.collaborator.read_environment(name=None)

        content = MASTER_PLANNING_PLANNING.format(
            robot_name_list=all_robots_name, robot_tools_info=all_robots_info, task=task, scene_info=all_environments_info
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": content},
                ],
            },
        ]

        self.display_profiling_info("messages", messages)

        from datetime import datetime

        start_inference = datetime.now()
        response = self.global_model.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.2,
            top_p=0.9,
            max_tokens=2048,
            seed=42,
        )
        end_inference = datetime.now()

        self.display_profiling_info(
            "inference time",
            f"inference start:{start_inference} end:{end_inference} during:{end_inference-start_inference}",
        )
        self.display_profiling_info("response", response)
        self.display_profiling_info("response.usage", response.usage)

        return response.choices[0].message.content

    def repair_forward(
        self,
        original_task: str,
        failed_subtask: str,
        failed_robot: str,
        failure_info: Dict,
        completed_subtasks: list,
        replan_attempt: int,
    ) -> str:
        """Generate a repair plan using failure context.

        Instead of the generic planning prompt, this uses the
        REPAIR_PLANNING_PROMPT which includes failure analysis
        and instructs the LLM to avoid the same failure.
        """
        all_robots_name = self.collaborator.read_all_agents_name()
        all_robots_info = self.collaborator.read_all_agents_info()
        all_environments_info = self.collaborator.read_environment(name=None)

        repair_prompt = self.repair_engine.build_repair_prompt(
            original_task=original_task,
            failed_subtask=failed_subtask,
            failed_robot=failed_robot,
            failure_info=failure_info,
            completed_subtasks=completed_subtasks,
            replan_attempt=replan_attempt,
            robot_name_list=str(all_robots_name),
            robot_tools_info=str(all_robots_info),
            scene_info=str(all_environments_info),
        )

        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": repair_prompt}],
            },
        ]

        self.display_profiling_info("repair_messages", messages)

        from datetime import datetime

        start_inference = datetime.now()
        response = self.global_model.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.4,  # slightly higher for creative repair strategies
            top_p=0.9,
            max_tokens=2048,
            seed=None,  # no fixed seed — allow different repair attempts
        )
        end_inference = datetime.now()

        self.display_profiling_info(
            "repair inference time",
            f"start:{start_inference} end:{end_inference} during:{end_inference - start_inference}",
        )
        self.display_profiling_info("repair response", response)

        return response.choices[0].message.content
