import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from utils.api_clients import OpenAIClient, AnthropicClient


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MatchReviewer:
    def __init__(self, language, native_language, api_type="anthropic", model="claude-3-haiku-20240307"):
        self.language = language
        self.native_language = native_language
        self.model = model
        self.max_retries = 3
        self.api_type = api_type

        if api_type.lower() == "openai":
            self.client = OpenAIClient(model)
        elif api_type.lower() == "anthropic":
            self.client = AnthropicClient(model)
        else:
            raise ValueError("Invalid api_type. Choose 'openai' or 'anthropic'.")

        self.example_input = {
            "phrase": "The boy played with his top.",
            "base_lemma": "top",
            "phrase_info": [
                                {
                                    "text": "The boy played with his top.",
                                    "tokens": [
                                        {
                                            "deprel": "det",
                                            "lemma": "the",
                                            "pos": "DET",
                                            "text": "The"
                                        },
                                        {
                                            "deprel": "nsubj",
                                            "lemma": "boy",
                                            "pos": "NOUN",
                                            "text": "boy"
                                        },
                                        {
                                            "deprel": "root",
                                            "lemma": "play",
                                            "pos": "VERB",
                                            "text": "played"
                                        },
                                        {
                                            "deprel": "case",
                                            "lemma": "with",
                                            "pos": "ADP",
                                            "text": "with"
                                        },
                                        {
                                            "deprel": "nmod:poss",
                                            "lemma": "his",
                                            "pos": "PRON",
                                            "text": "his"
                                        },
                                        {
                                            "deprel": "obl",
                                            "lemma": "top",
                                            "pos": "NOUN",
                                            "text": "top"
                                        },
                                        {
                                            "deprel": "punct",
                                            "lemma": ".",
                                            "pos": "PUNCT",
                                            "text": "."
                                        }
                                    ]
                                }
                            ],
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
            "phrase_info": [
                                {
                                    "text": "The man achieved top performance at his job.",
                                    "tokens": [
                                        {
                                            "deprel": "det",
                                            "lemma": "the",
                                            "pos": "DET",
                                            "text": "The"
                                        },
                                        {
                                            "deprel": "nsubj",
                                            "lemma": "man",
                                            "pos": "NOUN",
                                            "text": "man"
                                        },
                                        {
                                            "deprel": "root",
                                            "lemma": "achieve",
                                            "pos": "VERB",
                                            "text": "achieved"
                                        },
                                        {
                                            "deprel": "amod",
                                            "lemma": "top",
                                            "pos": "ADJ",
                                            "text": "top"
                                        },
                                        {
                                            "deprel": "obj",
                                            "lemma": "performance",
                                            "pos": "NOUN",
                                            "text": "performance"
                                        },
                                        {
                                            "deprel": "case",
                                            "lemma": "at",
                                            "pos": "ADP",
                                            "text": "at"
                                        },
                                        {
                                            "deprel": "nmod:poss",
                                            "lemma": "his",
                                            "pos": "PRON",
                                            "text": "his"
                                        },
                                        {
                                            "deprel": "obl",
                                            "lemma": "job",
                                            "pos": "NOUN",
                                            "text": "job"
                                        },
                                        {
                                            "deprel": "punct",
                                            "lemma": ".",
                                            "pos": "PUNCT",
                                            "text": "."
                                        }
                                    ]
                                }
                            ],
            "definition": "A toy that can be spun and maintain its balance until it loses momentum"
        }
        self.base_instructions = "You are a helpful assistant that verifies that the definition is correct for " \
            f"a given base_lemma. You will take a dictionary like this: {json.dumps(self.example_input, indent=4)} " \
            "You will use the phrase for context to determine whether or not the definiton matches the base lemma. " \
            "You will strictly output json with a single key: `Is_Correct` and the value will be a boolean: " \
            f"{json.dumps(self.example_output_False, indent=4)} or {json.dumps(self.example_output_True, indent=4)}"

        self.system_message = self.base_instructions
        self.base_message = {
            "role": "system",
            "content": self.system_message
        }

        if self.api_type == "openai":
            self.messages = [self.base_message]
        else:
            self.messages = []

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
            "content": json.dumps(match_to_validate, indent=4, ensure_ascii=False)
        })
        logging.info(f"Messages: {self.messages}")
        backup_messages = self.messages.copy()

        while retries < max_retries:
            try:
                if self.api_type == "openai":
                    response_message = json.loads(self.client.create_chat_completion(self.messages, system=None))
                else:
                    response_message = json.loads(self.client.create_chat_completion(self.messages, system=self.system_message))
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
        if self.api_type == "openai":
            self.messages = [self.base_message]
        else:
            self.messages = []
        return self.review_matches(match_to_validate)


if __name__ == "__main__":
    match_reviewer = MatchReviewer(language="English", native_language="English")
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