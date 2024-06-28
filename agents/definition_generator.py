import json
import csv
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pathlib import Path
from logging.handlers import RotatingFileHandler

from utils.definition_utils import find_pos_in_phrase_info, get_enumeration, add_definition_to_db
from agents.pydict_translator import PydictTranslator
from agents.instruction_translator import InstructionTranslator
from agents.matcher import Matcher
from agents.definition_checker import DefinitionChecker

import lexiwebdb.client.src.operations.app_ops as app_ops
import lexiwebdb.client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops

from utils.api_clients import OpenAIClient, AnthropicClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
advanced_model = "claude-3-5-sonnet-20240620"

class DefinitionGenerator:
    def __init__(self, list_filepath=None, language='Hungarian', native_language='English', api_type="anthropic", model="claude-3-haiku-20240307"):
        self.model = model
        self.language = language
        self.native_language = native_language
        self.max_retries = 3
        self.min_definitions = 1
        self.api_type = api_type

        if api_type.lower() == "openai":
            self.client = OpenAIClient(model)
        elif api_type.lower() == "anthropic":
            self.client = AnthropicClient(model)
        else:
            raise ValueError("Invalid api_type. Choose 'openai' or 'anthropic'.")

        self.matcher = Matcher(list_filepath, language, native_language, api_type, model)
        self.definition_checker = DefinitionChecker(api_type=api_type, model=model)

        self.base_word_phrase = {
            "word": "word",
            "phrase": "phrase",
            "pos": "part of speech"
        }
        self.translated_word_phrase = {}
        self.data_dir = Path("data/definition_generator")
        self.language_dir = self.data_dir / f"{self.language}"
        if not self.language_dir.exists():
            self.language_dir.mkdir(parents=True)

        self.base_descriptions = {
            "function_name": "generate_lemma_definitions",
            "function_description": f"Generate a structured JSON output with {self.min_definitions} definition for a word. It should look like this: ",
            "base_lemma_description": "The base word or lemma for which a definition is to be generated",
            "definition_description": f"{self.min_definitions} definition for the word. The definition should be in the language of {self.language} using no {self.native_language} words.",
        }
        self.descriptions = {}
        self.tools = []
        self.example_json_small = {}
        self.example_json_to_translate = {
            "top": "The highest or uppermost point" 
        }

        self.list_filepath = list_filepath
        self.string_list = []
    
        log_file = 'definition_generator.log'
        file_handler = RotatingFileHandler(log_file, mode='a', maxBytes=5*1024*1024, backupCount=2)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(file_handler)
        
    def initialize_instructions(self, translate=False):
        if translate:
            logging.info(f"translating instructions: {self.base_instructions}")
            InstructionTranslator(
                language=self.language, 
                model="gpt-4o", 
                base_instructions=self.base_instructions, 
                outfile=self.data_dir / "translated_instructions.json"
            )
        try:
            with open(self.language_dir / f"{self.language}_instructions.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
                self.translated_instructions = tmp
        except FileNotFoundError:
            logging.error(f"Error: {self.language_dir}/{self.language}_instructions.json file not found.")
            self.translated_instructions = ""

        self.instructions = self.translated_instructions + f"\n{json.dumps(self.example_json_small, indent=4)}"
        self.system_message = self.instructions
        self.base_message = {"role": "system", "content": self.system_message}
        self.base_messages = [self.base_message]

        if self.api_type.lower() == "openai":
            self.messages = [self.base_message]
        else:
            self.messages = []
    
    def load_translated_word_phrase(self):
        try:
            with open(self.language_dir / f"{self.language}_word_phrase.json", "r", encoding="utf-8") as f:
                self.translated_word_phrase = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.language_dir}/{self.language}_word_phrase.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.language_dir}/{self.language}_word_phrase.json.")
    
    def load_descriptions(self):
        try:
            with open(self.language_dir / f"{self.language}_descriptions.json", "r", encoding="utf-8") as f:
                self.descriptions = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.language_dir}/{self.language}_descriptions.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.language_dir}/{self.language}_descriptions.json.")
    
    def initialize_example_json_small(self):
        try:
            with open(self.language_dir / f"{self.language}_example_json_small.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
            self.example_json_small = {
                "word":  "top",
                "def": f"{tmp['top']}"
            }
            logging.info(f"example_json_small: {self.example_json_small}")
        except FileNotFoundError:
            logging.error(f"Error: {self.language_dir}/{self.language}_example_json_small.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.language_dir}/{self.language}_example_json_small.json.")

    
    def load_list(self):
        """
        Load the list of strings from the specified file.
        This list will be used in the create_definitions method.
        """
        try:
            with open(self.list_filepath, 'r', encoding='utf-8') as file:
                self.string_list = [line.strip() for line in file.readlines()]
        except FileNotFoundError:
            logging.error(f"{self.list_filepath} file not found.")
        except Exception as e:
            logging.error(f"Error loading list from {self.list_filepath}: {e}")

    def get_validation_schema(self):
        try:
            schema = {
                "type": "object",
                    "properties": {
                        "word": {"type": "string"},
                        "def": {"type": "string"}
                    },
                    "required": ["word", "def"]
                }
            return schema
        except Exception as e:
            print(f"Error generating validation schema: {e}")
            return None


    def generate_definition_for_word(self, 
                                     *, 
                                     word: str, 
                                     phrase: str, 
                                     pos: str, 
                                     entries: list, 
                                     phrase_info: str = None):
        max_retries = self.max_retries
        retries = 0
        success = False
        message = {
            "role": "user", "content": f"{self.translated_word_phrase.get('word', 'word')}: {word}."\
            f" {self.translated_word_phrase.get('phrase', 'phrase')}: {phrase}."\
            f" {self.translated_word_phrase.get('pos', 'part of speech')}: {pos}."

        }
        if phrase_info:
            message["content"] += f"\n{phrase_info}"

        logging.info(f"message: {message}")
        self.messages.append(message)
        back_up_messages = self.messages.copy()
        logging.info(f"entering generate_definitions_for_word with message: {message}")

        while not success and retries < max_retries:
            try:
                if self.api_type == "openai":
                    response_message = json.loads(self.client.create_chat_completion(self.messages, system=None))
                else:
                    response_message = json.loads(self.client.create_chat_completion(self.messages, system=self.system_message))
                logging.info(f"response_message: {response_message}")
                validate(instance=response_message, schema=self.get_validation_schema())

                stanza_pos = find_pos_in_phrase_info(word, phrase_info)

                # Check if the definition is valid
                is_valid = self.definition_checker.check_definition(word, response_message['def'], self.language)
                if not is_valid and stanza_pos != 'DET':
                    raise ValueError("Definition contains the word being defined or a closely related form.")
                
                entry = {
                    "enumeration": word + '_' + get_enumeration(word) if get_enumeration(word) else word + '_1',
                    "base_lemma": word,
                    "part_of_speech": pos,
                    "definition": response_message['def']
                }
                entries.append(entry)
                success = True
            except ValidationError as ve:
                logging.error(f"Validation error: {ve}")
                error_message = {"role": "user", "content": f"Error: {ve}"}
                back_up_messages.append(error_message)
                self.messages = back_up_messages
                retries += 1
            except ValueError as ve:
                logging.error(f"Definition check failed: {ve}")
                error_message = {"role": "user", "content": f"Error: {ve}. Please provide a definition that does not use the word '{word}' or closely related forms."}
                back_up_messages.append(error_message)
                self.messages = back_up_messages
                retries += 1
            except Exception as e:
                logging.error(f"Error: {e}")
                retries += 1
                if retries >= max_retries:
                    logging.error(f"Failed to generate definitions for word '{word}' after {max_retries} attempts.")
                    break
                logging.info(f"Retrying... ({retries}/{max_retries})")


    def load_and_initialize(self, translate=False):
        if translate:
            dict_translator = PydictTranslator(
                language=self.language, 
                model="gpt-4o"
            )

            dict_translator.translate_dictionaries(self.example_json_small, self.language_dir / f"{self.language}_example_json_small.json")
            dict_translator.translate_dictionaries(self.descriptions, self.language_dir / f"{self.language}_descriptions.json")
            dict_translator.translate_dictionaries(self.translated_word_phrase, self.language_dir / f"{self.language}_word_phrase.json")

        # load the descriptions, example json, tools and instructions
        self.load_descriptions()
        self.initialize_example_json_small()
        self.load_translated_word_phrase()
        self.base_instructions = {
            "instructions": "You are an expert lexicographer " \
                            f"You will be defining words in the {self.language} language, " \
                            "offering precise and " \
                            "contextually appropriate explanations in json format. You will include no " \
                            f"{self.native_language} words in the definitions. " \
                            "A phrase, part of speech and a tokenized phrase is supplied for context to help you articulate " \
                            "the correct definition. You will be constructing " \
                            "a dictionary entry for a given lemma/word. " \
                            f"An example of a definition in json format is:\n {json.dumps(self.example_json_small, indent=4)}" 
        }
        self.initialize_instructions(translate=translate)
    
    def run_single_word(self, *, word: str, phrase: str, phrase_info: list, entries: list, pos: str):
        self.generate_definition_for_word(word=word, phrase=phrase, phrase_info=phrase_info, entries=entries, pos=pos)
        add_definition_to_db(entries)


if __name__ == "__main__":
    definition_generator = DefinitionGenerator()
    word = "dog"
    phrase = "I love taking my dog for a walk."
    entries = []
    pos = "Noun"
    phrase_info = [
                    {
                        "text": "I love taking my dog for a walk.",
                        "tokens": [
                            {
                                "deprel": "nsubj",
                                "lemma": "I",
                                "pos": "PRON",
                                "text": "I"
                            },
                            {
                                "deprel": "root",
                                "lemma": "love",
                                "pos": "VERB",
                                "text": "love"
                            },
                            {
                                "deprel": "xcomp",
                                "lemma": "take",
                                "pos": "VERB",
                                "text": "taking"
                            },
                            {
                                "deprel": "nmod:poss",
                                "lemma": "my",
                                "pos": "PRON",
                                "text": "my"
                            },
                            {
                                "deprel": "obj",
                                "lemma": "dog",
                                "pos": "NOUN",
                                "text": "dog"
                            },
                            {
                                "deprel": "case",
                                "lemma": "for",
                                "pos": "ADP",
                                "text": "for"
                            },
                            {
                                "deprel": "det",
                                "lemma": "a",
                                "pos": "DET",
                                "text": "a"
                            },
                            {
                                "deprel": "obl",
                                "lemma": "walk",
                                "pos": "NOUN",
                                "text": "walk"
                            },
                            {
                                "deprel": "punct",
                                "lemma": ".",
                                "pos": "PUNCT",
                                "text": "."
                            }
                        ]
                    }
                ]
    definition_generator.load_and_initialize()
    definition_generator.run_single_word(word=word, phrase=phrase, phrase_info=phrase_info, entries=entries, pos=pos)