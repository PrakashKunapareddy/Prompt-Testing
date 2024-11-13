from datetime import datetime
import openpyxl
import json
import logging
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain_community.chat_models import AzureChatOpenAI
import SubIntentClassificationEmail
from ExampleSearchChromaDB import fetch_similar_queries, fetch_similar_queries_for_intent
from IntentClassificationPromptEmail import IntentClassificationPromptEmail

logging.basicConfig(
    filename='intent_classification_with_reason.log',
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


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
        azure_endpoint=config["OPENAI_API_BASE"],
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
    examples = fetch_similar_queries_for_intent(email_body, intent, top_k=10)
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
    return llm_chain.run({"email_history": email_body, "examples": examples})


def process_email_classifications(file_path, GPT):
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

        examples = fetch_similar_queries(user_latest_email_body, top_k=10)
        email_body = f"{email_history}\n{user_latest_email}"
        expected_intent = sheet[f'D{row}'].value.strip()

        classified_intent = intent_classification(email_body, examples, GPT)
        classified_data = json.loads(classified_intent)
        intent = classified_data.get("intent", "")

        if intent.lower() not in ["others", "banter"]:
            classified_sub_intent = sub_intent_classification(email_body, intent, GPT)
            sub_intent_data =  json.loads(classified_sub_intent)
            print(type(sub_intent_data))
            print(sub_intent_data)
            sub_intent = sub_intent_data['sub_intent']
            print(type(sub_intent))
        else:
            sub_intent = ""

        if (intent == "ORDER_STATUS" and sub_intent not in []) or \
                (intent == "RETURNS" and sub_intent != "RETURNS_PROCESSING"):
            final_intent = "OTHERS"
        else:
            final_intent = intent

        sheet[f'E{row}'] = final_intent

        if expected_intent.lower() == classified_data.get("intent", "").lower():
            sheet[f'F{row}'] = "PASS"
        else:
            sheet[f'F{row}'] = "FAIL"
            logging.getLogger().addFilter(NoHTTPRequestsFilter())
            logging.error(
                f"Failed Case #{row} :: Expected intent :: '{expected_intent}', but got :: '{classified_intent}'."
                f"\nEmail History:: {email_history}\nUser Latest Email :: {user_latest_email_body}\nExamples:: {examples}\n"
            )

    workbook.save(file_path)
    formatted_time2 = datetime.now().strftime("%H:%M:%S")
    print("Start Time", formatted_time1)
    print("END Time", formatted_time2)
    print(f"Updated Excel file saved at: {file_path}")


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/automation_testing_email.xlsx'
process_email_classifications(file_path, GPT="4omini")
