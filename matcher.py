import openai
import json
import logging
from pathlib import Path
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from client.src.operations import enumerated_lemma_ops
from definition_generator import DefinitionGenerator

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
        self.max_retries = 3
        self.base_word_phrase = {
            "word": "word",
            "phrase": "phrase"
        }
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
            f"enumerated lemmas in a given phrase. You will take a dictionary like this: {json.dumps(self.example_input, indent=4)} " \
            "You will use the phrase for context to determine which enumeration is the correct one. You will " \
            "output json with a single key: `Matched Lemma` and the value will be the correct enumerated lemma: " \
            f"{json.dumps(self.get_validation_schema(), indent=4)}"
        self.base_message = {
            "role": "system",
            "content": f"{self.base_instructions}"
        }
        self.messages = [self.base_message]

    def load_definitions(self, base_lemma):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(base_lemma)
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
        max_retries = self.max_retries
        retries = 0
        success = False
        message = {"role": "user", "content": f"{json.dumps(self.input, indent=4)}"}
        self.messages.append(message)
        back_up_messages = self.messages.copy()

        while not success and retries < max_retries:
            logging.info(f"Message: {message}")
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    response_format={"type": "json_object"},
                )
                response_message = json.loads(response.choices[0].message.content)
                logging.info(f"Response message: {response_message}")

                validate(instance=response_message, schema=self.get_validation_schema())
                success = True
                return response_message
            except ValidationError as ve:
                logging.error(f"Validation error: {ve}")
                self.messages = back_up_messages
                retries += 1
            except Exception as e:
                logging.error(f"Error: {e}")
                self.messages = back_up_messages
                retries += 1
                if retries >= max_retries:
                    logging.error(f"Failed to match lemmas after {max_retries} attempts.")
                    break
                logging.info(f"Retrying... ({retries}/{max_retries})")

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
                # Check if the word exists in the database
                response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word)
                if response.status_code == 404:
                    # If not, generate definitions using DefinitionGenerator
                    logging.info(f"Base lemma '{word}' not found in database. Generating definitions.")
                    definition_generator = DefinitionGenerator(
                        list_filepath=tmp_list_filepath,  # Update with the correct path
                        language=self.language,
                        native_language=self.native_language,
                        model=self.model
                    )
                    definition_generator.run()
                    # Reload definitions after generation
                    self.load_definitions(word)
                else:
                    self.definitions = response.json()['enumerated_lemmas']

                self.input = {}
                self.input['phrase'] = phrase
                self.input['base_lemma'] = word
                self.input['definitions'] = {}

                for definition in self.definitions:
                    self.input['definitions'][definition['enumerated_lemma']] = {
                        "def": definition['definition'],
                        "pos": definition['part_of_speech']
                    }
                logging.info(json.dumps(self.input, indent=4))
                matched_lemma = self.match_lemmas()
                logging.info(f"Matched lemma: {matched_lemma}")
                enumerated_lemma_ops.update_enumerated_lemma(matched_lemma, data={'familiar': True})
                Path(tmp_list_filepath).unlink()
                count += 1
                if count > reset_count:
                    self.messages = [self.base_message]
                    count = 0

if __name__ == "__main__":
    current_dir = Path.cwd()
    data_dir = current_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
    logging.info(f"data_dir: {data_dir}")
    list_filepath = data_dir / "list.txt"

    matcher = Matcher(
        language="English",
        native_language="English",
        list_filepath=list_filepath
    )
    matcher.run()