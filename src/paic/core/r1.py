import json
from typing import Dict, List

import ollama

R1_MODEL = "r1"


def prompt(prompt: str, model: str = R1_MODEL) -> str:
    """
    Send a prompt to R1 and get detailed response.
    """
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.message.content


def fill_in_the_middle_prompt(prompt: str, suffix: str, model: str = R1_MODEL) -> str:
    """
    Send a fill-in-the-middle prompt to R1 and get response.
    """
    # Format the FIM prompt for R1
    fim_prompt = f"{prompt}\n[Your task is to complete the code between the prefix and suffix]\n{suffix}"
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": fim_prompt}]
    )
    return prompt + response.message.content + suffix


def json_prompt(prompt: str, model: str = R1_MODEL) -> dict:
    """
    Send a prompt to R1 and get JSON response.

    Args:
        prompt: The user prompt to send
        model: The model to use, defaults to r1

    Returns:
        dict: The parsed JSON response
    """
    # Add JSON formatting instruction
    json_prompt = f"{prompt}\n[Please respond with valid JSON only]"
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": json_prompt}]
    )
    return json.loads(response.message.content)


def prefix_prompt(prompt: str, prefix: str, model: str = R1_MODEL, no_prefix: bool = False) -> str:
    """
    Send a prompt to R1 with a prefix constraint and get 'prefix + response'

    Args:
        prompt: The user prompt to send
        prefix: The required prefix for the response
        model: The model to use, defaults to r1
        no_prefix: If True, the prefix is not added to the response
    Returns:
        str: The model's response constrained by the prefix
    """
    # Format the prefix prompt
    prefix_prompt = f"{prompt}\n[Your response must start with: {prefix}]"
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prefix_prompt}]
    )
    content = response.message.content
    return content if no_prefix else prefix + content


def prefix_then_stop_prompt(prompt: str, prefix: str, suffix: str, model: str = R1_MODEL) -> str:
    """
    Send a prompt to R1 with a prefix and suffix constraint

    Args:
        prompt: The user prompt to send
        prefix: The required prefix for the response
        suffix: The required suffix for the response
        model: The model to use, defaults to r1

    Returns:
        str: The model's response constrained by the prefix and suffix
    """
    # Format the prefix-suffix prompt
    constrained_prompt = f"{prompt}\n[Your response must start with: {prefix} and end with: {suffix}]"
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": constrained_prompt}]
    )
    return response.message.content


def conversational_prompt(
    messages: List[Dict[str, str]],
    system_prompt: str = "You are a helpful conversational assistant. Respond in a short, concise, friendly manner.",
    model: str = R1_MODEL,
) -> str:
    """
    Send a conversational prompt to R1 with message history.

    Args:
        messages: List of message dicts with 'role' and 'content' keys
        system_prompt: Optional system prompt to set context
        model: The model to use, defaults to r1

    Returns:
        str: The model's response
    """
    # Format messages for Ollama
    formatted_messages = [{"role": "system", "content": system_prompt}]
    formatted_messages.extend(messages)
    
    response = ollama.chat(
        model=model,
        messages=formatted_messages
    )
    return response.message.content
