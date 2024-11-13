import json

import openpyxl
from openpyxl import load_workbook
from langchain.chains import LLMChain
from langchain_community.chat_models import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
from ExampleSearchChromaDB import fetch_similar_queries
from ExtractJsonFromStringChat import get_intent_name
from IntentClassificationPromptChat import INTENT_CLASSIFICATION_PROMPT_CHAT
import logging


logging.basicConfig(
    filename='intent_classification_with_reason_chat.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class NoHTTPRequestsFilter(logging.Filter):
    def filter(self, record):
        return 'HTTP' not in record.getMessage()

logger = logging.getLogger()
logger.addFilter(NoHTTPRequestsFilter())

GPT_CONFIG = {
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


def gpt_call(GPT_version):
    config = GPT_CONFIG.get(GPT_version)
    if not config:
        raise ValueError("Invalid GPT version specified")

    return AzureChatOpenAI(
        deployment_name=config["OPENAI_DEPLOYMENT_NAME"],
        model_name=config["MODEL_NAME"],
        azure_endpoint=config["OPENAI_API_BASE"],
        openai_api_type=config["OPENAI_API_TYPE"],
        openai_api_key=config["OPENAI_API_KEY"],
        openai_api_version=config["OPENAI_API_VERSION"],
        temperature=0.0
    )


def classify_intent(llm, chat_history, user_question, examples):
    prompt_template = ChatPromptTemplate(
        messages=[SystemMessagePromptTemplate.from_template(INTENT_CLASSIFICATION_PROMPT_CHAT)],
        input_variables=["CHAT_HISTORY", "question", "examples"]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template, verbose=False)
    result = llm_chain.run(
        {"chat_history": chat_history, "question": user_question, "examples": examples}
    )
    return result


def process_excel(file_path, GPT_version):
    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    llm = gpt_call(GPT_version)

    for row in range(2, sheet.max_row + 1):
        if sheet[f'A{row}'].value is None:
            break
        chat_history, user_latest_question, expected_intent = extract_row_data(sheet, row)
        examples = fetch_similar_queries(user_latest_question, top_k=5)
        classified_intent_raw = classify_intent(llm, chat_history, user_latest_question, examples)
        classified_intent = get_intent_name(classified_intent_raw)
        # print(classified_intent)
        # print(type(classified_intent))
        update_sheet_with_results(sheet, row, expected_intent, classified_intent,chat_history, user_latest_question, examples)
        print_classification_results(row, chat_history, user_latest_question, expected_intent, examples,
                                     classified_intent)

    save_updated_workbook(workbook, file_path)
    print(f"Updated Excel file saved at: {file_path}")

def extract_row_data(sheet, row):
    cell_value = sheet[f'C{row}'].value or ""
    chat_history = cell_value.split("USER_LATEST_CHAT:")[0].strip()
    user_latest_question = cell_value.split("USER_LATEST_CHAT:")[1].partition("Human:")[2].strip()
    expected_intent = sheet[f'D{row}'].value.strip()
    return chat_history, user_latest_question, expected_intent

def update_sheet_with_results(sheet, row, expected_intent, classified_intent, chat_history, user_latest_question, examples):
        if isinstance(classified_intent, list):
            # classified_intent = 'OTHERS'
            result = ", ".join(classified_intent)
            sheet[f'E{row}'] =  result

        else:
            sheet[f'E{row}'], sheet[f'F{row}'] = (
                ('OTHERS', "PASS") if classified_intent == 'Banter' and expected_intent.lower() == 'others'
                else (classified_intent, "PASS" if expected_intent.lower() == classified_intent.lower() else "FAIL")
            )
        if sheet[f'F{row}'] == "FAIL":
            logger.error(
                f"Failed Case #{row} :: Expected intent :: '{expected_intent}', but got :: '{classified_intent}'."
                f"\nChat History:: {chat_history}\nUser Latest Chat :: {user_latest_question}\nExamples:: {examples}\n"
            )


def print_classification_results(row, chat_history, user_latest_question, expected_intent, examples, classified_intent):
    if not isinstance(classified_intent, list):
        print(f"{row-1} : Classified Intent - {expected_intent.lower() == classified_intent.lower()}")
    else:
        print(f"{row - 1} : expected Intent - {expected_intent}, but classified Intents {classified_intent}")
    print("chat_history:", chat_history)
    print("user_latest_question:", user_latest_question)
    print("expected_intent:", expected_intent)
    print("examples:", examples)


def save_updated_workbook(workbook, file_path):
    workbook.save(file_path)


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/automation_testing_chat.xlsx'
process_excel(file_path, GPT_version="4omini")


Rules_Followed = """
----Intents Classified = Single - Actual Intent = Intent Classified----
----
Intents Classified = TWO
1. Major Intent + Others = Major Intent,
2. Major Intent + Major Intent = OTHERS [if DAMAGES + RETURNS = DAMAGES]
----
----Intents Classified > TWO - Actual Intent = OTHERS
"""
