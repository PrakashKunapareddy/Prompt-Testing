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
EMAIL_CONTEXT = [
    {
        "EMAIL_HISTORY": "User: Subject: Product Availability,Body:Is the Woven Leather Dining Chair available?\nBot: Yes, the Woven Leather Dining Chair is available.",
        "CURRENT_INTENT": "PRODUCT_AVAILABILITY",
        "BOT_CURRENT_EMAIL": "It's in stock.",
        "USER_CURRENT_EMAIL": "Subject: Product Availability,Body: How many are available in stock?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User:Subject: Product Availability,Body: Can I buy the Driskill Arm Chair?\nBot: Yes, the Driskill Arm Chair is available.",
        "CURRENT_INTENT": "PRODUCT_AVAILABILITY",
        "BOT_CURRENT_EMAIL": "It's available for purchase.",
        "USER_CURRENT_EMAIL": "Subject: Product Availability,Body: Can I confirm the availability of 2 more units?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User:Subject: Product Availability,Body: Is the product with SKU ID 136-112237 available?\nBot: Yes, the product with SKU ID 136-112237 is available.",
        "CURRENT_INTENT": "PRODUCT_AVAILABILITY",
        "BOT_CURRENT_EMAIL": "It's currently in stock.",
        "USER_CURRENT_EMAIL": "Subject: Product Availability,Body: What is the return policy on this product?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User: Subject: Product Availability,Body: Do you have the Amaranthus Stool available?\nBot: Yes, the Amaranthus Stool is in stock.",
        "CURRENT_INTENT": "PRODUCT_AVAILABILITY",
        "BOT_CURRENT_EMAIL": "It's available.",
        "USER_CURRENT_EMAIL": "Subject: Product Availability,Body: Can I order more than one unit at a time?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User: Subject: Product Availability,Body: Is the product with SKU ID 138-111298 available?\nBot: Yes, the product with SKU ID 138-111298 is in stock.",
        "CURRENT_INTENT": "PRODUCT_AVAILABILITY",
        "BOT_CURRENT_EMAIL": "It's available now.",
        "USER_CURRENT_EMAIL": "Subject: Product Availability,Body: Can I cancel this order if I change my mind later?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User:Subject: Return my Order,Body: I want to return a product\nBot: Can you please provide the Order ID?\nUser: Subject: Return my Order,Body: #295938",
        "CURRENT_INTENT": "RETURNS",
        "BOT_CURRENT_EMAIL": "The product is not eligible for return because it is beyond the return period.",
        "USER_CURRENT_EMAIL": "Subject: Return my Order,Body:Okay, thank you.",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User:Subject: Return my Order,Body: I need to return an item.\nBot: Could you provide your order ID?\nUser:Subject: Return my Order,Body: I do not remember my order ID.",
        "CURRENT_INTENT": "RETURNS",
        "BOT_CURRENT_EMAIL": "Sorry, I can't proceed without it. Please provide the Order ID.",
        "USER_CURRENT_EMAIL": "Subject: Return my Order,Body:Can I give you my email address instead?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User:Subject: Return my Order,Body: I want to return a product\nBot: Can you please provide the Order ID?\nUser: Subject: Return my Order,Body: #295938\nBot: The product is not eligible for return because it is beyond the return period.",
        "CURRENT_INTENT": "RETURNS",
        "BOT_CURRENT_EMAIL": "The product is not eligible for return because it is beyond the return period.",
        "USER_CURRENT_EMAIL": "Subject: Return my Order,Body:Do you have any new products on sale?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User: Subject: Return my Order,Body:I would like to return a product.\nBot: Please provide the order ID.\nUser: Subject: Return my Order,Body: Order ID #298859",
        "CURRENT_INTENT": "RETURNS",
        "BOT_CURRENT_EMAIL": "Your return request is being processed.",
        "USER_CURRENT_EMAIL": "Subject: Return my Order,Body: Can you tell me when my order will be delivered?",
        "Expected_Flag": "FALSE"
    },
    {
        "EMAIL_HISTORY": "User: Subject: Return my Order,Body:I need to return my Getty Table Lamp.\nBot: Could you provide the order ID?\nUser: Subject: Return my Order,Body: #295932",
        "CURRENT_INTENT": "RETURNS",
        "BOT_CURRENT_EMAIL": "The return request is processed.",
        "USER_CURRENT_EMAIL": "Subject: Return my Order,Body: Is the Getty Table Lamp still under warranty?",
        "Expected_Flag": "FALSE"
    }
]


def gpt_call(GPT):
    # Define configuration settings for different GPT versions
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

    # Fetch configuration based on GPT version
    config = gpt_config.get(GPT)
    if not config:
        raise ValueError("Invalid GPT version specified")

    # Unpack configuration settings
    OPENAI_API_KEY = config["OPENAI_API_KEY"]
    OPENAI_DEPLOYMENT_NAME = config["OPENAI_DEPLOYMENT_NAME"]
    OPENAI_EMBEDDING_MODEL_NAME = config["OPENAI_EMBEDDING_MODEL_NAME"]
    OPENAI_API_BASE = config["OPENAI_API_BASE"]
    MODEL_NAME = config["MODEL_NAME"]
    OPENAI_API_TYPE = config["OPENAI_API_TYPE"]
    OPENAI_API_VERSION = config["OPENAI_API_VERSION"]

    # Initialize the LLM
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


def intentChecker(EmailHistory, CURRENT_INTENT, BOT_CURRENT_EMAIL, USER_CURRENT_EMAIL, Expected_Flag, GPT):
    # prompt = f"{IntentCheckerPrompt.get('SYSTEM')}\nCONTEXT:{EmailHistory}\nCURRENT_INTENT:{CURRENT_INTENT}\nBOT_CURRENT_EMAIL:{BOT_CURRENT_EMAIL}\nUSER_CURRENT_EMAIL:{USER_CURRENT_EMAIL}"

    llm = gpt_call(GPT)
    template = ChatPromptTemplate(
        messages=[
            SystemMessagePromptTemplate.from_template(IntentCheckerPrompt.get("SYSTEM_PROMPT")),
            HumanMessagePromptTemplate.from_template(IntentCheckerPrompt.get("CONTEXT")),
            SystemMessagePromptTemplate.from_template(IntentCheckerPrompt.get("DISPLAY")),
            SystemMessagePromptTemplate.from_template(IntentCheckerPrompt.get("REMEMBER"))
        ]
    )
    llm_chain = LLMChain(llm=llm, prompt=template, verbose=True)
    result = llm_chain.run(
        {"EMAIL_HISTORY": EmailHistory, "BOT_CURRENT_EMAIL": BOT_CURRENT_EMAIL,
         "USER_CURRENT_EMAIL": USER_CURRENT_EMAIL,"CURRENT_INTENT": CURRENT_INTENT})

    if result == Expected_Flag:
        print(f"Passed:{result}")
    else:
        print(f"Failed:{result} but expected {Expected_Flag}")


for item in EMAIL_CONTEXT:
    intentChecker(item['EMAIL_HISTORY'], item['CURRENT_INTENT'], item['BOT_CURRENT_EMAIL'],
                  item['USER_CURRENT_EMAIL'],
                  item['Expected_Flag'], "4omini")
