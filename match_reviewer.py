import openai
import anthropic
import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from api_clients import OpenAIClient, AnthropicClient

class MatchReviewer:
    def __init__(self, language, native_language, api_type="openai", model="gpt-3.5-turbo-0125"):
        self.language = language
        self.native_language = native_language
        self.model = model
        self.max_retries = 3

        if api_type.lower() == "openai":
            self.client = OpenAIClient(model)
        elif api_type.lower() == "anthropic":
            self.client = AnthropicClient(model)
        else:
            raise ValueError("Invalid api_type. Choose 'openai' or 'anthropic'.")

        self.example_input = {
            "phrase": "The boy played with his top.",
            "base_lemma": "top",
            "definition": "A toy that can be spun and maintain its balance until it loses momentum"
        }
        self.example_output_False = {
            "Is_Correct": False
        }
        self.example_output_True = {
            "Is_Correct": True
        }
        self.bad_input = {
            "phrase": "The man achieved top performance at his job.",
            "base_lemma": "top",
            "definition": "A toy that can be spun and maintain its balance until it loses momentum"
        }
        self.base_instructions = "You are a helpful assistant that verifies that the definition is correct for " \
            f"a given base_lemma. You will take a dictionary like this: {json.dumps(self.example_input, indent=4)} " \
            "You will use the phrase for context to determine whether or not the definiton matches the base lemma. " \
            "You will output json with a single key: `Is_Correct` and the value will be a boolean: " \
            f"{json.dumps(self.example_output_False, indent=4)} or {json.dumps(self.example_output_True, indent=4)}"

        self.base_message = {
            "role": "system",
            "content": f"{self.base_instructions}"
        }
        self.messages = [self.base_message]

    def get_validation_schema(self):
        try:
            schema = {
                "type": "object",
                "properties": {
                    "Is_Correct": {"type": "boolean"}
                },
                "required": ["Is_Correct"]
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
        backup_messages = self.messages.copy()

        while retries < max_retries:
            try:
                response_message = self.client.create_chat_completion(self.messages)
                try:
                    validate(instance=response_message, schema=self.get_validation_schema())
                    logging.info(f"\n\nresponse_message: {json.dumps(response_message, indent=4)}")
                    logging.info(f"\n\nresponse_message['Is_Correct']: {response_message['Is_Correct']}")
                    is_correct = response_message['Is_Correct']
                    logging.info(f"\n\nIs_Correct value: {is_correct}")
                    return is_correct
                except ValidationError as e:
                    logging.error(f"Validation error: {e}")
                    raise e
            except Exception as e:
                retries += 1
                self.messages = backup_messages
                logging.error(f"Error reviewing matches: {e}")
        return None
    
    def run(self, match_to_validate):
        self.messages = [self.base_message]
        return self.review_matches(match_to_validate)


if __name__ == "__main__":
    match_reviewer = MatchReviewer(language="English", native_language="English", api_type="openai")
    is_correct_bad = match_reviewer.run(match_to_validate=match_reviewer.bad_input)
    is_correct_good = match_reviewer.run(match_to_validate=match_reviewer.example_input)

    if is_correct_bad and is_correct_bad is not None:
        logging.info(f"\n\nTest Failed: Is True: {is_correct_bad}, should be False\n\n")
    if not is_correct_bad and is_correct_bad is not None:
        logging.info(f"\n\nTest Passed: Is False: {is_correct_bad}\n\n")

    if is_correct_good and is_correct_good is not None:
        logging.info(f"\n\nTest Passed: Is True: {is_correct_good}")
    if not is_correct_good and is_correct_good is not None:
        logging.info(f"\n\nTest Failed: Is False: {is_correct_good}, should be True")