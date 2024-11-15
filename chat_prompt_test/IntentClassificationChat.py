import json
import logging
import openpyxl
from langchain.chains import LLMChain
from langchain_community.chat_models import AzureChatOpenAI
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate
from ExampleSearchChromaDB import fetch_similar_queries, fetch_similar_queries_for_intent
from ExtractJsonFromStringChat import process_classifications
from IntentClassificationPromptChat import INTENT_CLASSIFICATION_PROMPT_CHAT
from SubIntentClassificationChat import sub_intents_chat
from otherSubIntents import Others

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
        classified_intent = process_classifications(input_string=classified_intent_raw,sub_intent_string="")[0]
        print(type(classified_intent))
        print(classified_intent)
        print("=" * 50)
        update_sheet(llm, sheet, row, expected_intent, classified_intent, chat_history, user_latest_question)

    save_workbook(workbook, file_path)
    print(f"Updated Excel file saved at: {file_path}")


def extract_row_data(sheet, row):
    cell_value = sheet[f'C{row}'].value or ""
    chat_history, _, user_latest_question = cell_value.partition("USER_LATEST_CHAT:")
    user_latest_question = user_latest_question.partition("Human:")[2].strip()
    expected_intent = sheet[f'D{row}'].value.strip() if sheet[f'D{row}'].value else "UNKNOWN"
    return chat_history.strip(), user_latest_question, expected_intent


def update_sheet(llm, sheet, row, expected_intent, classified_intent, chat_history, user_latest_question):
    def update_sub_intent_and_final_intent(intent):
        classified_sub_intent_raw = classify_sub_intent(llm, chat_history, user_latest_question, intent)
        print(classified_sub_intent_raw)
        print(type(classified_sub_intent_raw))
        classified_sub_intent_json = process_classifications(input_string= "",sub_intent_string=classified_sub_intent_raw)[1]
        print(classified_sub_intent_json)
        print(type(classified_sub_intent_json))
        classified_sub_intent = classified_sub_intent_json.get("sub_intent", "")
        sheet[f'H{row}'] = classified_sub_intent
        sheet[f'I{row}'] = classified_sub_intent_json.get("bot_likely_response", "")
        sheet[f'J{row}'] = classified_sub_intent_json.get("reason", "")
        list_intents = [intent.strip() for intent in Others.get(intent, [])]
        final_intent = "OTHERS" if classified_sub_intent in list_intents else intent
        sheet[f'K{row}'] = final_intent

    if len(classified_intent.get("classified_intents")) > 1:
        for item in classified_intent.get("classified_intents"):
            intents_only = item.get("intent_name")
            if set(intents_only) == {"DAMAGES", "RETURNS"}:
                sheet[f'E{row}'] = "DAMAGES"
                sheet[f'F{row}'] = classified_intent.get("bot_likely_response", "")
                sheet[f'G{row}'] = classified_intent.get("reason", "")
                update_sub_intent_and_final_intent("DAMAGES")
            else:
                sheet[f'E{row}'] = "OTHERS"
                sheet[f'F{row}'] = classified_intent.get("bot_likely_response", "")
                sheet[f'G{row}'] = classified_intent.get("reason", "")
                sheet[f'K{row}'] = "OTHERS"
    else:
        if classified_intent.get("classified_intents")[0].get("intent_name") == "BANTER" and expected_intent.upper() == "OTHERS":
            sheet[f'E{row}'] = "OTHERS"
            sheet[f'F{row}'] = classified_intent.get("bot_likely_response", "")
            sheet[f'G{row}'] = classified_intent.get("reason", "")
            sheet[f'K{row}'] = "OTHERS"
        elif classified_intent.get("classified_intents")[0].get("intent_name") not in ["OTHERS", "BANTER"]:
            sheet[f'E{row}'] = classified_intent.get("classified_intents")[0].get("intent_name")
            sheet[f'F{row}'] = classified_intent.get("bot_likely_response", "")
            sheet[f'G{row}'] = classified_intent.get("reason", "")
            update_sub_intent_and_final_intent(classified_intent.get("classified_intents")[0].get("intent_name"))
        else:
            sheet[f'E{row}'] = "OTHERS"
            sheet[f'F{row}'] = classified_intent.get("bot_likely_response", "")
            sheet[f'G{row}'] = classified_intent.get("reason", "")
            sheet[f'K{row}'] = "OTHERS"
    expected = expected_intent.strip().upper()
    final = sheet[f'K{row}'].value.strip().upper() if sheet[f'K{row}'].value else ""
    sheet[f'L{row}'] = "PASS" if expected == final else "FAIL"


def save_workbook(workbook, file_path):
    workbook.save(file_path)


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/chat_prompt_test/automation_testing_chat.xlsx'
process_excel(file_path, GPT_version="4omini")



# My Intent json output:
# {
#   "classified_intents": [
#     {
#       "intent_name": "OTHERS",
#       "similarity_score": 0.9
#     }
#   ],
#   "bot_likely_response": "Thank you for providing your order number. Since you received a different product, we can initiate a replacement for you. Please hold on while I process this request.",
#   "reason": "The user is requesting a replacement for a product that was received incorrectly, which falls under a general request for assistance rather than a specific intent like returns or damages."
# }