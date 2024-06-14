import client.src.operations.app_ops as app_ops
import client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops

from jsonschema import validate
from jsonschema.exceptions import ValidationError
from utils.deg_gen_util import preprocess_text, extract_definitions

import openai
import json

class DefinitionGenerator:
    """
    """
    def __init__(self, list_filepath, language='Hungarian', native_language='English', filepath_ids='definition_ids.txt', model="gpt-3.5-turbo-0125"):
        self.model = model
        self.client = openai.OpenAI()
        self.language = language
        self.native_language = native_language
        self.assistant_id = None
        self.thread_id = None
        self.sleep_interval = 5  # seconds
        self.max_retries = 3
        self.filepath_ids = filepath_ids
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
        self.definitions = []
        self.string_list = []
        self.missing_definitions = []
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
        with open("translated_instructions.json", "r", encoding="utf-8") as f:
            tmp = json.load(f)
        for key, value in tmp.items():
            self.translated_instructions = value

        self.instructions = self.translated_instructions + f"\n{json.dumps(self.example_json_small, indent=4)}"
        self.is_phrase_list = False
        self.base_message = {"role": "system", "content": self.instructions}
        self.base_messages = [self.base_message]
        self.messages = [self.base_message]
    
    def translate_tool_descriptions(self):
        """
            Translates the values of each key into the language of self.language.
                self.base_descriptions = {
                    "function_name": "generate_lemma_definitions",
                    "function_description": "Generate a structured JSON output with definitions for a base lemma. It should look like this:",
                    "base_lemma_description": "The base word or lemma for which definitions are to be generated",
                    "definitions_description": f"A list of definitions for the lemma. The definition should be in the language of {self.language} using no {self.native_language} words.",
                    "enumerated_lemma_description": "The enumerated lemma for the definition, base_lemma_n where n is between 1 and 10, ie top_1, top_2, etc.",
                    "definition_description": "The definition of the lemma",
                    "part_of_speech_description": "The part of speech for the definition"
                }
        """
        messages = []
        for key, value in self.base_descriptions.items():
            message = {"role": "user", "content": f"Translate '{value}' to {self.language} with json format:\n {value}: <translation>"}
            messages.append(message)
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"}
            )
            response = json.loads(response.choices[0].message.content)
            print(f"response: {response}")
            for response_key, translated_value in response.items():
                self.descriptions[key] = translated_value
            messages = []
        with open("descriptions.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.descriptions, indent=4))

    def translate_example_json_small(self):
        messages = []
        for key, value in self.example_json_to_translate.items():
            message = {"role": "user", "content": f"Translate '{value}' to {self.language} with json format:\n {value}: <translation>"}
            messages.append(message)
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"}
            )
            response = json.loads(response.choices[0].message.content)
            print(f"response: {response}")
            for response_key, translated_value in response.items():
                self.example_json_small[key] = translated_value
            messages = []
        with open("example_json_small.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.example_json_small, indent=4))
    
    def translate_instructions(self):
        messages = []
        for key, value in self.base_instructions.items():
            message = {"role": "user", "content": f"Translate '{value}' to {self.language} with json format:\n instructions: <translation>"}
            messages.append(message)
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"}
            )
            response = json.loads(response.choices[0].message.content)
            print(f"response: {response}")
            with open("translated_instructions.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(response, indent=4))
            for response_key, translated_value in response.items():
                self.translated_instructions = translated_value
            messages = []
    
    def translate_word_phrase(self):
        messages = []
        for key, value in self.base_word_phrase.items():
            message = {"role": "user", "content": f"Translate '{value}' to {self.language} with json format:\n {value}: <translation>"}
            messages.append(message)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"}
            )
            response = json.loads(response.choices[0].message.content)
            for response_key, translated_value in response.items():
                self.translated_word_phrase[key] = translated_value
            messages = []

        with open("translated_word_phrase.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(self.translated_word_phrase, indent=4))
    
    def load_translated_word_phrase(self):
        with open("translated_word_phrase.json", "r", encoding="utf-8") as f:
            self.translated_word_phrase = json.load(f)
    
    def load_descriptions(self):
        with open("descriptions.json", "r", encoding="utf-8") as f:
            self.descriptions = json.load(f)
    
    def initialize_example_json_small(self):
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
    
    def initialize_tools(self):
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
        with open(self.list_filepath, 'r', encoding='utf-8') as file:
            self.string_list = [line.strip() for line in file.readlines()]

    def get_validation_schema(self):
        return {
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

    def create_definitions(self):
        responses = []
        for item in self.string_list:
            words = preprocess_text(item).split()
            print(words)

            for word in words:
                response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word)
                print(response)
                if response.status_code == 404:
                    self.generate_definitions_for_word(word, item, responses)
                    self.messages = self.base_messages
                    break

        return responses

    def generate_definitions_for_word(self, word, phrase, responses):
        """
        Helper function to generate definitions for a given word.
        Retries the operation if it fails.
        """
        max_retries = 3 
        retries = 0
        success = False
        message = {"role": "user", "content": f"{self.translated_word_phrase['word']}: {word}. {self.translated_word_phrase['phrase']}: {phrase}."}
        print(f"entering generate_definitions_for_word with messsage: {message}")

        while not success and retries < max_retries:
            print(f"message: {message}")
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
                    #print(f"tool_calls[0].function.arguments: {tool_calls[0].function.arguments}")  # Debug print
                    extracted_data = extract_definitions(tool_calls[0].function.arguments)
                    validate(instance=extracted_data, schema=self.get_validation_schema())
                    responses.append(extracted_data)
                    success = True
            except Exception as e:
                print(f"Error: {e}")
                retries += 1
                if retries >= max_retries:
                    print(f"Failed to generate definitions for word '{word}' after {max_retries} attempts.")
                    break
                print(f"Retrying... ({retries}/{max_retries})")
    
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
                enumerated_lemma_ops.create_enumerated_lemma(data=data)

if __name__ == "__main__":
    #app_ops.reset_db()
    definition_generator = DefinitionGenerator(list_filepath="phrase_list.txt")
    #definition_generator.translate_tool_descriptions()
    #definition_generator.translate_example_json_small()
    #definition_generator.translate_word_phrase()
    definition_generator.run(familiar=True)

    #response = enumerated_lemma_ops.get_all_enumerated_lemmas()
    #if response.status_code == 200:
    #    lemmas = response.json()['enumerated_lemmas']
    #    for lemma in lemmas:
    #        for key, value in lemma.items():
    #            print(f"{key}: {value}")
    #        print("\n----------------\n")
    #else:
    #    print(response.status_code)