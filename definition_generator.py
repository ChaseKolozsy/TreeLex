import client.src.operations.app_ops as app_ops
import client.src.operations.attribute_ops as attribute_ops
import client.src.operations.branch_node_ops as branch_node_ops
import client.src.operations.branch_ops as branch_ops
import client.src.operations.grammar_ops as grammar_ops
import client.src.operations.object_ops as object_ops
import client.src.operations.phrase_ops as phrase_ops
import client.src.operations.routine_ops as routine_ops
import client.src.operations.state_ops as state_ops
import client.src.operations.verb_ops as verb_ops

import client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops
import openai
from pydantic import BaseModel, Field
from typing import List, Dict

from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Example usage
example_json = {
    "base_lemma": "top",
    "definitions": [
        {"enumerated_lemma": "top_1", "definition": "The highest or uppermost point", "part_of_speech": "noun"},
        {"enumerated_lemma": "top_2", "definition": "To surpass or exceed", "part_of_speech": "verb"},
        {"enumerated_lemma": "top_3", "definition": "a toy with rounded sides, a flat top, a vertical handle, and a point at the bottom, that turns round and round on the point when the handle is pushed and pulled up and down or twisted", "part_of_speech": "noun"},
        {"enumerated_lemma": "top_4", "definition": "situated at the highest point or part; uppermost.", "part_of_speech": "adjective"},
        {"enumerated_lemma": "top_5", "definition": "extremely; very much", "part_of_speech": "adverb"},
        {"enumerated_lemma": "top_6", "definition": "a garment that is usually worn over the torso, that performs the function of a shirt", "part_of_speech": "noun"},
        {"enumerated_lemma": "top_7", "definition": "A role that one performs in a sexual relationship, indicating a position of dominance or control.", "part_of_speech": "noun"},
        {"enumerated_lemma": "top_8", "definition": "A lid or cover for a container", "part_of_speech": "noun"},
        {"enumerated_lemma": "top_9", "definition": "Of the highest quality or rank", "part_of_speech": "adjective"},
        {"enumerated_lemma": "top_10", "definition": "The upper part of something", "part_of_speech": "noun"}
    ]
}

example_json_small = {
    "base_lemma":  "top",
        "definitions": [
            {"enumerated_lemma": "top_1", "definition": "The highest or uppermost point", "part_of_speech": "noun"},
            {"enumerated_lemma": "top_2", "definition": "extremely; very much", "part_of_speech": "adverb"},
            {"enumerated_lemma": "top_n", "definition": "...", "part_of_speech": "..."},
    ]
}

import re

def extract_definitions(text):
    pattern = r'"base_lemma": "(.*?)",\n\s+"definitions": \[\n(.*?)\n\s+\]'
    matches = re.findall(pattern, text, re.DOTALL)

    extracted_data = []
    for match in matches:
        base_lemma = match[0]
        definitions = match[1]

        definition_pattern = r'"enumerated_lemma": "(.*?)",\n\s+"definition": "(.*?)",\n\s+"part_of_speech": "(.*?)"'
        individual_definitions = re.findall(definition_pattern, definitions)

        for enumerated_lemma, definition, part_of_speech in individual_definitions:
            extracted_data.append({
                "Base Lemma": base_lemma,
                "Enumerated Lemma": enumerated_lemma,
                "Definition": definition,
                "Part of Speech": part_of_speech
            })

    return extracted_data


import json
import time
import logging
from datetime import datetime
from pathlib import Path
import re

def preprocess_text(text):
    # Remove specified punctuation marks using regular expressions
    text = re.sub(r'[,:;.\-?!\']', '', text)
    return text


class DefinitionGenerator:
    """
    """
    def __init__(self, list_filepath, language='Hungarian', native_language='English', filepath_ids='definition_ids.txt', model="gpt-3.5-turbo-16k"):
        self.model = model
        self.client = openai.OpenAI()
        self.language = language
        self.native_language = native_language
        self.assistant_id = None
        self.thread_id = None
        self.sleep_interval = 5  # seconds
        self.max_retries = 3
        self.filepath_ids = filepath_ids
        self.tools = [
        {
                "type": "function",
                "function": {
                    "name": "generate_lemma_definitions",
                    "description": f"Generate a structured JSON output with definitions for a base lemma. It should look like this:\n{json.dumps(example_json_small, indent=4)}",
                    "parameters": {
                "type": "object",
                "properties": {
                    "base_lemma": {
                        "type": "string",
                        "description": "The base word or lemma for which definitions are to be generated"
                    },
                "definitions": {
                    "type": "array",
                    "items": {
                    "type": "object",
                    "properties": {
                        "enumerated_lemma": {
                            "type": "string",
                            "description": "The enumerated lemma for the definition, base_lemma_n where n is between 1 and 10, ie top_1, top_2, etc."
                        },
                        "definition": {
                        "type": "string",
                        "description": "The definition of the lemma"
                    },
                    "part_of_speech": {
                        "type": "string",
                        "enum": ["noun", "verb", "adjective", "adverb"],
                        "description": "The part of speech for the definition"
                    }
                },
                    "required": ["definition", "part_of_speech"]
                },
                "description": f"A list of definitions for the lemma. The definition should be in the language of {self.language} using no {self.native_language} words."
                    }
                },
                    "required": ["lemma", "definitions"]
                }
            }
        }
        ]


        self.list_filepath = list_filepath
        self.definitions = []
        self.string_list = []
        self.missing_definitions = []
        self.instructions = "You are an expert lexicographer with a deep understanding " \
                            "of etymology and semantics. Your task is to provide clear, " \
                            "concise, and accurate definitions for words, ensuring that " \
                            "each definition captures the essence and nuances of the word. " \
                            f"You will be defining words in the {self.language} language, " \
                            "drawing on your extensive knowledge to offer precise and " \
                            "contextually appropriate explanations. You will include no " \
                            f"{self.native_language} words in the definitions. Nor should you " \
                            "include the language that these instructions are in unless told to. " \
                            "If you are asked to define a word in a different language, you should " \
                            "define it in that language, not in the language of the instructions. " \
                            "A word will be supplied to you, one at a time. Its phrase will " \
                            "accompany it. The phrase is supplied for context to help you articulate " \
                            "the correct definition and its part of speech. However, you will supply " \
                            "more than one definition for this word. You will be constructing a " \
                            "a dictionary entry. Dictionary entries contain multiple definitions for " \
                            "a given lemma/word. You will create a JSON entry for the base_lemma. " \
                            "For example, the base lemma might be, 'top'. " \
                            "You will make the definition enumerated with 1 be the definition that best matches " \
                            "the phrase. If you are not sure, you can make an educated guess. You will be supplied " \
                            "with a phrase, and you will need to define the word in the phrase context. Always make " \
                            "the first enumerated lemma/word be the one that is represented in the phrase. " \
                            "Please strive for 10 definitions per lemma, " \
                            "If there are more than 10 definitions, provide the 10 most distinct definitions. " \
                            "If possible, the definitions supplied should illustrate 10 different distinct meanings " \
                            "of the word. BUT DO NOT MAKE UP DEFINITIONS TO SERVE THIS PURPOSE. They need to be real " \
                            "definitions that are used in the language for that word/lemma. Ideally, " \
                            "each definition should illustrate a different meaning of the word.  " \
                            f"Again, USE NO {self.native_language.upper()} words in the definitions. " \
                            f"ONLY USE {self.language.upper()} words. "
        self.is_phrase_list = False
        self.base_message = {"role": "system", "content": self.instructions}
        self.base_messages = [self.base_message]
        self.messages = [self.base_message]

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

    def analyze_list_content(self):
        # Ensure there's a list to analyze and it has more than 3 items (as we start analyzing from the 4th item)
        if not self.string_list or len(self.string_list) <= 3:
            print("List is too short to analyze. Assuming it contains words.")
            self.is_phrase_list = False
            return

        # Count how many items from the 4th one onward are phrases (i.e., contain more than one word)
        phrase_count = sum(1 for line in self.string_list[3:] if len(line.split()) > 1)

        # Calculate the percentage of phrases
        total_lines_to_analyze = len(self.string_list) - 3
        percentage_phrases = (phrase_count / total_lines_to_analyze) * 100

        # Set the flag based on whether more than 50% are phrases
        self.is_phrase_list = percentage_phrases > 50

        print(f"List analyzed. Contains {'mostly phrases' if self.is_phrase_list else 'mostly single words'}.")

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

        return responses

    def generate_definitions_for_word(self, word, item, responses):
        """
        Helper function to generate definitions for a given word.
        Retries the operation if it fails.
        """
        max_retries = 3 
        retries = 0
        success = False
        message = {"role": "user", "content": f"The word is {word} and the phrase is {item}."}
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
                    extracted_data = extract_definitions(tool_calls[0].function.arguments)
                    for data in extracted_data:
                        print(json.dumps(data, indent=4))
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
    
    def run(self, create=False): 
        self.load_list()
        print(self.string_list)

        responses = self.create_definitions()

        with open("definitions.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(responses, indent=4))
        # TODO: save the definitions to the database


if __name__ == "__main__":
    definition_generator = DefinitionGenerator(list_filepath="phrase_list.txt")
    definition_generator.run(create=False)