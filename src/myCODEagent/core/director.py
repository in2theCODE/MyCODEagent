import argparse
import shlex
import subprocess
import sys
from pathlib import Path
from typing import List, Literal, Optional, Dict, Any

import yaml
from openai import OpenAI
from pydantic import BaseModel
from aiden.coders import Coder
from aiden.models import Model
from aiden.io import InputOutput


class AgentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]]
    error: Optional[str]


class EvaluationResult(BaseModel):
    success: bool
    feedback: Optional[str]


class DirectorConfig(BaseModel):
    prompt: str
    coder_model: str
    evaluator_model: Literal["gpt-4o", "gpt-4o-mini", "o1-mini", "o1-preview"]
    max_iterations: int
    execution_command: str
    context_editable: List[str]
    context_read_only: List[str]
    evaluator: Literal["default"]


class Director:
    """
    Self Directed AI Coding Assistant
    """

    def __init__(self, config_path: str):
        self.config = self.validate_config(Path(config_path))
        self.llm_client = OpenAI()

    @staticmethod
    def validate_config(config_path: Path) -> DirectorConfig:
        """Validate the yaml config file and return DirectorConfig object."""
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config_dict = yaml.safe_load(f)

        # If prompt ends with .md, read content from that file
        if config_dict["prompt"].endswith(".md"):
            prompt_path = Path(config_dict["prompt"])
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            with open(prompt_path) as f:
                config_dict["prompt"] = f.read()

        config = DirectorConfig(**config_dict)

        # Validate evaluator_model is one of the allowed values
        allowed_evaluator_models = {"gpt-4o", "gpt-4o-mini", "o1-mini", "o1-preview"}
        if config.evaluator_model not in allowed_evaluator_models:
            raise ValueError(
                f"evaluator_model must be one of {allowed_evaluator_models}, "
                f"got {config.evaluator_model}"
            )

        # Validate we have at least 1 editable file
        if not config.context_editable:
            raise ValueError("At least one editable context file must be specified")

        # Validate all paths in context_editable and context_read_only exist
        for path in config.context_editable:
            if not Path(path).exists():
                raise FileNotFoundError(f"Editable context file not found: {path}")

        for path in config.context_read_only:
            if not Path(path).exists():
                raise FileNotFoundError(f"Read-only context file not found: {path}")

        return config

    def parse_llm_json_response(self, response_str: str) -> str:
        """
        Parse and fix the response from an LLM that is expected to return JSON.
        
        Args:
            response_str: Raw response string from the LLM
            
        Returns:
            str: Cleaned JSON string with markdown and whitespace removed
        """
        if "```" not in response_str:
            response_str = response_str.strip()
            self.file_log(f"raw pre-json-parse: {response_str}", print_message=False)
            return response_str

        # Remove opening backticks and language identifier
        response_str = response_str.split("```", 1)[-1].split("\n", 1)[-1]

        # Remove closing backticks
        response_str = response_str.rsplit("```", 1)[0]

        response_str = response_str.strip()

        self.file_log(f"post-json-parse: {response_str}", print_message=False)

        # Remove any leading or trailing whitespace
        return response_str

    def file_log(self, message: str, print_message: bool = True) -> None:
        if print_message:
            print(message)
        with open("director_log.txt", "a+") as f:
            f.write(message + "\n")

    # ------------- Key Director Methods -------------

    def create_new_ai_coding_prompt(
        self,
        iteration: int,
        base_input_prompt: str,
        execution_output: str,
        evaluation: EvaluationResult,
    ) -> str:
        """
        Create a new prompt for the AI coder based on previous results.
        
        Args:
            iteration: Current iteration number
            base_input_prompt: Original user prompt
            execution_output: Output from previous code execution
            evaluation: Previous evaluation result
            
        Returns:
            str: New prompt incorporating feedback
        """
        if iteration == 0:
            return base_input_prompt
        else:
            return f"""
# Generate the next iteration of code to achieve the user's desired result based on their original instructions and the feedback from the previous attempt.
> Generate a new prompt in the same style as the original instructions for the next iteration of code.

## This is your {iteration}th attempt to generate the code.
> You have {self.config.max_iterations - iteration} attempts remaining.

## Here's the user's original instructions for generating the code:
{base_input_prompt}

## Here's the output of your previous attempt:
{execution_output}

## Here's feedback on your previous attempt:
{evaluation.feedback}"""

    def ai_code(self, prompt: str) -> None:
        """
        Generate code using the configured AI model.
        
        Args:
            prompt: The prompt describing desired code changes
        """
        model = Model(self.config.coder_model)
        coder = Coder.create(
            main_model=model,
            io=InputOutput(yes=True),
            fnames=self.config.context_editable,
            read_only_fnames=self.config.context_read_only,
            auto_commits=False,
            suggest_shell_commands=False,
            detect_urls=False,
        )
        coder.run(prompt)

    def execute(self) -> str:
        """
        Execute the tests and return the output as a string.
        
        Returns:
            str: Combined stdout and stderr from command execution
            
        Raises:
            subprocess.SubprocessError: If command execution fails
        """
        result = subprocess.run(
            shlex.split(self.config.execution_command),
            capture_output=True,
            text=True,
        )
        self.file_log(
            f"Execution output: \n{result.stdout + result.stderr}",
            print_message=False,
        )
        return result.stdout + result.stderr

    def evaluate(self, execution_output: str) -> EvaluationResult:

        if self.config.evaluator != "default":
            raise ValueError(
                f"Custom evaluator {self.config.evaluator} not implemented"
            )

        map_editable_fname_to_files = {
            Path(fname).name: Path(fname).read_text()
            for fname in self.config.context_editable
        }

        map_read_only_fname_to_files = {
            Path(fname).name: Path(fname).read_text()
            for fname in self.config.context_read_only
        }

        evaluation_prompt = f"""Evaluate this execution output and determine if it was successful based on the execution command, the user's desired result, the editable files, checklist, and the read-only files.

## Checklist:
- Is the execution output reporting success or failure?
- Did we miss any tasks? Review the User's Desired Result to see if we have satisfied all tasks.
- Did we satisfy the user's desired result?
- Ignore warnings

## User's Desired Result:
{self.config.prompt}

## Editable Files:
{map_editable_fname_to_files}

## Read-Only Files:
{map_read_only_fname_to_files}

## Execution Command:
{self.config.execution_command}

## Execution Output:
{execution_output}

## Response Format:
> Be 100% sure to output JSON.parse compatible JSON.
> That means no new lines.

Return a structured JSON response with the following structure: {{
    success: bool - true if the execution output generated by the execution command matches the Users Desired Result
    feedback: str | None - if unsuccessful, provide detailed feedback explaining what failed and how to fix it, or None if successful
}}"""

        self.file_log(
            f"Evaluation prompt: ({self.config.evaluator_model}):\n{evaluation_prompt}",
            print_message=False,
        )

        try:
            completion = self.llm_client.chat.completions.create(
                model=self.config.evaluator_model,
                messages=[
                    {
                        "role": "user",
                        "content": evaluation_prompt,
                    },
                ],
            )

            self.file_log(
                f"Evaluation response: ({self.config.evaluator_model}):\n{completion.choices[0].message.content}",
                print_message=False,
            )

            evaluation = EvaluationResult.model_validate_json(
                self.parse_llm_json_response(completion.choices[0].message.content)
            )

            return evaluation
        except Exception as e:

            self.file_log(
                f"Error evaluating execution output for '{self.config.evaluator_model}'. Error: {e}. Falling back to gpt-4o & structured output."
            )

            ## Fallback
            completion = self.llm_client.beta.chat.completions.parse(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": evaluation_prompt,
                    },
                ],
                response_format=EvaluationResult,
            )

            message = completion.choices[0].message
            if message.parsed:
                return message.parsed
            else:
                raise ValueError("Failed to parse the response")

    def direct(self):
        evaluation = EvaluationResult(success=False, feedback=None)
        execution_output = ""
        success = False

        for i in range(self.config.max_iterations):
            self.file_log(f"\nIteration {i + 1}/{self.config.max_iterations}")

            self.file_log("🧠 Creating new prompt...")
            new_prompt = self.create_new_ai_coding_prompt(
                i, self.config.prompt, execution_output, evaluation
            )

            self.file_log("🤖 Generating AI code...")
            self.ai_code(new_prompt)

            self.file_log(f"💻 Executing code... '{self.config.execution_command}'")
            execution_output = self.execute()

            self.file_log(
                f"🔍 Evaluating results... '{self.config.evaluator_model}' + '{self.config.evaluator}'"
            )
            evaluation = self.evaluate(execution_output)

            self.file_log(
                f"🔍 Evaluation result: {'✅ Success' if evaluation.success else '❌ Failed'}"
            )
            if evaluation.feedback:
                self.file_log(f"💬 Feedback: \n{evaluation.feedback}")

            if evaluation.success:
                success = True
                self.file_log(
                    f"\n🎉 Success achieved after {i + 1} iterations! Breaking out of iteration loop."
                )
                break
            else:
                self.file_log(
                    f"\n🔄 Continuing with next iteration... Have {self.config.max_iterations - i - 1} attempts remaining."
                )

        if not success:
            self.file_log(
                "\n🚫 Failed to achieve success within the maximum number of iterations."
            )

        self.file_log("\nDone.")




def main() -> None:
    """Main entry point for the Director CLI."""
    parser = argparse.ArgumentParser(
        description="Run the AI Coding Director with a config file"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="specs/basic.yaml",
        help="Path to the YAML config file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    try:
        director = Director(args.config)
        director.direct()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
