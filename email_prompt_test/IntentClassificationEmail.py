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


# Helper functions
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


def log_result(row, result, expected_intent, final_intent, additional_info=""):
    if result == "PASS":
        logger.info(f"Row #{row}: PASS - Expected Intent: '{expected_intent}', Classified Intent: '{final_intent}'")
    else:
        logger.error(
            f"Row #{row}: FAIL - Expected Intent: '{expected_intent}', Classified Intent: '{final_intent}'. {additional_info}"
        )


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
    return [result, sub_examples]


def process_email_classifications(file_path, GPT):
    logging.basicConfig(
        filename='email_classification.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    global logger
    logger = logging.getLogger()

    gpt_config = {
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
    llm = gpt_call(gpt_config[GPT])

    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    start_time = datetime.now()
    formatted_time1 = start_time.strftime("%H:%M:%S")

    for row in range(2, sheet.max_row + 1):
        if sheet[f'A{row}'].value is None:
            break

        email_history, user_latest_email, user_latest_email_body = parse_email_data(sheet[f'C{row}'].value)
        examples = fetch_similar_queries(user_latest_email_body, top_k=5)
        sub_examples, classified_sub_intent = "", ""
        email_body = f"{email_history}\n{user_latest_email}"
        expected_intent = sheet[f'D{row}'].value.strip()

        classified_intent = intent_classification(email_body, examples, llm)
        classified_data = json.loads(classified_intent)
        intent = classified_data.get("intent", "")
        sheet[f'E{row}'] = intent
        sheet[f'F{row}'] = classified_data.get("bot_likely_response", "")
        sheet[f'G{row}'] = classified_data.get("reason", "")

        if intent not in ["OTHERS", "BANTER"]:
            classified_sub_intent_and_examples = sub_intent_classification(email_body, intent, llm)
            classified_sub_intent = classified_sub_intent_and_examples[0]
            sub_examples = classified_sub_intent_and_examples[1]
            sub_intent_data = json.loads(classified_sub_intent)
            sub_intent = sub_intent_data.get("sub_intent").strip()
            sub_intent_bot_likely_res = sub_intent_data.get("bot_likely_response").strip()
            sheet[f'H{row}'] = sub_intent
            sheet[f'I{row}'] = sub_intent_bot_likely_res
            sheet[f'J{row}'] = sub_intent_data.get("reason").strip()
            list_intents = Others.get(intent, [])
            final_intent = "OTHERS" if sub_intent in list_intents else intent
            sheet[f'K{row}'] = final_intent
        else:
            final_intent = intent
            sheet[f'K{row}'] = final_intent

        result = "PASS" if expected_intent.lower().strip() == final_intent.lower().strip() else "FAIL"
        sheet[f'L{row}'] = result
        log_result(row, result, expected_intent, final_intent)

    workbook.save(file_path)
    formatted_time2 = datetime.now().strftime("%H:%M:%S")
    logger.info(f"Start Time: {formatted_time1}")
    logger.info(f"End Time: {formatted_time2}")
    logger.info(f"Updated Excel file saved at: {file_path}")


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/email_prompt_test/automation_testing_email.xlsx'
process_email_classifications(file_path, GPT="4omini")
