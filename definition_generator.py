import logging
import client.src.operations.app_ops as app_ops
import client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops

from jsonschema import validate
from jsonschema.exceptions import ValidationError
from utils.def_gen_util import preprocess_text, extract_definitions

import openai
import json
from pathlib import Path

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
        self.base_word_phrase = {
            "word": "word",
            "phrase": "phrase"
        }
        self.translated_word_phrase = {}

        self.base_descriptions = {
            "function_name": "generate_lemma_definitions",
            "function_description": "Generate a structured JSON output with definitions for a base lemma. It should look like this",
            "base_lemma_description": "The base word or lemma for which definitions are to be generated",
            "definitions_description": f"A list of ten definitions for the lemma. The definition should be in the language of {self.language} using no {self.native_language} words.",
            "enumerated_lemma_description": "The enumerated lemma for the definition, base_lemma_n where n is between 1 and 10, ie top_1, top_2, etc.",
            "definition_description": "The definition of the lemma",
            "part_of_speech_description": "The part of speech for the definition",
        }
        self.descriptions = {}
        self.tools = []
        self.example_json_small = {}
        self.example_json_to_translate = {
            "top_1": "The highest or uppermost point",
            "top_2": "extremely; very much",
            "noun": "noun",
            "adverb": "adverb"
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
                            "A phrase is supplied for context to help you articulate " \
                            "the correct definition and its part of speech. However, you will supply " \
                            "more than one definition for this word. You will be constructing " \
                            "a dictionary entry for a given lemma/word. " \
                            "Please strive for 10 definitions per lemma, " \
                            "The definitions supplied should represent 10 different distinct meanings. " \
                            f"An example of a definition is:\n" 
                            }

    def initialize_instructions(self, translate=False):
        if translate:
            self.translate_instructions()
        try:
            with open("translated_instructions.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
            for key, value in tmp.items():
                self.translated_instructions = value
        except FileNotFoundError:
            logging.error("Error: translated_instructions.json file not found.")
            self.translated_instructions = ""

        self.instructions = self.translated_instructions + f"\n{json.dumps(self.example_json_small, indent=4)}"
        self.base_message = {"role": "system", "content": self.instructions}
        self.base_messages = [self.base_message]
        self.messages = [self.base_message]
    
    def translate_instructions(self):
        messages = []
        for key, value in self.base_instructions.items():
            message = {"role": "user", "content": f"Translate '{value}' to {self.language} with json format:\n instructions: <translation>"}
            messages.append(message)
            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                response = json.loads(response.choices[0].message.content)
                logging.info(f"response: {response}")
                with open("translated_instructions.json", "w", encoding="utf-8") as f:
                    f.write(json.dumps(response, indent=4))
                for response_key, translated_value in response.items():
                    self.translated_instructions = translated_value
            except Exception as e:
                logging.error(f"An error occurred: {e}")
            messages = []
    
    
    
    def translate_dictionaries(self, base: dict, outfile: str):
        """
        Translate a dictionary from one language to another.
        base: dict - the dictionary to translate
        outfile: str - the file to save the translated dictionary to, must be json
        """
        if not outfile.endswith(".json"):
            raise ValueError("Outfile must be a json file")

        messages = []
        for key, value in base.items():
            message = {"role": "user", "content": f"Translate '{value}' to {self.language} with json format:\n {value}: <translation>"}
            messages.append(message)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"}
                )
                response = json.loads(response.choices[0].message.content)
                for response_key, translated_value in response.items():
                    self.translated_word_phrase[key] = translated_value
                messages = []
            except Exception as e:
                print(f"Error during dictionary translation: {e}")

        try:
            with open(outfile, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.translated_word_phrase, indent=4))
        except Exception as e:
            print(f"Error writing to file {outfile}: {e}")
    
    
    def load_translated_word_phrase(self):
        try:
            with open("translated_word_phrase.json", "r", encoding="utf-8") as f:
                self.translated_word_phrase = json.load(f)
        except FileNotFoundError:
            logging.error("Error: translated_word_phrase.json file not found.")
        except json.JSONDecodeError:
            logging.error("Error: JSON decode error in translated_word_phrase.json.")
    
    
    
    def load_descriptions(self):
        try:
            with open("descriptions.json", "r", encoding="utf-8") as f:
                self.descriptions = json.load(f)
        except FileNotFoundError:
            logging.error("descriptions.json file not found.")
        except json.JSONDecodeError:
            logging.error("JSON decode error in descriptions.json.")
    
    
    
    def initialize_example_json_small(self):
        try:
            with open("example_json_small.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
            self.example_json_small = {
                "base_lemma":  "top",
                "definitions": [
                    {"enumerated_lemma": "top_1", "definition": f"{tmp['top_1']}", "part_of_speech": f"{tmp['noun']}"},
                    {"enumerated_lemma": "top_2", "definition": f"{tmp['top_2']}", "part_of_speech": f"{tmp['adverb']}"},
                    {"enumerated_lemma": "top_n", "definition": '...', "part_of_speech": "..."},
                ]
            }
        except FileNotFoundError:
            logging.error("example_json_small.json file not found.")
        except json.JSONDecodeError:
            logging.error("JSON decode error in example_json_small.json.")
    
    
    
    def initialize_tools(self):
        """
        Initialize tools for function definitions.

        This method sets up the tools required for defining functions, including the name, description, and parameters.

        Parameters:
        - self: the object instance
        """
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": f"{self.base_descriptions['function_name']}",
                    "description": f"{self.descriptions['function_description']}:\n{json.dumps(self.example_json_small, indent=4)}",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "base_lemma": {
                                "type": "string",
                                "description": f"{self.descriptions['base_lemma_description']}"
                            },
                            "definitions": {
                                "type": "array",
                                "minItems": 10,
                                "maxItems": 10,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "enumerated_lemma": {
                                            "type": "string",
                                            "description": f"{self.descriptions['enumerated_lemma_description']}"
                                        },
                                        "definition": {
                                            "type": "string",
                                            "description": f"{self.descriptions['definition_description']}"
                                        },
                                        "part_of_speech": {
                                            "type": "string",
                                            "description": f"{self.descriptions['part_of_speech_description']}"
                                        }
                                    },
                                    "required": ["definition", "part_of_speech"]
                                },
                                "description": f"{self.descriptions['definitions_description']}"
                            }
                        },
                        "required": ["base_lemma", "definitions"]
                    }
                }
            }
        ]


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
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "Base Lemma": {"type": "string"},
                        "Enumerated Lemma": {"type": "string"},
                        "Definition": {"type": "string"},
                        "Part of Speech": {"type": "string"}
                    },
                    "required": ["Base Lemma", "Enumerated Lemma", "Definition", "Part of Speech"]
                }
            }
            return schema
        except Exception as e:
            print(f"Error generating validation schema: {e}")
            return None

    def create_definitions(self):
        """
        Create definitions for each word in the string list.
        """
        responses = []
        for item in self.string_list:
            try:
                words = preprocess_text(item).split()
                logging.info(words)

                for word in words:
                    try:
                        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word)
                        logging.info(response)
                        if response.status_code == 404:
                            self.generate_definitions_for_word(word, item, responses)
                            self.messages = self.base_messages
                            break
                    except Exception as e:
                        logging.error(f"Error processing word '{word}': {e}")
            except Exception as e:
                logging.error(f"Error processing item '{item}': {e}")

        return responses

    def generate_definitions_for_word(self, word, phrase, responses):
        """
        Helper function to generate definitions for a given word.
        Retries the operation if it fails.
        """
        max_retries = self.max_retries
        retries = 0
        success = False
        message = {"role": "user", "content": f"{self.translated_word_phrase.get('word', 'word')}: {word}. {self.translated_word_phrase.get('phrase', 'phrase')}: {phrase}."}
        logging.info(f"entering generate_definitions_for_word with message: {message}")

        while not success and retries < max_retries:
            logging.info(f"message: {message}")
            try:
                self.messages.remove(message)
            except ValueError:
                pass
            try:
                self.messages.append(message)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.tools,
                    tool_choice=self.tools[0]
                )

                response_message = response.choices[0].message
                tool_calls = response_message.tool_calls
                if tool_calls:
                    extracted_data = extract_definitions(tool_calls[0].function.arguments)
                    validate(instance=extracted_data, schema=self.get_validation_schema())
                    responses.append(extracted_data)
                    success = True
            except ValidationError as ve:
                logging.error(f"Validation error: {ve}")
                retries += 1
            except Exception as e:
                logging.error(f"Error: {e}")
                retries += 1
                if retries >= max_retries:
                    logging.error(f"Failed to generate definitions for word '{word}' after {max_retries} attempts.")
                    break
                logging.info(f"Retrying... ({retries}/{max_retries})")
    
    
    def run(self, familiar=False): 
        self.load_list()
        print(self.string_list)

        # load the descriptions, example json, tools and instructions
        self.load_descriptions()
        self.initialize_example_json_small()
        self.initialize_tools()
        self.initialize_instructions()
        self.load_translated_word_phrase()

        responses = self.create_definitions()
        for response in responses:
            for definition in response:
                data = {
                    'enumerated_lemma': definition['Enumerated Lemma'],
                    'base_lemma': definition['Base Lemma'],
                    'part_of_speech': definition['Part of Speech'],
                    'definition': definition['Definition'],
                    'frequency': 0,  # Assuming initial frequency is 0
                    'phrase': '',  # Assuming no phrase is provided
                    'story_link': '',  # Assuming no story link is provided
                    'media_references': [],  # Assuming no media references are provided
                    'object_exploration_link': '',  # Assuming no object exploration link is provided
                    'familiar': familiar,  # Assuming not familiar initially
                    'active': False,  # Assuming active by default
                    'anki_card_ids': [] # Assuming no anki card ids are provided
                }
                try:
                    enumerated_lemma_ops.create_enumerated_lemma(data=data)
                except Exception as e:
                    logging.error(f"Error creating enumerated lemma: {e}")

if __name__ == "__main__":
    current_dir = Path.cwd()
    data_dir = current_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
    print(f"data_dir: {data_dir}")
    
    # Uncomment and configure the following lines as needed
    # definition_generator = DefinitionGenerator(list_filepath=data_dir / "phrase_list.txt")
    # definition_generator.translate_dictionaries(definition_generator.base_descriptions, data_dir / "translated_descriptions.json")
    # definition_generator.translate_dictionaries(definition_generator.example_json_small, data_dir / "translated_example_json_small.json")
    # definition_generator.translate_dictionaries(definition_generator.translated_word_phrase, data_dir / "translated_word_phrase.json")
    # definition_generator.translate_instructions()
    # definition_generator.run(familiar=True)

    # response = enumerated_lemma_ops.get_all_enumerated_lemmas()
    # if response.status_code == 200:
    #     lemmas = response.json()['enumerated_lemmas']
    #     for lemma in lemmas:
    #         for key, value in lemma.items():
    #             print(f"{key}: {value}")
    #         print("\n----------------\n")
    # else:
    #     print(response.status_code)
