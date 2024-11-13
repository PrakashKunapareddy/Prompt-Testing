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


def gpt_call(GPT):
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
    config = gpt_config.get(GPT)
    if not config:
        raise ValueError("Invalid GPT version specified")

    llm = AzureChatOpenAI(
        deployment_name=config["OPENAI_DEPLOYMENT_NAME"],
        model_name=config["MODEL_NAME"],
        openai_api_base=config["OPENAI_API_BASE"],
        openai_api_type=config["OPENAI_API_TYPE"],
        openai_api_key=config["OPENAI_API_KEY"],
        openai_api_version=config["OPENAI_API_VERSION"],
        temperature=0.0
    )
    return llm


def intent_classification(email_body, examples, GPT):
    llm = gpt_call(GPT)
    prompt_template = ChatPromptTemplate(
        messages=[
            SystemMessagePromptTemplate.from_template(IntentClassificationPromptEmail.get("SYSTEM")),
            HumanMessagePromptTemplate.from_template(IntentClassificationPromptEmail.get("CONTEXT")),
            SystemMessagePromptTemplate.from_template(IntentClassificationPromptEmail.get("DISPLAY")),
            SystemMessagePromptTemplate.from_template(IntentClassificationPromptEmail.get("REMEMBER"))
        ]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template, verbose=False)
    return llm_chain.run({"email_history": email_body, "examples": examples})


def sub_intent_classification(email_body, intent, GPT):
    llm = gpt_call(GPT)
    sub_examples = fetch_similar_queries_for_intent(email_body, intent, top_k=5)
    sub_intent_data = SubIntentClassificationEmail.sub_intents_email.get(intent.upper(), {})
    if not sub_intent_data:
        logging.warning(f"Sub-intent configuration not found for: {intent.upper()}")
        return "No DATA FOR SUB-INTENT"

    prompt_template = ChatPromptTemplate(
        messages=[
            SystemMessagePromptTemplate.from_template(sub_intent_data.get("SYSTEM")),
            HumanMessagePromptTemplate.from_template(sub_intent_data.get("CONTEXT")),
            SystemMessagePromptTemplate.from_template(sub_intent_data.get("DISPLAY")),
            SystemMessagePromptTemplate.from_template(sub_intent_data.get("REMEMBER"))
        ]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template, verbose=False)
    result = llm_chain.run({"email_history": email_body, "examples": sub_examples})
    return [result,sub_examples]


import logging
from datetime import datetime
import json
import openpyxl


def process_email_classifications(file_path, GPT):
    logging.basicConfig(
        filename='email_classification.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger()

    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    formatted_time1 = datetime.now().strftime("%H:%M:%S")

    for row in range(2, sheet.max_row + 1):
        if sheet[f'A{row}'].value is None:
            break

        email_history = (sheet[f'C{row}'].value or "").split("USER_LATEST_EMAIL:")[0].strip()
        user_latest_email = (sheet[f'C{row}'].value or "").split("USER_LATEST_EMAIL:")[1].strip() if sheet[
            f'C{row}'].value else ""
        user_latest_email_body = user_latest_email.split("Body:")[1] if "Body:" in user_latest_email else ""

        examples = fetch_similar_queries(user_latest_email_body, top_k=5)
        sub_examples = ""
        classified_sub_intent = ""
        email_body = f"{email_history}\n{user_latest_email}"
        expected_intent = sheet[f'D{row}'].value.strip()

        classified_intent = intent_classification(email_body, examples, GPT)
        classified_data = json.loads(classified_intent)
        intent = classified_data.get("intent", "")
        if intent not in ["OTHERS", "BANTER"]:
            classified_sub_intent_and_examples = sub_intent_classification(email_body, intent, GPT)
            classified_sub_intent = classified_sub_intent_and_examples[0]
            sub_examples = classified_sub_intent_and_examples[1]
            sub_intent_data = json.loads(classified_sub_intent)
            sub_intent = sub_intent_data.get("sub_intent").strip()

            list_intents = [intent.strip() for intent in Others.get(intent, [])]
            if sub_intent in list_intents:
                final_intent = "OTHERS"
            else:
                final_intent = intent
            sheet[f'E{row}'] = final_intent
        else:
            final_intent = intent
            sheet[f'E{row}'] = final_intent

        if expected_intent.lower().strip() == final_intent.lower().strip():
            sheet[f'F{row}'] = "PASS"
            logger.info(f"Row #{row}: PASS - Expected Intent: '{expected_intent}', Classified Intent: '{final_intent}'")
        else:
            sheet[f'F{row}'] = "FAIL"
            logger.error(
                f"Row #{row}: FAIL - Expected Intent: '{expected_intent}', Classified Intent: '{final_intent}'."
                f"\nEmail History: {email_history}\nUser Latest Email: {user_latest_email_body}\n\nIntent_Data:{classified_intent}"
                f"Intent Examples: {examples}\nSub Intent Data: {classified_sub_intent}\nSub Intent Examples: {sub_examples}"
            )

    workbook.save(file_path)
    formatted_time2 = datetime.now().strftime("%H:%M:%S")
    logger.info(f"Start Time: {formatted_time1}")
    logger.info(f"End Time: {formatted_time2}")
    logger.info(f"Updated Excel file saved at: {file_path}")



file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/email_prompt_test/automation_testing_email.xlsx'
process_email_classifications(file_path, GPT="4omini")