import os
from openai import OpenAI, APIConnectionError
from flask import current_app
from ..models import Transaction, Category


def is_ai_configured():
    """Check if the necessary AI configuration is present."""
    config = current_app.config
    return all([config.get("OPENAI_API_BASE"), config.get("OPENAI_API_KEY"), config.get("OPENAI_MODEL_NAME")])


def get_category_suggestions(transactions, all_categories):
    """
    Given a list of transactions, get category suggestions from the LLM.
    Returns a list of tuples: (transaction_id, suggested_category_name, reason)
    Returns an empty list and an error message if it fails.
    """
    if not is_ai_configured():
        return [], "AI features are not configured in your .env file."

    if not transactions:
        return [], None

    if not all_categories:
        return [], "No categories exist in the database. Please create some first."

    try:
        client = OpenAI(
            base_url=current_app.config["OPENAI_API_BASE"],
            api_key=current_app.config["OPENAI_API_KEY"],
        )

        # --- Prepare the Prompt ---
        # Create a simple, numbered list of all available categories
        category_list_str = "\n".join(
            [f"{i + 1}. {c.name} (in group: {c.group})" for i, c in enumerate(all_categories)])

        # Create the list of transactions to categorize
        transaction_list_str = "\n".join([f"ID {t.id}: {t.description_raw}" for t in transactions])

        system_prompt = f"""
You are an expert financial assistant. Your task is to categorize bank transactions based on their description.
You must respond with ONLY a valid JSON object. Do not include any other text or explanations.
The JSON object should have a single key "suggestions", which is an array of objects.
Each object in the array must have three keys: "id" (the integer transaction ID), "category_name" (the suggested category name), and "reason" (a brief, one-sentence explanation).

Choose a category name from this exact list:
{category_list_str}
"""
        user_prompt = f"""
Here are the transactions to categorize:
{transaction_list_str}
"""
        # --- Make the API Call ---
        response = client.chat.completions.create(
            model=current_app.config["OPENAI_MODEL_NAME"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )

        # --- Parse the Response ---
        # The response content should be a JSON string, which we need to parse.
        import json
        result = json.loads(response.choices[0].message.content)
        return result.get("suggestions", []), None

    except APIConnectionError:
        return [], "Could not connect to the AI endpoint. Please check the URL and ensure the service is running."
    except Exception as e:
        # Catch any other errors (e.g., malformed JSON, other API issues)
        return [], f"An unexpected error occurred: {str(e)}"