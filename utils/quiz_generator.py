import json
import time
import random
from typing import Dict, Any, List

# --- Firebase Global Variables (Provided by Canvas Environment) ---
# NOTE: These variables are typically used in client-side JS/React/Angular apps
# For a backend utility like this, they serve mainly to acknowledge the environment.
# They are not used in the core API call logic below but are included for context.
try:
    __app_id = __app_id # Provided by the execution environment
    __firebase_config = __firebase_config # Provided by the execution environment
    __initial_auth_token = __initial_auth_token # Provided by the execution environment
except NameError:
    # Default values for local testing outside the Canvas environment
    __app_id = 'default-quiz-app'
    __firebase_config = '{}'
    __initial_auth_token = 'none'

# --- API Configuration ---
# API key is implicitly handled by the execution environment when fetching.
API_KEY = ""
MODEL_NAME = "gemini-2.5-flash-preview-09-2025"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"

def create_api_payload(system_prompt: str, user_query: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates the JSON payload for the Gemini API call with structured output.
    """
    return {
        "contents": [{
            "parts": [{"text": user_query}]
        }],
        "systemInstruction": {
            "parts": [{"text": system_prompt}]
        },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema
        },
        "tools": [{"google_search": {}}] # Use Google Search for grounding
    }

def get_reflection_quiz_schema() -> Dict[str, Any]:
    """
    Defines the strict JSON schema for the reflection quiz structure.
    """
    return {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING", "description": "The title of the reflection quiz."},
            "questions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "id": {"type": "INTEGER", "description": "A unique question ID starting from 1."},
                        "type": {"type": "STRING", "enum": ["multiple_choice", "short_answer"], "description": "The type of question."},
                        "question_text": {"type": "STRING", "description": "The question content."},
                        "options": {
                            "type": "ARRAY",
                            "items": {"type": "STRING"},
                            "description": "Only for multiple_choice type. List of 3-5 possible answers. Empty list for short_answer."
                        },
                        "correct_answer": {"type": "STRING", "description": "The correct answer text (for MC) or a brief expected answer/key concept (for SA)."}
                    },
                    "required": ["id", "type", "question_text", "options", "correct_answer"]
                },
                "description": "A list of 5-7 questions covering the reflection topic."
            }
        },
        "required": ["title", "questions"]
    }

def validate_quiz_data(data: Dict[str, Any]) -> bool:
    """
    Performs critical validation on the parsed quiz structure.
    """
    if not isinstance(data.get('title'), str) or not data.get('title'):
        print("Validation Error: Quiz title is missing or invalid.")
        return False

    questions = data.get('questions')
    if not isinstance(questions, list) or not questions:
        print("Validation Error: Questions list is missing or invalid.")
        return False

    for q in questions:
        if q.get('type') not in ['multiple_choice', 'short_answer']:
            print(f"Validation Error: Invalid question type: {q.get('type')}")
            return False

        if q.get('type') == 'multiple_choice':
            options = q.get('options')
            if not isinstance(options, list) or not (3 <= len(options) <= 5):
                print(f"Validation Error: Multiple choice question {q.get('id')} has invalid options count.")
                return False

    return True

async def generate_reflection_quiz(topic: str) -> Dict[str, Any]:
    """
    Generates a structured reflection quiz on the given topic using the Gemini API.
    Implements exponential backoff for retries.
    """
    print(f"Attempting to generate reflection quiz for topic: {topic}")

    system_prompt = (
        "You are an educational quiz generator. Your task is to create a structured "
        "5-7 question reflection quiz based on the user's topic. "
        "The quiz MUST strictly follow the provided JSON schema. "
        "Include a mix of 'multiple_choice' (MC) and 'short_answer' (SA) questions. "
        "MC options must be 3-5 choices. SA questions should test understanding and reflection."
    )
    
    user_query = f"Generate a reflection quiz consisting of 5-7 questions about the following topic, using up-to-date information: {topic}"
    schema = get_reflection_quiz_schema()
    payload = create_api_payload(system_prompt, user_query, schema)
    
    max_retries = 3
    initial_delay = 1 # seconds

    for attempt in range(max_retries):
        try:
            # 1. API Call
            response = await fetch(API_URL, {
                'method': 'POST',
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(payload)
            })
            
            # Raise an exception for bad status codes (e.g., 400s or 500s)
            if not response.ok:
                raise Exception(f"API request failed with status {response.status}")

            result = await response.json()
            
            # 2. Extract and Parse Text
            json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
            
            if not json_text:
                raise ValueError("API response contained no generated text.")

            # The response is a JSON string due to responseMimeType
            quiz_data = json.loads(json_text)
            
            # 3. Validate Data Structure
            if not validate_quiz_data(quiz_data):
                # If validation fails, it's likely a model generation error. Retry.
                raise ValueError("Generated JSON failed structural validation.")
            
            print("Quiz generation successful.")
            return quiz_data # Success!

        except (Exception, ValueError) as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries - 1:
                # Calculate exponential backoff delay with jitter
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                print(f"Retrying in {delay:.2f} seconds...")
                await time.sleep(delay)
            else:
                print("Max retries reached. Failed to generate quiz.")
                # Return a failure structure or re-raise
                return {
                    "title": f"Error Quiz: {topic}",
                    "questions": [{"id": 1, "type": "short_answer", "question_text": "Failed to generate content.", "options": [], "correct_answer": ""}]
                }

    # Should not be reached if max_retries handles the final failure state
    return {}
    
# Example of a dummy function for local testing (can be removed later)
def test_quiz_generation():
    print("This is a local test run of the utility.")
    # Note: To actually test the API call, this would need to be run in an async environment.
    # print(await generate_reflection_quiz("Climate Change Mitigation"))

if __name__ == '__main__':
    # This block executes if the file is run directly
    print("Quiz Generator Utility Loaded.")
    # test_quiz_generation()
