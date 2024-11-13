import json
import re
import logging
from enum import Enum


class INTENTS(Enum):
    TRADE_APPLICATION = "Trade Application"
    ORDER_STATUS = "Order Status"
    PRODUCT_INFORMATION = "Product Availability"
    DAMAGES = "Damages"
    RETURNS = "Returns"
    SMALL_TALK = "Small Talk"
    CSR = "CSR"
    INTENT_NOT_IDENTIFIED = "Intent Not Identified"
    OTHERS = "Others"

logger = logging.getLogger(__name__)

def extract_json_object(input_string):
    json_pattern = r'\{.*\}'
    match = re.search(json_pattern, input_string, re.DOTALL)

    if match:
        json_str = match.group(0)
        try:
            json_object = json.loads(json_str)
            logger.info("Successfully extracted and parsed JSON")
            return json_object
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None
    logger.error("No valid JSON found in input string")
    return None

def get_intent_name(intent_classification_result):
    intent_data = extract_json_object(intent_classification_result)
    if intent_data:
        intents = intent_data.get("intent", [])
        if isinstance(intents, list):
            if len(intents) == 1:
                return intents[0].get("intent_name", INTENTS.OTHERS.value)
            else:
                return [intent.get("intent_name") for intent in intents]
    return INTENTS.OTHERS.value

