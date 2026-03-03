"""
Validates and normalizes Claude's JSON output.
"""

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_VALID_ACTIONS = {"HOLD", "BUY", "ADD", "REDUCE", "AVOID", "WAIT"}
_VALID_CONVICTION = {"HIGH", "MEDIUM", "LOW"}
_VALID_URGENCY = {"immediate", "standard", "low"}


def parse_recommendation(raw_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Parse and validate Claude's raw text response.

    Returns (parsed_dict, error_message).
    If parsing succeeds, error_message is None.
    If parsing fails, parsed_dict is None.
    """
    # Strip any accidental markdown fences
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"JSON decode error: {e}"

    # Minimal structural validation
    rec = data.get("recommendation", {})
    action = rec.get("current_action", "")
    if action not in _VALID_ACTIONS:
        logger.warning(f"Unexpected action value: {action!r}")

    conviction = rec.get("conviction", "")
    if conviction not in _VALID_CONVICTION:
        logger.warning(f"Unexpected conviction value: {conviction!r}")

    # Ensure disclaimer is present
    if "confidence_disclaimer" not in data:
        data["confidence_disclaimer"] = "Suggestion only. Always do your own research."

    return data, None
