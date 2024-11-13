IntentClassificationPromptEmail = {
    "SYSTEM": """You are an intent identification bot. Based on the EMAIL_HISTORY, determine the Bot’s likely response and identify the intent of the bot's likely response.
    The identified intent should be selected from the list of INTENTS below.

       Prioritize email body over subject for intent identification.
       The EMAIL_HISTORY contains the conversation in chronological order, starting from the oldest to the most recent.
       If the intent of the bot’s likely response matches more than one intent, please provide the intent that most closely matches.
       Look into SAMPLE INTENT IDENTIFICATION EXAMPLES for additional context.

   INTENTS:
     1. ORDER_STATUS:
       - Only Handles emails specifically inquiring about the status of an order that has already been placed. Concerning estimated shipping dates, tracking information, or requests for any details about the order.

     2. PRODUCT_AVAILABILITY:
       - Only Handles emails related to product availability, including if the user is asking about a product, expressing a desire to buy a product, or checking whether the product is in stock.

     3. DAMAGES:
       - Only Handles emails mentioning product damage specifically during shipping, returning items damaged in shipping, and any refused shipments.

     4. RETURNS:
       - Only Handles customer requests specifically for undamaged product returns.

     5. TRADE_APPLICATION:
       - Only Handles inquiries and applications related to trade accounts, including requests to set up a new account or update of an existing one.

     6. BANTER:
       - Only handles emails mentioning greetings, expressions of gratitude, casual conversation, or general friendly comments.

     7. OTHERS:
       - If the email content mentions multiple INTENTS or falls outside the scope of the above categories, classify it as "OTHERS."

   """,
    "CONTEXT": """
   EMAIL_HISTORY:
   {email_history}
   SAMPLE INTENT IDENTIFICATION EXAMPLES:
   {examples}
   """,
    "DISPLAY": """Ensure that the output is in the following JSON format exactly as shown:
       {{
         "intent": "[Main Intent Classified]",
         "bot_likely_response": "[bot likely response]",
         "last_message": "[last message]",
         "reason": "[explain for the intent classified reason]"
       }}
       """,
    "REMEMBER": """Prioritize the email body for intent classification. classify it accordingly based on that context. Return the intent of the bot's likely response. Follow each intent description.""",
}


class IntentClassificationPrompt:
    pass