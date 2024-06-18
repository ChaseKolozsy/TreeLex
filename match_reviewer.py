
import openai
import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MatchReviewer:
    def __init__(self, language, native_language, model="gpt-3.5-turbo-0125"):
        self.client = openai.OpenAI()
        self.language = language
        self.native_language = native_language
        self.model = model
        self.max_retries = 3
        self.example_input = {
            "phrase": "The boy played with his top.",
            "base_lemma": "top",
            "definition": "A toy that can be spun and maintain its balance until it loses momentum"
        }
        self.base_instructions = "You are a helpful assistant that verifies that the definition is correct for " \
            f"a given base_lemma. You will take a dictionary like this: {json.dumps(self.example_input, indent=4)} " \
            "You will use the phrase for context to determine whether or not the definiton matches the base lemma. " \
            "You will output json with a single key: `Is_Correct` and the value will be a boolean: " \
            f"{json.dumps(self.get_validation_schema(), indent=4)}"

        self.base_message = {
            "role": "system",
            "content": f"{self.base_instructions}"
        }
        self.messages = [self.base_message]

    def get_validation_schema(self):
        try:
            schema = {
                "Is_Correct": {"type": "boolean"}
            }
            return schema
        except Exception as e:
            logging.error(f"Error getting validation schema: {e}")
            return None

    def review_matches(self, match_to_validate):
        max_retries = self.max_retries
        retries = 0
        self.messages.append({
            "role": "user",
            "content": f"{json.dumps(match_to_validate, indent=4)}"
        })
        logging.info(f"Messages: {self.messages}")
        while retries < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    response_format={"type": "json_object"},
                )
                response_message = json.loads(response.choices[0].message.content)
                try:
                    validate(instance=response_message, schema=self.get_validation_schema())
                    logging.info(f"\n\nresponse_message: {json.dumps(response_message, indent=4)}")
                    logging.info(f"\n\nresponse_message['Is_Correct']: {response_message['Is_Correct']}")
                    is_correct = response_message['Is_Correct']['value'] if isinstance(response_message['Is_Correct'], dict) else response_message['Is_Correct']
                    logging.info(f"\n\nIs_Correct value: {is_correct}")
                    return is_correct
                except ValidationError as e:
                    logging.error(f"Validation error: {e}")
            except Exception as e:
                retries += 1
                logging.error(f"Error reviewing matches: {e}")
        return None
    
    def run(self, match_to_validate):
        self.messages = [self.base_message]
        return self.review_matches(match_to_validate)