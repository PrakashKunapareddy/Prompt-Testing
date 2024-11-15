import json
import re
import logging
from enum import Enum


class INTENTS(Enum):
    TRADE_APPLICATION = "Trade Application"
    ORDER_STATUS = "Order Status"
    PRODUCT_AVAILABILITY = "Product Availability"
    DAMAGES = "Damages"
    RETURNS = "Returns"
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


def get_intent_name_and_scores(intent_classification_result):
    intent_data = extract_json_object(intent_classification_result)
    if intent_data:
        intents = intent_data.get("intent", [])
        if isinstance(intents, list):
            classified_intents = []
            for intent in intents:
                intent_name = intent.get("intent_name", INTENTS.OTHERS.value)
                similarity_score = float(intent.get("similarity_score", 0.0))
                classified_intents.append({
                    "intent_name": intent_name,
                    "similarity_score": similarity_score
                })
            return classified_intents
    return [{"intent_name": INTENTS.OTHERS.value, "similarity_score": 0.0}]


def parse_bot_response(intent_classification_result):
    intent_data = extract_json_object(intent_classification_result)
    if intent_data:
        bot_likely_response = intent_data.get("bot_likely_response", "")
        reason = intent_data.get("reason", "")
        return bot_likely_response, reason
    return "", ""


def get_sub_intent_classification(sub_intent_classification_result):
    sub_intent_data = extract_json_object(sub_intent_classification_result)
    if sub_intent_data:
        sub_intent = sub_intent_data.get("sub_intent", "")
        bot_likely_response = sub_intent_data.get("bot_likely_response", "")
        reason = sub_intent_data.get("reason", "")
        return sub_intent, bot_likely_response, reason
    return "", "", ""


def process_classifications(input_string, sub_intent_string):
    intents = get_intent_name_and_scores(input_string)
    bot_likely_response, reason = parse_bot_response(input_string)
    sub_intent, sub_bot_response, sub_reason = get_sub_intent_classification(sub_intent_string)
    intent_output = {
        "classified_intents": intents,
        "bot_likely_response": bot_likely_response,
        "reason": reason
    }

    sub_intent_output = {
        "sub_intent": sub_intent,
        "bot_likely_response": sub_bot_response,
        "reason": sub_reason
    }

    return [intent_output, sub_intent_output]
