import json

import openpyxl
from langchain.chains import LLMChain
from langchain.chat_models import AzureChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate
)

IntentCheckerPrompt = {"SYSTEM": """ You are an intent checker bot. Your task is to determine if the email content is trying to switch from CURRENT_INTENT to another intent, based on the email history, bot's latest email, user's latest email and examples. If the user's latest email is continuing in the same CURRENT_INTENT or is responding directly to the Bot’s current email then return "True", Otherwise "False".

    User's latest email is identified in USER_CURRENT_EMAIL.
    Bot's latest email is identified in BOT_CURRENT_EMAIL.
    Email history is identified in EMAIL_HISTORY.
    Prioritise email body over subject, while intent identification.
    Check the email history to see if the user's current email continues the conversation. If it does, return "True".
    If more than one intent is discussed in the USER_CURRENT_EMAIL return "False".

    The intent should be one of the following listed intents below. 
        Intents:
            1. ORDER_STATUS:
                - Description: Only Handles Emails inquiring about the status of an order or ship date or delivery updates.

            2. PRODUCT_AVAILABILITY:
                - Description: Only Handles Emails inquiring about the availability of specific products.

            3. DAMAGES:
                - Description: Only Handles inquiries where the customer is reporting damage to a product that they received or claims regarding damaged products or refused shipments.

            4. RETURNS:
                - Description: Only Handles customer requests to return products.

            5. TRADE_APPLICATION:
                - DESCRIPTION: Only Handles Emails related to inquiries or applications for trade accounts,including requests for setting up a business account. This can also include situations where a customer is inquiring about the status or continuity of a previously existing trade account.

            6. OTHERS:
                - Description: Only Handles Emails that are vague, non-specific, or general in nature. If they are discussing about multiple intents classify as "OTHERS". If the email content does not clearly inquire about a specific product, order, or other clearly defined categories or discussing for multiple intents, it should be classified as "OTHERS". This includes emails like general status updates, follow-up messages, or broad inquiries where the intent is unclear.
     """,
                       "CONTEXT": """
        EMAIL_HISTORY : {email_history}
        BOT_CURRENT_EMAIL : {bot_current_email}
        USER_CURRENT_EMAIL : {user_current_email}
        CURRENT_INTENT : {current_intent}
        """,
                       "DISPLAY": """Ensure that the output is in the following JSON format exactly as shown:
        {{
                "is_intent_changed": "[True/False]"
        }}"""

                       }


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
        print("Invalid GPT version specified")

    # Unpack configuration settings
    OPENAI_API_KEY = config["OPENAI_API_KEY"]
    OPENAI_DEPLOYMENT_NAME = config["OPENAI_DEPLOYMENT_NAME"]
    OPENAI_EMBEDDING_MODEL_NAME = config["OPENAI_EMBEDDING_MODEL_NAME"]
    OPENAI_API_BASE = config["OPENAI_API_BASE"]
    MODEL_NAME = config["MODEL_NAME"]
    OPENAI_API_TYPE = config["OPENAI_API_TYPE"]
    OPENAI_API_VERSION = config["OPENAI_API_VERSION"]

    llm = AzureChatOpenAI(
        deployment_name=OPENAI_DEPLOYMENT_NAME,
        model_name=MODEL_NAME,
        azure_endpoint=OPENAI_API_BASE,
        openai_api_type=OPENAI_API_TYPE,
        openai_api_key=OPENAI_API_KEY,
        openai_api_version=OPENAI_API_VERSION,
        temperature=0.0
    )
    return llm


def intentChecker(email_history, bot_current_email, user_current_email, current_intent, GPT):
    # prompt = f"{IntentCheckerPrompt.get('SYSTEM')}\nCONTEXT:{EmailHistory}\nCURRENT_INTENT:{CURRENT_INTENT}\nBOT_CURRENT_EMAIL:{BOT_CURRENT_EMAIL}\nUSER_CURRENT_EMAIL:{USER_CURRENT_EMAIL}"
    llm = gpt_call(GPT)
    template = ChatPromptTemplate(
        messages=[
            SystemMessagePromptTemplate.from_template(IntentCheckerPrompt.get("SYSTEM")),
            HumanMessagePromptTemplate.from_template(IntentCheckerPrompt.get("CONTEXT")),
            SystemMessagePromptTemplate.from_template(IntentCheckerPrompt.get("DISPLAY")),
        ]
    )
    llm_chain = LLMChain(llm=llm, prompt=template, verbose=True)
    result = llm_chain.run({"email_history": email_history, "bot_current_email": bot_current_email,
         "user_current_email": user_current_email, "current_intent": current_intent})

    return result


file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/intentChecker.xlsx'
workbook = openpyxl.load_workbook(file_path)
sheet = workbook.active
for row in range(2, sheet.max_row + 1):
    if sheet[f'A{row}'].value is None:
        break
    cell_value = sheet[f'C{row}'].value
    if cell_value:
        email_history = cell_value.split("Current_Intent:")[0].strip()
    else:
        email_history = ""
    current_convo = sheet[f'C{row}'].value
    print(current_convo)
    current_intent = current_convo.split("Current_Intent:")[1].split("Bot's_Current_Email:")[0].strip()
    bot_current_email = \
        current_convo.split("Current_Intent:")[1].split("Bot's_Current_Email:")[1].split("User's_Current_Email:")[
            0].strip()
    user_current_email = \
        current_convo.split("Current_Intent:")[1].split("Bot's_Current_Email:")[1].split("User's_Current_Email:")[
            1].strip()
    expected_result = sheet[f'D{row}'].value.strip()
    print(f"email_history:: {email_history}")
    print(f"current_intent: {current_intent}")
    print(f"bot_current_email: {bot_current_email}")
    print(f"user_current_email: {user_current_email}")
    Intent_Change_Status = intentChecker(email_history, bot_current_email, user_current_email, current_intent,
                                         GPT="4omini")
    print(Intent_Change_Status)
    print(json.loads(Intent_Change_Status).get("is_intent_changed", ""))
    sheet[f'E{row}'] = json.loads(Intent_Change_Status).get("is_intent_changed", "")
    if expected_result == json.loads(Intent_Change_Status).get("is_intent_changed", ""):
        sheet[f'F{row}'] = "PASS"
    else:
        sheet[f'F{row}'] = "FAIL"
    print(f"Intent Classification - {expected_result == json.loads(Intent_Change_Status).get("is_intent_changed", "")}")

updated_file_path = '/home/saiprakesh/PycharmProjects/Prompt Testing Using Excel/intentChecker.xlsx'
workbook.save(updated_file_path)

print("Updated File Path Saved Location:", updated_file_path)
