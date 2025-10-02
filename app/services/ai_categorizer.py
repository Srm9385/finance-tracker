# srm9385/finance-tracker/finance-tracker-b6479a0b9b4b550a18703e80c76c724f6985583c/app/services/ai_categorizer.py
import os
from openai import OpenAI, APIConnectionError
from flask import current_app
from ..models import Transaction, Category
import json


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

        category_list_str = "\n".join([f'- "{c.name}"' for c in all_categories])
        transaction_list_str = "\n".join(
            [f"ID {t.id}: {t.description_raw}" for t in transactions]
        )

        # --- START MODIFICATION ---
        system_prompt = f"""
You are an expert financial assistant. Your task is to categorize bank transactions based on their description.
You must respond with ONLY a valid JSON object. Do not include any other text, explanations, or markdown.
Your entire response must be a single JSON object.

The JSON object should have a single key "suggestions", which is an array of objects.
Each object in the array must have three keys: "id" (the integer transaction ID), "category_name" (the suggested category name), and "reason" (a brief, one-sentence explanation).

For the "category_name", you must choose one of the following exact, case-sensitive category names. Do not add, modify, or infer any other category.

Available Categories:
{category_list_str}
"""
        # --- END MODIFICATION ---
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
            max_tokens=2048,
        )

        raw_content = response.choices[0].message.content
        start_index = raw_content.find('{')
        end_index = raw_content.rfind('}') + 1

        if start_index == -1 or end_index == 0:
            raise ValueError("No valid JSON object found in the LLM response.")

        json_string = raw_content[start_index:end_index]
        result = json.loads(json_string)

        return result.get("suggestions", []), None

    except APIConnectionError:
        return [], "Could not connect to the AI endpoint. Please check the URL and ensure the service is running."
    except Exception as e:
        return [], f"An unexpected error occurred: {str(e)}"