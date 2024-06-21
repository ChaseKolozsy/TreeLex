import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pathlib import Path
from logging.handlers import RotatingFileHandler

from utils.def_gen_util import preprocess_text, load_config, pos_do_not_match, matches_by_pos
from pydict_translator import PydictTranslator
from instruction_translator import InstructionTranslator
from pos_identifier import POSIdentifier
from matcher import Matcher
from definition_checker import DefinitionChecker

import client.src.operations.app_ops as app_ops
import client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops

from api_clients import OpenAIClient, AnthropicClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
advanced_model = "claude-3-5-sonnet-20240620"

class DefinitionGenerator:
    def __init__(self, list_filepath, language='Hungarian', native_language='English', api_type="openai", model="gpt-3.5-turbo-0125"):
        self.model = model
        self.language = language
        self.native_language = native_language
        self.max_retries = 3
        self.min_definitions = 1

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
        self.data_dir = Path("data")

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
            with open(f"{self.data_dir}/translated_instructions.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
                self.translated_instructions = tmp
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_instructions.json file not found.")
            self.translated_instructions = ""

        self.instructions = self.translated_instructions + f"\n{json.dumps(self.example_json_small, indent=4)}"
        self.base_message = {"role": "system", "content": self.instructions}
        self.base_messages = [self.base_message]
        self.messages = [self.base_message]
    
    def load_translated_word_phrase(self):
        try:
            with open(f"{self.data_dir}/translated_word_phrase.json", "r", encoding="utf-8") as f:
                self.translated_word_phrase = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_word_phrase.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.data_dir}/translated_word_phrase.json.")
    
    
    
    def load_descriptions(self):
        try:
            with open(f"{self.data_dir}/translated_descriptions.json", "r", encoding="utf-8") as f:
                self.descriptions = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_descriptions.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.data_dir}/translated_descriptions.json.")
    
    
    
    def initialize_example_json_small(self):
        try:
            with open(f"{self.data_dir}/translated_example_json_small.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
            self.example_json_small = {
                "word":  "top",
                "def": f"{tmp['top']}"
            }
            logging.info(f"example_json_small: {self.example_json_small}")
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_example_json_small.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.data_dir}/translated_example_json_small.json.")

    def load_translated_pos(self):
        try:
            with open(f"{self.data_dir}/translated_pos.json", "r", encoding="utf-8") as f:
                self.translated_pos = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_pos.json file not found.")
    
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

    def get_pos(self, word, phrase):
        if len(word) < 4:
            model = advanced_model
        else:
            model = self.model

        pos_identifier = POSIdentifier(
            language=self.language,
            api_type=self.api_type,
            model=model,
            data_dir=str(self.data_dir)
        )
        return pos_identifier.identify_pos(word, phrase)
    
    
    def get_enumeration(self, word):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
        if response.status_code == 200:
            enumerated_lemmas = response.json()['enumerated_lemmas']
            return str(int(enumerated_lemmas[-1]['enumerated_lemma'].split('_')[1]) + 1)
        else:
            logging.info(f"No Base lemma found for word: {word}")
        
        return None

    def create_definitions(self):
        """
        Create definitions for each word in the string list.
        """
        entries = []
        for phrase in self.string_list:
            logging.info(f"\n------- phrase: {phrase} -----\n")
            try:
                words = preprocess_text(phrase).split()
                logging.info(f"\n------- words: {words}-----\n")

                for word in words:
                    logging.info(f"\n------- word: {word} -----\n")
                    try:
                        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())

                        pos = self.get_pos(word, phrase)
                        logging.info("\n\n-------------------------------------------------\n\n")
                        logging.info(f"\n------- pos: {pos} -----\n")

                        if response.status_code == 200:
                            enumerated_lemmas = response.json()['enumerated_lemmas']
                            logging.info("\n\n-------------------------------------------------\n\n")
                            logging.info(f"\n------- enumerated_lemmas: {enumerated_lemmas} -----\n")

                            pos_no_match = pos_do_not_match(enumerated_lemmas, pos) 
                            logging.info("\n\n-------------------------------------------------\n\n")
                            logging.info(f"\n------- pos_no_match: {pos_no_match} -----\n")
                            
                            if not pos_no_match:
                                match = self.matcher.match_lemmas({
                                    "phrase": phrase,
                                    "base_lemma": word.lower(),
                                    "definitions": {
                                        lemma['enumerated_lemma']: {
                                            "def": lemma['definition'],
                                            "pos": lemma['part_of_speech']
                                        } for lemma in enumerated_lemmas
                                    }
                                })
                                if match[0]:  # If a match is found, skip definition generation
                                    continue
                            
                        # If no match found, or no definitions exist, or no matching POS, generate a new definition
                        if not match[0] or response.status_code == 404:
                            self.generate_definition_for_word(word.lower(), phrase, pos, entries)
                        self.messages = self.base_messages
                    except Exception as e:
                        logging.error(f"Error processing word '{word.lower()}': {e}")
            except Exception as e:
                logging.error(f"Error processing phrase '{phrase}': {e}")

        return entries


    def generate_definition_for_word(self, word, phrase, pos, entries):
        max_retries = self.max_retries
        retries = 0
        success = False
        message = {
            "role": "user", "content": f"{self.translated_word_phrase.get('word', 'word')}: {word}."\
            f" {self.translated_word_phrase.get('phrase', 'phrase')}: {phrase}."\
            f" {self.translated_word_phrase.get('pos', 'part of speech')}: {pos}."
        }
        logging.info(f"message: {message}")
        self.messages.append(message)
        back_up_messages = self.messages.copy()
        logging.info(f"entering generate_definitions_for_word with message: {message}")

        while not success and retries < max_retries:
            try:
                response_content = self.client.create_chat_completion(self.messages)
                logging.info(f"response_content: {response_content}")
                validate(instance=response_content, schema=self.get_validation_schema())
                
                # Check if the definition is valid
                is_valid = self.definition_checker.check_definition(word, response_content['def'], self.language)
                if not is_valid:
                    raise ValueError("Definition contains the word being defined or a closely related form.")
                
                entry = {
                    "enumeration": word + '_' + self.get_enumeration(word) if self.get_enumeration(word) else word + '_1',
                    "base_lemma": word,
                    "part_of_speech": pos,
                    "definition": response_content['def']
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

    def get_definitions_from_online_dict(self, word):
        #TODO: implement this
        pass

    
    def add_definition_to_db(self, entries):
        for entry in entries:
            logging.info(json.dumps(entry, indent=4, ensure_ascii=False))
            data = {
                'enumerated_lemma': entry['enumeration'].lower(),
                'base_lemma': entry['base_lemma'].lower(),
                'part_of_speech': entry['part_of_speech'],
                'definition': entry['definition'],
                'english_translation': '',
                'frequency': 0,  # Assuming initial frequency is 0
                'phrase': '',  # Assuming no phrase is provided
                'story_link': '',  # Assuming no story link is provided
                'media_references': [],  # Assuming no media references are provided
                'object_exploration_link': '',  # Assuming no object exploration link is provided
                'familiar': False,  # Assuming not familiar initially
                'active': False,  # Assuming not active by default
                'anki_card_ids': [] # Assuming no anki card ids are provided
            }
            try:
                response = enumerated_lemma_ops.create_enumerated_lemma(data=data)
                logging.info(json.dumps(response.json(), indent=4))
            except Exception as e:
                logging.error(f"Error creating enumerated lemma: {e}")
                if "Enumerated Lemma already exists" in str(e):
                    data['enumerated_lemma'] = data['base_lemma'] + '_' + str(int(data['enumerated_lemma'].split('_')[1]) + 10)
                    response = enumerated_lemma_ops.create_enumerated_lemma(data=data)
                    logging.info(json.dumps(response.json(), indent=4))

    def load_and_initialize(self, translate=False):
        # load the descriptions, example json, tools and instructions
        self.load_descriptions()
        self.initialize_example_json_small()
        self.load_translated_word_phrase()
        self.load_translated_pos()
        self.base_instructions = {
            "instructions": "You are an expert lexicographer " \
                            f"You will be defining words in the {self.language} language, " \
                            "offering precise and " \
                            "contextually appropriate explanations in json format. You will include no " \
                            f"{self.native_language} words in the definitions. " \
                            "A phrase and part of speech is supplied for context to help you articulate " \
                            "the correct definition. You will be constructing " \
                            "a dictionary entry for a given lemma/word. " \
                            f"An example of a definition in json format is:\n {json.dumps(self.example_json_small, indent=4)}" 
        }
        self.initialize_instructions(translate=translate)
    
    def run_single_word(self, word, phrase):
        self.load_and_initialize()

        responses = []
        self.generate_definitions_for_word(word, phrase, responses)
        self.add_definition_to_db(responses)

    
    def run(self, familiar=False, translate=False): 
        self.load_list()
        logging.info(self.string_list)

        if translate:
            dict_translator = PydictTranslator(
                language=self.language, 
                model="gpt-4o"
            )

            dict_translator.translate_dictionaries(self.example_json_small, data_dir / "translated_example_json_small.json")
            dict_translator.translate_dictionaries(self.descriptions, data_dir / "translated_descriptions.json")
            dict_translator.translate_dictionaries(self.translated_word_phrase, data_dir / "translated_word_phrase.json")

        # load the descriptions, example json, tools and instructions
        self.load_and_initialize(translate=translate)

        entries = self.create_definitions()
        self.add_definition_to_db(entries)


if __name__ == "__main__":
    current_dir = Path.cwd()
    data_dir = current_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
    print(f"data_dir: {data_dir}")

    config = load_config(Path(data_dir) / "def_gen_config.yaml")

    definition_generator = DefinitionGenerator(
        list_filepath=config['list_filepath'],
        language=config['language'],
        native_language=config['native_language'],
        api_type=config.get('api_type', 'openai'),  # Default to 'openai' if not specified
        model=config['model']
    )
    definition_generator.run()

    #print(definition_generator.get_enumeration("dog"))
    #print(definition_generator.translated_instructions)
    #print(definition_generator.translated_pos)
    #print(definition_generator.example_json_small)
    #print(definition_generator.translated_word_phrase)
    #for key, value in definition_generator.descriptions.items():
    #    print(f"[{key}: {value}]")

#
#    # response = enumerated_lemma_ops.get_all_enumerated_lemmas()
#    # if response.status_code == 200:
#    #     lemmas = response.json()['enumerated_lemmas']
#    #     for lemma in lemmas:
#    #         for key, value in lemma.items():
#    #             print(f"{key}: {value}")
#    #         print("\n----------------\n")
#    # else:
#    #     print(response.status_code)
#