import openai
import json
import logging
from pathlib import Path
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from client.src.operations import enumerated_lemma_ops
from definition_generator import DefinitionGenerator
from match_reviewer import MatchReviewer

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class Matcher:
    """
    Matcher class is responsible for matching base lemmas with their correct enumerated lemmas in a given phrase.
    It leverages the OpenAI API to perform the matching based on provided definitions and phrases.

    Attributes:
        - model (str): The model used for matching.
        - client (openai.OpenAI): The OpenAI client for API interactions.
        - max_retries (int): The maximum number of retries for an operation.
        - base_word_phrase (dict): Dictionary containing base word and phrase keys.
        - translated_word_phrase (dict): Dictionary containing translated word and phrase keys.
        - definitions (list): List of definitions to be matched.
        - phrase (str): The phrase containing the base lemma.

    Methods:
        - __init__: Initializes the Matcher with specified parameters.
        - load_definitions: Loads definitions from the database.
        - match_lemmas: Matches base lemmas with enumerated lemmas in the phrase.
        - run: Executes the matching process.
    """
    def __init__(self, list_filepath, language, native_language, model="gpt-3.5-turbo-0125"):
        self.list_filepath = list_filepath
        self.language = language
        self.native_language = native_language
        self.model = model
        self.client = openai.OpenAI()
        self.match_reviewer = MatchReviewer(language, native_language, "gpt-4o")
        self.max_retries = 3
        self.string_list = []
        self.definitions = []
        self.example_input = {
            "phrase": "The boy played with his top.",
            "base_lemma": "top",
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
        self.base_message = {
            "role": "system",
            "content": f"{self.base_instructions}"
        }
        self.messages = [self.base_message]

    def load_definitions(self, base_lemma):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(base_lemma)
        logging.info(f"Response: {response.json()}")
        if response.status_code == 200:
            self.definitions = response.json()['enumerated_lemmas']
        else:
            logging.error(f"Error: Unable to load definitions for base lemma '{base_lemma}' from the database.")

    def load_list(self):
        """
        Load the list of strings from the specified file.
        """
        try:
            with open(self.list_filepath, 'r', encoding='utf-8') as file:
                self.string_list = [line.strip() for line in file.readlines()]
        except FileNotFoundError:
            logging.error(f"{self.list_filepath} file not found.")
        except Exception as e:
            logging.error(f"Error loading list from {self.list_filepath}: {e}")

    def match_lemmas(self):
        """
        Matches base lemmas with enumerated lemmas in the phrase.
        """
        max_retries = len(self.input['definitions'])
        retries = 0
        cut_off = False
        success = False
        message = {"role": "user", "content": f"{json.dumps(self.input, indent=4, ensure_ascii=False)}"}
        self.messages.append(message)
        back_up_messages = self.messages.copy()

        while not success and retries < max_retries:
            logging.info(f"Message: {json.dumps(message, indent=4, ensure_ascii=False)}")
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                response_message = json.loads(response.choices[0].message.content)
                logging.info(f"Response message: {response_message}")
                validate(instance=response_message, schema=self.get_validation_schema())

                #Peer Review
                matched_lemma = response_message['Matched Lemma']

                definition_to_validate = self.input['definitions'][matched_lemma]['def']

                match_to_validate = {}
                match_to_validate['phrase'] = self.input['phrase']
                match_to_validate['base_lemma'] = self.input['base_lemma']
                match_to_validate['definition'] = definition_to_validate

                is_valid = self.match_reviewer.run(match_to_validate)
                logging.info(f"Is valid: {is_valid}")
                if is_valid:
                    success = True
                    return response_message, success
                else:
                    logging.info(f"Definition is not valid for base lemma '{self.input['base_lemma']}': {definition_to_validate}")
                    for key, value in self.input['definitions'].items():
                        if key == matched_lemma['Matched Lemma']:
                            self.input['definitions'].pop(key)
                    raise Exception(f"Definition is not valid for base lemma '{self.input['base_lemma']}': {definition_to_validate}")
            except ValidationError as ve:
                logging.error(f"Validation error: {ve}")
                self.messages = back_up_messages
            except Exception as e:
                logging.error(f"Error: {e}")

                retries += 1
                if retries >= max_retries:
                    if not cut_off:
                        logging.error(f"\n\n--------- Failed to match lemmas after {max_retries} attempts. -------------\n\n")

                        logging.info(f"\n\n--------- Deleting lemmas: {self.input['base_lemma']} -------------\n\n")
                        lemmas_to_delete = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(matched_lemma['Matched Lemma'])
                        for lemma in lemmas_to_delete:
                            enumerated_lemma_ops.delete_enumerated_lemma(lemma['enumerated_lemma'])

                        logging.info(f"\n\n--------- Generating new lemmas: {self.input['base_lemma']} -------------\n\n")
                        definition_generator = DefinitionGenerator(self.language, self.native_language, self.model)
                        definition_generator.run_single_word(self.input['base_lemma'], self.input['phrase'])
                        new_lemmas = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(self.input['base_lemma'])
                        new_lemma_count = len(new_lemmas)
                        # Sort the lemmas_to_delete list based on the suffix number
                        logging.info(f"\n\n--------- Sorting lemmas and updating old lemmas: {self.input['base_lemma']} -------------\n\n")
                        sorted_old_lemmas = sorted(lemmas_to_delete, key=lambda x: int(x['enumerated_lemma'].split('_')[1]))

                        # Update the suffix numbers with the new_lemma_count
                        logging.info(f"\n\n--------- Updating lemmas: {self.input['base_lemma']} -------------\n\n")
                        for i, lemma in enumerate(sorted_old_lemmas):
                            suffix_number = int(lemma['enumerated_lemma'].split('_')[1])
                            new_suffix_number = suffix_number + new_lemma_count
                            lemma['enumerated_lemma'] = f"{lemma['enumerated_lemma'].split('_')[0]}_{new_suffix_number}"
                            data = {
                                'enumerated_lemma': lemma['enumerated_lemma'],
                                'base_lemma': lemma['base_lemma'],
                                'part_of_speech': lemma['part_of_speech'],
                                'definition': lemma['definition'],
                                'english_translation': lemma['english_translation'],
                                'frequency': lemma['frequency'],
                                'phrase': lemma['phrase'],
                                'story_link': lemma['story_link'],
                                'media_references': lemma['media_references'],
                                'object_exploration_link': lemma['object_exploration_link'],
                                'familiar': lemma['familiar'],
                                'active': lemma['active'],
                                'anki_card_ids': lemma['anki_card_ids']
                            }
                            try:
                                response = enumerated_lemma_ops.create_enumerated_lemma(data=data)
                                logging.info(json.dumps(response.json(), indent=4))
                            except Exception as e:
                                logging.error(f"Error creating enumerated lemma: {e}")

                        logging.info(f"\n\n--------- Loading new lemmas: {self.input['base_lemma']} -------------\n\n")
                        self.definitions = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(self.input['base_lemma'])
                        self.input['definitions'] = {}
                        for definition in self.definitions:
                            self.input['definitions'][definition['enumerated_lemma']] = {
                                "def": definition['definition'],
                                "pos": definition['part_of_speech']
                            }
                        max_retries = len(self.input['definitions'])
                        retries = 0
                        cut_off = True
                    else:
                        break

                self.messages = back_up_messages[:-1]
                message = {"role": "user", "content": f"{json.dumps(self.input, indent=4, ensure_ascii=False)}"}
                self.messages.append(message)
                back_up_messages = self.messages.copy()

                logging.info(f"Retrying... ({retries}/{max_retries})")

        return None, success

    def get_validation_schema(self):
        try:
            schema = {
                "type": "object",
                "properties": {
                    "Matched Lemma": {"type": "string"},
                },
                "required": ["Matched Lemma"]
            }
            return schema
        except Exception as e:
            logging.error(f"Error generating validation schema: {e}")
            return None

    def run(self):
        self.load_list()
        count = 0
        reset_count = 10
        for phrase in self.string_list:
            clean_phrase = phrase.replace(' ', '_').replace('!', '').replace(',', '').replace('.', '').replace(':', '').replace(';', '').replace('?', '').replace('!', '')
            tmp_list_filepath = f"tmp_{clean_phrase}.txt"
            with open(tmp_list_filepath, 'w', encoding='utf-8') as file:
                file.write(phrase)
            for word in phrase.split():
                try:
                    no_punc = word.replace(' ', '_').replace('!', '').replace(',', '').replace('.', '').replace(':', '').replace(';', '').replace('?', '').replace('!', '')
                    clean_word = no_punc.lower()

                    # Check if the word exists in the database
                    response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(clean_word)
                    if response.status_code == 404:
                        # If not, generate definitions using DefinitionGenerator
                        logging.info(f"Base lemma '{clean_word}' not found in database.")
                        try:
                            clean_word = no_punc
                            response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(clean_word)
                            logging.info(f"Response: {response.json()}")
                            self.definitions = response.json()['enumerated_lemmas']
                        except Exception as e:
                            logging.error(f"Error: {e}")

                    else:
                        self.definitions = response.json()['enumerated_lemmas']

                    self.input = {}
                    self.input['phrase'] = phrase
                    self.input['base_lemma'] = clean_word
                    self.input['definitions'] = {}

                    for definition in self.definitions:
                        self.input['definitions'][definition['enumerated_lemma']] = {
                            "def": definition['definition'],
                            "pos": definition['part_of_speech']
                        }
                    logging.info(json.dumps(self.input, indent=4, ensure_ascii=False))
                    matched_lemma, success = self.match_lemmas()
                    if success:
                        logging.info(f"Matched lemma: {matched_lemma}")
                        response = enumerated_lemma_ops.update_enumerated_lemma(matched_lemma['Matched Lemma'], data={'familiar': True})
                        logging.info(f"Response: {json.dumps(response.json(), indent=4, ensure_ascii=False)}")
                    if matched_lemma is None:
                        raise Exception(f"No match found for base lemma '{clean_word}'")
                except Exception as e:
                    logging.error(f"Error: {e}")

                proceed = input("Proceed? (y/n): ")
                if proceed.lower() != 'y':
                    break
            Path(tmp_list_filepath).unlink()
