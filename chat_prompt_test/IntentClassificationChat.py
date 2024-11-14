import logging
import openpyxl
from langchain.chains import LLMChain
from langchain_community.chat_models import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
from ExampleSearchChromaDB import fetch_similar_queries, fetch_similar_queries_for_intent
from ExtractJsonFromStringChat import get_intent_name
from IntentClassificationPromptChat import INTENT_CLASSIFICATION_PROMPT_CHAT
from SubIntentClassificationChat import sub_intents_chat
from otherSubIntents import Others

# Set up logging
logging.basicConfig(
    filename='chat_classification.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()


class NoHTTPRequestsFilter(logging.Filter):
    def filter(self, record):
        return 'HTTP' not in record.getMessage()

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
        input_variables=["chat_history", "question", "examples"]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template)
    return llm_chain.run({
        "chat_history": chat_history,
        "question": user_question,
        "examples": examples
    })


def classify_sub_intent(llm, chat_history, user_question, intent):
    examples = fetch_similar_queries_for_intent(user_question, intent, top_k=5)
    template = sub_intents_chat.get(intent)
    if not template:
        raise ValueError(f"No template found for intent: {intent}")
    prompt_template = ChatPromptTemplate(
        messages=[SystemMessagePromptTemplate.from_template(template)],
        input_variables=["user_query", "chat_history", "subintent_examples"]
    )
    llm_chain = LLMChain(llm=llm, prompt=prompt_template)
    return llm_chain.run({
        "question": user_question,
        "chat_history": chat_history,
        "examples": examples
    })


def process_excel(file_path, GPT_version):
    workbook = openpyxl.load_workbook(file_path)
    sheet = workbook.active
    llm = gpt_call(GPT_version)

    for row in range(2, sheet.max_row + 1):
        if not sheet[f'A{row}'].value:  # Stop if row is empty
            break
        chat_history, user_latest_question, expected_intent = extract_row_data(sheet, row)
        examples = fetch_similar_queries(user_latest_question, top_k=5)
        classified_intent_raw = classify_intent(llm, chat_history, user_latest_question, examples)
        classified_intent = get_intent_name(classified_intent_raw)
        update_sheet(llm, sheet, row, expected_intent, classified_intent, chat_history, user_latest_question, examples)

    save_workbook(workbook, file_path)
    print(f"Updated Excel file saved at: {file_path}")


def extract_row_data(sheet, row):
    cell_value = sheet[f'C{row}'].value or ""
    chat_history, _, user_latest_question = cell_value.partition("USER_LATEST_CHAT:")
    user_latest_question = user_latest_question.partition("Human:")[2].strip()
    expected_intent = sheet[f'D{row}'].value.strip() if sheet[f'D{row}'].value else "UNKNOWN"
    return chat_history.strip(), user_latest_question, expected_intent


def update_sheet(llm, sheet, row, expected_intent, classified_intent, chat_history, user_latest_question, examples):
    def update_sub_intent_and_final_intent(intent):
        classified_sub_intent = classify_sub_intent(llm, chat_history, user_latest_question, intent)
        sheet[f'F{row}'] = classified_sub_intent
        list_intents = [intent.strip() for intent in Others.get(intent, [])]
        final_intent = "OTHERS" if classified_sub_intent in list_intents else intent
        sheet[f'G{row}'] = final_intent

    if isinstance(classified_intent, list):
        classified_intent_str = ", ".join(classified_intent)
        if set(classified_intent) == {"DAMAGES", "RETURNS"}:
            sheet[f'E{row}'] = "DAMAGES"
            update_sub_intent_and_final_intent("DAMAGES")
        else:
            sheet[f'E{row}'] = classified_intent_str
    else:
        classified_intent = classified_intent.upper()
        if classified_intent == "BANTER" and expected_intent.upper() == "OTHERS":
            sheet[f'E{row}'] = "OTHERS"
            sheet[f'G{row}'] = "OTHERS"
        elif classified_intent not in ["OTHERS", "BANTER"]:
            sheet[f'E{row}'] = classified_intent
            update_sub_intent_and_final_intent(classified_intent)

    if sheet[f'H{row}'].value == "FAIL":
        log_failure(row, expected_intent, classified_intent, chat_history, user_latest_question, examples)


def log_failure(row, expected_intent, classified_intent, chat_history, user_latest_question, examples):
    logger.error(
        f"Failed Case #{row} :: Expected intent: '{expected_intent}', but got: '{classified_intent}'."
        f"\nChat History: {chat_history}\nUser Latest Chat: {user_latest_question}\nExamples: {examples}\n"
    )


def save_workbook(workbook, file_path):
    workbook.save(file_path)


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/chat_prompt_test/automation_testing_chat.xlsx'
process_excel(file_path, GPT_version="4omini")


