from datetime import datetime
import openpyxl
import json
import logging
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_community.chat_models import AzureChatOpenAI

import SubIntentClassificationEmail
from ExampleSearchChromaDB import fetch_similar_queries_for_intent, fetch_similar_queries
from IntentClassificationPromptEmail import IntentClassificationPromptEmail
from otherSubIntents import Others


class NoHTTPRequestsFilter(logging.Filter):
    def filter(self, record):
        return 'HTTP' not in record.getMessage()


def gpt_call(config):
    return AzureChatOpenAI(
        deployment_name=config["OPENAI_DEPLOYMENT_NAME"],
        model_name=config["MODEL_NAME"],
        openai_api_base=config["OPENAI_API_BASE"],
        openai_api_type=config["OPENAI_API_TYPE"],
        openai_api_key=config["OPENAI_API_KEY"],
        openai_api_version=config["OPENAI_API_VERSION"],
        temperature=0.0
    )


def create_prompt_template(system_msg, context_msg, display_msg, remember_msg):
    return ChatPromptTemplate(
        messages=[
            SystemMessagePromptTemplate.from_template(system_msg),
            HumanMessagePromptTemplate.from_template(context_msg),
            SystemMessagePromptTemplate.from_template(display_msg),
            SystemMessagePromptTemplate.from_template(remember_msg)
        ]
    )


def parse_email_data(email_data):
    if not email_data:
        return "", "", ""
    parts = email_data.split("USER_LATEST_EMAIL:")
    email_history = parts[0].strip()
    user_latest_email = parts[1].strip() if len(parts) > 1 else ""
    user_latest_email_body = user_latest_email.split("Body:")[1] if "Body:" in user_latest_email else user_latest_email
    return email_history, user_latest_email, user_latest_email_body


def intent_classification(email_body, examples, llm):
    prompt_template = create_prompt_template(
        IntentClassificationPromptEmail.get("SYSTEM"),
        IntentClassificationPromptEmail.get("CONTEXT"),
        IntentClassificationPromptEmail.get("DISPLAY"),
        IntentClassificationPromptEmail.get("REMEMBER")
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template, verbose=False)
    return llm_chain.run({"email_history": email_body, "examples": examples})


def sub_intent_classification(email_body, intent, llm):
    sub_examples = fetch_similar_queries_for_intent(email_body, intent, top_k=5)
    sub_intent_data = SubIntentClassificationEmail.sub_intents_email.get(intent.upper(), {})
    if not sub_intent_data:
        logging.warning(f"Sub-intent configuration not found for: {intent.upper()}")
        return "No DATA FOR SUB-INTENT"

    prompt_template = create_prompt_template(
        sub_intent_data.get("SYSTEM"),
        sub_intent_data.get("CONTEXT"),
        sub_intent_data.get("DISPLAY"),
        sub_intent_data.get("REMEMBER")
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template, verbose=False)
    result = llm_chain.run({"email_history": email_body, "examples": sub_examples})
    return [[result], sub_examples]


def setup_logger():
    logging.basicConfig(
        filename='email_classification.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger()


def load_gpt_config():
    return {
        "4omini": {
            "OPENAI_API_KEY": "95058a9e99794e4689d179dd726e7eec",
            "OPENAI_DEPLOYMENT_NAME": "vassar-4o-mini",
            "OPENAI_EMBEDDING_MODEL_NAME": "vassar-text-ada002",
            "OPENAI_API_BASE": "https://vassar-openai.openai.azure.com/",
            "MODEL_NAME": "gpt-4o-mini",
            "OPENAI_API_TYPE": "azure",
            "OPENAI_API_VERSION": "2024-02-15-preview",
        }
    }


def initialize_workbook(file_path):
    workbook = openpyxl.load_workbook(file_path)
    return workbook, workbook.active


def classify_intent(row, sheet, llm, Others):
    email_history, user_latest_email, user_latest_email_body = parse_email_data(sheet[f'C{row}'].value)
    examples = fetch_similar_queries(user_latest_email_body, top_k=5)
    email_body = f"{email_history}\n{user_latest_email}"
    expected_intent = sheet[f'D{row}'].value.strip()

    classified_intent = intent_classification(email_body, examples, llm)
    classified_data = json.loads(classified_intent)
    intent_list = classified_data.get("intent", [])
    final_intent, sub_examples = process_intents(intent_list, email_body, sheet, row, llm, Others, classified_data)
    result = "PASS" if final_intent.lower().strip() == expected_intent.lower().strip() else "FAIL"
    sheet[f'L{row}'] = result
    log_result(row, result, expected_intent, final_intent, examples, sub_examples, email_history, user_latest_email)
    return final_intent


def process_intents(intent_list, email_body, sheet, row, llm, Others, classified_data):
    if len(intent_list) == 1:
        return handle_single_intent(intent_list, email_body, sheet, row, llm, Others, classified_data)
    elif len(intent_list) == 2:
        return handle_two_intents(intent_list, email_body, sheet, row, llm, Others, classified_data)
    else:
        return handle_multiple_intents(sheet, row, classified_data)


def handle_single_intent(intent_list, email_body, sheet, row, llm, Others, classified_data):
    intent_data_score = intent_list[0].get("intent") + " - " + intent_list[0].get("similarity_score")
    intent = intent_list[0].get("intent")
    sheet[f'E{row}'] = intent_data_score
    sheet[f'F{row}'] = classified_data.get("bot_likely_response", "")
    sheet[f'G{row}'] = classified_data.get("reason", "")
    if intent not in ["OTHERS", "BANTER"]:
        intent_data, examples = classify_sub_intent(intent, email_body, sheet, row, llm)
        return intent_data, examples
    return intent, ""


def handle_two_intents(intent_list, email_body, sheet, row, llm, Others, classified_data):
    intents = [item.get("intent") for item in intent_list]
    similarity_scores = [float(item.get("similarity_score", 0)) for item in intent_list]
    intent_data_score = []
    for item in intent_list:
        intent_data_score.append(item.get("intent") + " - " + item.get("similarity_score"))
    sheet[f'E{row}'] = ', '.join(intent_data_score)
    if set(intents) == {"DAMAGES", "RETURNS"}:
        return classify_sub_intent("DAMAGES", email_body, sheet, row, llm)
    elif similarity_scores[0] > 0.5 and similarity_scores[1] > 0.5:
        return "OTHERS", ""  ##i must to run subintent code for the both intents
    else:
        max_score_index = similarity_scores.index(max(similarity_scores))
        if intents[max_score_index] not in ["OTHERS", "BANTER"]:
            return classify_sub_intent(intents[max_score_index].strip(), email_body, sheet, row, llm)
    return "OTHERS", ""


def handle_multiple_intents(sheet, row, classified_data):
    sheet[f'K{row}'] = "OTHERS"
    sheet[f'F{row}'] = classified_data.get("bot_likely_response", "")
    sheet[f'G{row}'] = classified_data.get("reason", "")
    return "OTHERS", ""


def classify_sub_intent(intent, email_body, sheet, row, llm):
    classified_sub_intent_and_examples = sub_intent_classification(email_body, intent, llm)
    classified_sub_intent = classified_sub_intent_and_examples[0][0]
    sub_examples = classified_sub_intent_and_examples[1]
    sub_intent_data = json.loads(classified_sub_intent)
    sub_intent_list = sub_intent_data.get("intent", [])
    if len(sub_intent_list) == 1:
        sub_intent = sub_intent_list[0].get("Intent")
        sheet[f'H{row}'] = sub_intent + " - " + sub_intent_list[0].get("similarity_score")
        sheet[f'I{row}'] = sub_intent_data.get("bot_likely_response", "").strip()
        sheet[f'J{row}'] = sub_intent_data.get("reason", "").strip()
        return map_final_intent(intent, sub_intent_list), sub_examples
    elif len(sub_intent_list) > 1:
        excel_assign = []
        for item in sub_intent_list:
            excel_assign.append(item.get("Intent") + " - " + item.get("similarity_score"))
        sheet[f'H{row}'] = ', '.join(excel_assign)
        sheet[f'I{row}'] = sub_intent_data.get("bot_likely_response", "").strip()
        sheet[f'J{row}'] = sub_intent_data.get("reason", "").strip()
        return map_final_intent(intent, sub_intent_list), sub_examples
    return intent, sub_examples


def map_final_intent(main_intent, sub_intent_list):
    intents = [item['Intent'] for item in sub_intent_list]
    scores = [float(item['similarity_score']) for item in sub_intent_list]
    intents_above_threshold = [intents[i] for i in range(len(scores)) if scores[i] > 0.5]
    if len(intents_above_threshold) > 1:
        invalid_sub_intents = [intent for intent in intents_above_threshold if intent in Others.get(main_intent, [])]
        if invalid_sub_intents:
            return "OTHERS"
        return main_intent
    elif len(intents_above_threshold) == 1:
        intent = intents_above_threshold[0]
        if intent == "RETURNING_DAMAGED_PRODUCT":
            return "DAMAGES"
        elif intent not in Others.get(main_intent, []):
            return main_intent
        return "OTHERS"

    return main_intent


def process_email_classifications(file_path, GPT):
    logger = setup_logger()
    gpt_config = load_gpt_config()
    llm = gpt_call(gpt_config[GPT])
    workbook, sheet = initialize_workbook(file_path)

    start_time = datetime.now().strftime("%H:%M:%S")
    for row in range(2, sheet.max_row + 1):
        if sheet[f'A{row}'].value is None:
            break
        sheet[f'K{row}'] = classify_intent(row, sheet, llm, Others)

    workbook.save(file_path)
    end_time = datetime.now().strftime("%H:%M:%S")

    logger.info(f"Start Time: {start_time}")
    logger.info(f"End Time: {end_time}")
    logger.info(f"Updated Excel file saved at: {file_path}")


def log_result(row, result, expected_intent, final_intent, examples, sub_examples, email_history,
               user_latest_email):
    logger = setup_logger()
    if result == "PASS":
        logger.info(f"Row #{row}: PASS - Expected Intent: '{expected_intent}', Classified Intent: '{final_intent}'")
    else:
        logger.error(
            f"Row #{row}: FAIL - Expected Intent: '{expected_intent}', Classified Intent: '{final_intent}'\n"
            f"email_history::{email_history} \n\n user_latest_email::{user_latest_email} \n\n intent_examples:: {examples} \n\n sub_intent_examples::{sub_examples}"
        )


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/email_prompt_test/automation_testing_email.xlsx'
process_email_classifications(file_path, GPT="4omini")
