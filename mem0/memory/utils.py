import re
import logging
from copy import deepcopy
from typing import Any, Dict, Optional, Tuple, List

from mem0.configs.prompts import (
    FACT_RETRIEVAL_PROMPT,
    USER_MEMORY_EXTRACTION_PROMPT,
    AGENT_MEMORY_EXTRACTION_PROMPT,
)

logger = logging.getLogger(__name__)


def get_fact_retrieval_messages(message, is_agent_memory=False):
    """Get fact retrieval messages based on the memory type.

    Args:
        message: The message content to extract facts from
        is_agent_memory: If True, use agent memory extraction prompt, else use user memory extraction prompt

    Returns:
        tuple: (system_prompt, user_prompt)
    """
    if is_agent_memory:
        return AGENT_MEMORY_EXTRACTION_PROMPT, f"Input:\n{message}"
    else:
        return USER_MEMORY_EXTRACTION_PROMPT, f"Input:\n{message}"


def get_graph_extraction_prompt(message):
    from mem0.configs.prompts import GRAPH_MEMORY_EXTRACTION_PROMPT

    return GRAPH_MEMORY_EXTRACTION_PROMPT.format(text=message)


def get_fact_retrieval_messages_legacy(message):
    """Legacy function for backward compatibility."""
    return FACT_RETRIEVAL_PROMPT, f"Input:\n{message}"


def parse_messages(messages):
    response = ""
    for msg in messages:
        if msg["role"] == "system":
            response += f"system: {msg['content']}\n"
        if msg["role"] == "user":
            response += f"user: {msg['content']}\n"
        if msg["role"] == "assistant":
            response += f"assistant: {msg['content']}\n"
    return response


def format_entities(entities):
    if not entities:
        return ""

    formatted_lines = []
    for entity in entities:
        simplified = f"{entity['source']} -- {entity['relationship']} -- {entity['destination']}"
        formatted_lines.append(simplified)

    return "\n".join(formatted_lines)


def remove_code_blocks(content: str) -> str:
    """
    Removes enclosing code block markers ```[language] and ``` from a given string.

    Remarks:
    - The function uses a regex pattern to match code blocks that may start with ``` followed by an optional language tag (letters or numbers) and end with ```.
    - If a code block is detected, it returns only the inner content, stripping out the markers.
    - If no code block markers are found, the original content is returned as-is.
    """
    pattern = r"^```[a-zA-Z0-9]*\n([\s\S]*?)\n```$"
    match = re.match(pattern, content.strip())
    match_res = match.group(1).strip() if match else content.strip()
    return re.sub(r"<think>.*?</think>", "", match_res, flags=re.DOTALL).strip()


def extract_json(text):
    """
    Extracts JSON content from a string, removing enclosing triple backticks and optional 'json' tag if present.
    If no code block is found, returns the text as-is.
    """
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        json_str = text  # assume it's raw JSON
    return json_str


def get_image_description(image_obj, llm, vision_details):
    """
    Get the description of the image
    """
    # Placeholder implementation
    return "Image description placeholder"

def parse_vision_messages(messages):
    """
    Parse messages containing vision content.
    """
    # Placeholder implementation
    return messages

def process_telemetry_filters(filters: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """
    Process filters for telemetry to extract keys and values.
    """
    if not filters:
        return [], []
    keys = list(filters.keys())
    # simplistic implementation - in real world might hash values
    encoded_ids = [str(filters[k]) for k in keys]
    return keys, encoded_ids

def build_filters_and_metadata(
    user_id: Optional[str] = None,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    input_metadata: Optional[Dict[str, Any]] = None,
    input_filters: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Construct metadata and filters based on identifiers and inputs.
    """
    base_filters = {}
    base_metadata = {}

    if user_id:
        base_filters["user_id"] = user_id
        base_metadata["user_id"] = user_id
    if agent_id:
        base_filters["agent_id"] = agent_id
        base_metadata["agent_id"] = agent_id
    if run_id:
        base_filters["run_id"] = run_id
        base_metadata["run_id"] = run_id

    final_metadata = base_metadata.copy()
    if input_metadata:
        final_metadata.update(input_metadata)

    final_filters = base_filters.copy()
    if input_filters:
        final_filters.update(input_filters)

    return final_metadata, final_filters

def _safe_deepcopy_config(config):
    """
    Safely copies a configuration object.
    """
    if hasattr(config, "model_copy"):
        return config.model_copy(deep=True)
    return deepcopy(config)

def select_fields(records, fields: Optional[List[str]] = None):
    if not fields:
        return records
    field_set = set(fields)
    selected = []
    for record in records:
        if not isinstance(record, dict):
            selected.append(record)
            continue
        selected.append({k: v for k, v in record.items() if k in field_set})
    return selected
