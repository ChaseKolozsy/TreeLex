import json
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s')
from pathlib import Path
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from lexiwebdb.client.src.operations import enumerated_lemma_ops
from stanza.client.src.operations.app_ops import process_text, select_language, language_abreviations
from agents.match_reviewer import MatchReviewer
from utils.api_clients import OpenAIClient, AnthropicClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s')

class Matcher:
    def __init__(self, list_filepath, language, native_language, api_type="anthropic", model="claude-3-haiku-20240307"):
        self.list_filepath = list_filepath
        self.language = language
        self.native_language = native_language
        self.api_type = api_type
        self.model = model
        self.client = self._create_client()
        self.match_reviewer = MatchReviewer(language, native_language, api_type, model)
        self.max_retries = 1
        self.string_list = []
        self.definitions = []
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
            "definitions": {
                "top_1": {
                    "def": "the peak, the highest point",
                    "pos": "noun"
                },
                "top_2": {
                    "def": "Highest in rank",
                    "pos": "adjective"
                },
                "top_3": {
                    "def": "A toy that can be spun and maintain its balance until it loses momentum",
                    "pos": "noun"
                }
            }
        }
        self.base_instructions = "You are a helpful assistant that matches base lemmas with their correct " \
            f"enumerated lemmas in a given phrase. You will take a dictionary like this: {json.dumps(self.example_input, indent=4, ensure_ascii=False)} " \
            "You will use the phrase for context to determine which enumeration is the correct one. You will " \
            "output json with a single key: `Matched Lemma` and the value will be the correct enumerated lemma: " \
            f"{json.dumps(self.get_validation_schema(), indent=4, ensure_ascii=False)}"
        
        self.system_message = self.base_instructions
        self.base_message = {
            "role": "system",
            "content": self.system_message
        }
        if self.api_type == "openai":
            self.messages = [self.base_message]
        else:
            self.messages = []

    def _create_client(self):
        if self.api_type.lower() == "openai":
            return OpenAIClient(self.model)
        elif self.api_type.lower() == "anthropic":
            return AnthropicClient(self.model)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")

    def load_definitions(self, base_lemma):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(base_lemma)
        logging.info(f"Response: {response.json()}")
        if response.status_code == 200:
            return response.json()['enumerated_lemmas']
        else:
            logging.error(f"Error: Unable to load definitions for base lemma '{base_lemma}' from the database.")
            return []

    def load_list(self):
        try:
            with open(self.list_filepath, 'r', encoding='utf-8') as file:
                self.string_list = [line.strip() for line in file.readlines()]
        except FileNotFoundError:
            logging.error(f"{self.list_filepath} file not found.")
        except Exception as e:
            logging.error(f"Error loading list from {self.list_filepath}: {e}")

    def match_lemmas(self, input_data):
        max_retries = len(input_data['definitions'])
        retries = 0
        success = False
        message = {"role": "user", "content": json.dumps(input_data, indent=4, ensure_ascii=False)}
        self.messages.append(message)
        back_up_messages = self.messages.copy()

        while not success and retries < max_retries:
            try:
                if self.api_type == "openai":
                    response_message = json.loads(self.client.create_chat_completion(self.messages, system=None))
                else:
                    response_message = json.loads(self.client.create_chat_completion(self.messages, system=self.system_message))

                validate(instance=response_message, schema=self.get_validation_schema())

                matched_lemma = response_message['Matched Lemma']
                definition_to_validate = input_data['definitions'][matched_lemma]['def']

                match_to_validate = {
                    'phrase': input_data['phrase'],
                    'base_lemma': input_data['base_lemma'],
                    'phrase_info': input_data['phrase_info'],
                    'definition': definition_to_validate
                }

                is_valid = self.match_reviewer.run(match_to_validate)
                if is_valid:
                    success = True
                    return response_message, success
                else:
                    logging.info(f"Definition is not valid for base lemma '{input_data['base_lemma']}': {definition_to_validate}")
                    input_data['definitions'].pop(matched_lemma)
                    raise Exception(f"Definition is not valid for base lemma '{input_data['base_lemma']}': {definition_to_validate}")
            except (ValidationError, Exception) as e:
                logging.error(f"Error: {e}")
                retries += 1
                self.messages = back_up_messages[:-1]
                message = {"role": "user", "content": json.dumps(input_data, indent=4, ensure_ascii=False)}
                self.messages.append(message)
                back_up_messages = self.messages.copy()
                logging.info(f"Retrying... ({retries}/{max_retries})")

        return None, success

    def get_validation_schema(self):
        return {
            "type": "object",
            "properties": {
                "Matched Lemma": {"type": "string"},
            },
            "required": ["Matched Lemma"]
        }

    def run(self):
        self.load_list()
        for phrase in self.string_list:
            self.process_phrase(phrase)

    def process_phrase(self, phrase):
        clean_phrase = phrase.replace(' ', '_').replace('!', '').replace(',', '').replace('.', '').replace(':', '').replace(';', '').replace('?', '').replace('!', '')
        tmp_list_filepath = f"tmp_{clean_phrase}.txt"
        with open(tmp_list_filepath, 'w', encoding='utf-8') as file:
            file.write(phrase)
        
        for word in phrase.split():
            self.process_word(word, phrase)

        Path(tmp_list_filepath).unlink()

    def process_word(self, word, phrase, phrase_info):
        clean_word = word.lower().strip('.,!?:;')
        definitions = self.load_definitions(clean_word)

        if definitions:
            input_data = {
                "phrase": phrase,
                "base_lemma": clean_word,
                "phrase_info": json.dumps(phrase_info, indent=4, ensure_ascii=False),
                "definitions": {
                    d['enumerated_lemma']: {
                        "def": d['definition'],
                        "pos": d['part_of_speech']
                    } for d in definitions
                }
            }
            matched_lemma, success = self.match_lemmas(input_data)
            if success:
                logging.info(f"Matched lemma: {matched_lemma}")
                response = enumerated_lemma_ops.update_enumerated_lemma(matched_lemma['Matched Lemma'], data={'familiar': True})
                logging.info(f"Response: {json.dumps(response.json(), indent=4, ensure_ascii=False)}")
            else:
                logging.error(f"No match found for base lemma '{clean_word}'")
        else:
            logging.error(f"No definitions available for base lemma '{clean_word}'")

    def run_by_word(self, word, phrase, phrase_info):
        self.process_word(word, phrase, phrase_info)
        logging.info("Word-by-word processing complete.")

if __name__ == "__main__":
    data_dir = Path("data")
    matcher = Matcher(list_filepath=data_dir / "list.txt", language="English", native_language="English")

    word = "dog"
    phrase = "The guy keeps dogging me no matter what I do."

    select_language(language=language_abreviations["English"])
    phrase_info = process_text(phrase).json()
    matcher.run_by_word(word=word, phrase=phrase, phrase_info=phrase_info)
