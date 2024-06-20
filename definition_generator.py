import client.src.operations.app_ops as app_ops
import client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops

from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pathlib import Path

from utils.def_gen_util import preprocess_text, extract_definitions, load_config
from pydict_translator import PydictTranslator
from instruction_translator import InstructionTranslator

import openai
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DefinitionGenerator:
    """
    DefinitionGenerator class is responsible for generating structured JSON output with definitions for base lemmas. 
    It provides functionality to define words in a specified language, ensuring clear, concise, and accurate definitions. 
    The class leverages extensive knowledge of etymology and semantics to offer contextually appropriate explanations. 
    It aims to provide 10 distinct meanings for each lemma, excluding any words from the native language. 

    Attributes:
        - model (str): The model used for generating definitions.
        - client (openai.OpenAI): The OpenAI client for API interactions.
        - language (str): The target language for defining words.
        - native_language (str): The native language for exclusion in definitions.
        - max_retries (int): The maximum number of retries for an operation.
        - base_word_phrase (dict): Dictionary containing base word and phrase keys.
        - translated_word_phrase (dict): Dictionary containing translated word and phrase keys.
        - base_descriptions (dict): Dictionary containing base descriptions for definitions.
        - descriptions (dict): Dictionary containing descriptions for tools.
        - tools (list): List of tools for function definitions.
        - example_json_small (dict): Example JSON structure for translation.
        - example_json_to_translate (dict): Example JSON for translation.
        - list_filepath (str): The file path for the list of strings.
        - string_list (list): List of strings loaded from file.
        - base_instructions (dict): Instructions for the lexicographer.
        - instructions (str): Instructions for generating definitions.
        - translated_instructions (str): Translated instructions.
        - base_message (dict): Base message for system interaction.
        - base_messages (list): List of base messages.
        - messages (list): List of messages for interactions.

    Methods:
        - __init__: Initializes the DefinitionGenerator with specified parameters.
        - initialize_instructions: Initializes instructions for generating definitions.
        - translate_instructions: Translates instructions to the target language.
        - translate_dictionaries: Translates dictionaries to the target language.
        - load_translated_word_phrase: Loads translated word phrases from file.
        - load_descriptions: Loads descriptions for tools from file.
        - initialize_example_json_small: Initializes example JSON structure.
        - initialize_tools: Initializes tools for function definitions.
        - load_list: Loads the list of strings from the specified file.
        - get_validation_schema: Retrieves the validation schema for definitions.
        - create_definitions: Creates definitions for each word in the string list.
        - generate_definitions_for_word: Generates definitions for a given word.
        - run: Executes the process of generating definitions.

    """
    def __init__(self, list_filepath, language='Hungarian', native_language='English', model="gpt-3.5-turbo-0125"):
        self.model = model
        self.client = openai.OpenAI()
        self.language = language
        self.native_language = native_language
        self.max_retries = 3
        self.min_definitions = 1
        self.base_word_phrase = {
            "word": "word",
            "phrase": "phrase",
            "pos": "part of speech"
        }
        self.translated_word_phrase = {}
        self.data_dir = "data"

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
        self.pos_enum = {
            "enum": [
                "noun", 
                "pronoun", 
                "verb", 
                "adjective", 
                "adverb", 
                "preposition", 
                "conjunction", 
                "interjection", 
                "article", 
                "determiner", 
                "particle", 
                "gerund", 
                "infinitive", 
                "auxiliary verb", 
                "modal verb",
                "definite article",
                "indefinite article",
                "demonstrative pronoun",
                "personal pronoun",
                "relative pronoun",
                "interrogative pronoun",
            ]
        }


        self.list_filepath = list_filepath
        self.string_list = []
        self.base_instructions = {"instructions": "You are an expert lexicographer with a deep understanding " \
                            "of etymology and semantics. Your task is to provide clear, " \
                            "concise, and accurate definitions for words." \
                            f"You will be defining words in the {self.language} language, " \
                            "drawing on your extensive knowledge to offer precise and " \
                            "contextually appropriate explanations. You will include no " \
                            f"{self.native_language} words in the definitions." \
                            "A phrase and part of speech is supplied for context to help you articulate " \
                            "the correct definition. You will be constructing " \
                            "a dictionary entry for a given lemma/word. " \
                            f"An example of a definition is:\n {json.dumps(self.example_json_small, indent=4)}" 
                            }

    def initialize_instructions(self, translate=False):
        if translate:
            InstructionTranslator(
                language=self.language, 
                model=self.model, 
                base_instructions=self.base_instructions, 
                outfile=f"{self.data_dir}/translated_instructions.json"
            )
        try:
            with open(f"{self.data_dir}/translated_instructions.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
            for key, value in tmp.items():
                self.translated_instructions = value
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
            with open(f"{self.data_dir}/descriptions.json", "r", encoding="utf-8") as f:
                self.descriptions = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/descriptions.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.data_dir}/descriptions.json.")
    
    
    
    def initialize_example_json_small(self):
        try:
            with open(f"{self.data_dir}/example_json_small.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
            self.example_json_small = {
                "word":  "top",
                "def": f"{tmp['top']}"
            }
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/example_json_small.json file not found.")
        except json.JSONDecodeError:
            logging.error(f"Error: JSON decode error in {self.data_dir}/example_json_small.json.")
    
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
                        if response.status_code == 404:
                            logging.info(f"\n------- status code: {response.status_code} Word not found -----\n")
                            pos = self.get_pos(word, phrase)
                            self.generate_definitions_for_word(word, phrase, pos, entries)
                            self.messages = self.base_messages
                    except Exception as e:
                        logging.error(f"Error processing word '{word}': {e}")
            except Exception as e:
                logging.error(f"Error processing phrase '{phrase}': {e}")

        return entries

    def get_pos(self, word, phrase):
        # TODO: implement this
        pos = {"pos": "noun"}
        return pos.get('pos', 'noun')
    
    def get_enumeration(self, word):
        #TODO: this should find the largest enumeration in the database and then add 1 to it and return that
        enumeration = {"enumeration": "1"}
        return enumeration.get('enumeration', '1')

    def generate_definition_for_word(self, word, phrase, pos, entries):
        """
        Helper function to generate definitions for a given word.
        Retries the operation if it fails.
        """
        max_retries = self.max_retries
        retries = 0
        success = False
        message = {
            "role": "user", "content": f"{self.translated_word_phrase.get('word', 'word')}: {word}."\
            f"{self.translated_word_phrase.get('phrase', 'phrase')}: {phrase}."\
            f"{self.translated_word_phrase.get('pos', 'part of speech')}: {pos}."
        }
        logging.info(f"message: {message}")
        self.messages.append(message)
        back_up_messages = self.messages.copy()
        logging.info(f"entering generate_definitions_for_word with message: {message}")

        while not success and retries < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    response_format={"type": "json_object"},
                    temperature=0.0
                )

                response_content = json.loads(response.choices[0].message.content)
                logging.info(f"response_content: {response_content}")
                validate(instance=response_content, schema=self.get_validation_schema())
                entry = {
                    "enumeration": self.get_enumeration(word),
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
            logging.info(json.dumps(entry, indent=4))
            for definition in entry:
                logging.info(json.dumps(definition, indent=4))
                data = {
                    'enumerated_lemma': definition['Enumerated Lemma'],
                    'base_lemma': definition['Base Lemma'].lower(),
                    'part_of_speech': definition['Part of Speech'],
                    'definition': definition['Definition'],
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
        self.initialize_instructions(translate=translate)
        self.load_translated_word_phrase()
    
    def run_single_word(self, word, phrase):
        self.load_and_initialize()

        responses = []
        self.generate_definitions_for_word(word, phrase, responses)
        self.add_definition_to_db(responses)

    
    def run(self, familiar=False): 
        self.load_list()
        logging.info(self.string_list)

        # load the descriptions, example json, tools and instructions
        self.load_and_initialize(translate=True)

        responses = self.create_definitions()
        self.add_definition_to_db(responses)


if __name__ == "__main__":
    current_dir = Path.cwd()
    data_dir = current_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
    print(f"data_dir: {data_dir}")
#
    config = load_config(data_dir / "def_gen_config.yaml")
#
    definition_generator = DefinitionGenerator(
        list_filepath=config['list_filepath'],
        language=config['language'],
        native_language=config['native_language'],
        model=config['model']
    )
    
    # Uncomment and configure the following lines as needed
    dict_translator = PydictTranslator(
        language=definition_generator.language, 
        model=definition_generator.model
    )

    dict_translator.translate_dictionaries(definition_generator.base_descriptions, data_dir / "translated_descriptions.json")
    dict_translator.translate_dictionaries(definition_generator.example_json_small, data_dir / "translated_example_json_small.json")
    #dict_translator.translate_dictionaries(definition_generator.translated_word_phrase, data_dir / "translated_word_phrase.json")

    definition_generator.run()
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