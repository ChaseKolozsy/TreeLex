import openai
import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from instruction_translator import InstructionTranslator
from pydict_translator import PydictTranslator

from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class POSIdentifier:
    def __init__(self, language, model="gpt-3.5-turbo-0125", data_dir="data", translate=False):
        self.client = openai.OpenAI()
        self.data_dir = Path(data_dir)
        self.language = language
        self.model = model
        self.max_retries = 3
        self.base_instructions = {
            "instructions": f"You are a helpful assistant that identifies the part of speech of a word in a given phrase in {self.language}."
        }
        self.base_content_keys = {
            "part_1": "Identify the part of speech of the word",
            "part_2": "in the phrase",
            "part_3": "with json format",
            "part_4": "part_of_speech"
        } 
        if translate:
            self.instruction_translator = InstructionTranslator(language=self.language, model="gpt-4o")
            self.instruction_translator.translate_instructions(self.base_instructions, outfile=(self.data_dir / "translated_content.json"))
            self.pydict_translator = PydictTranslator(language=self.language, model="gpt-4o")
            self.pydict_translator.translate_dictionaries(self.base_content_keys, outfile=(self.data_dir / "translated_content_keys.json"))
        self.load_translated_content()
        self.load_translated_content_keys()

        self.base_message = {
            "role": "system",
            "content": self.translated_content
        }
        logging.info(f"Base message: {self.base_message}")
        self.messages = [self.base_message]

    def load_translated_content(self):
        try:
            with open(self.data_dir / "translated_content.txt", "r", encoding="utf-8") as f:
                tmp = json.load(f)
                self.translated_content = tmp
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_content.txt file not found.")
            self.translated_content = ""

    def load_translated_content_keys(self):
        try:
            with open(self.data_dir / "translated_content_keys.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
                self.translated_content_keys = tmp
                logging.info(f"Translated content keys: {self.translated_content_keys}")
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_content_keys.json file not found.")
            self.translated_content_keys = ""

    def get_validation_schema(self):
        try:
            schema = {
                "type": "object",
                "properties": {
                    f"{self.translated_content_keys['part_4']}": {"type": "string"}
                },
                "required": [f"{self.translated_content_keys['part_4']}"],
                "additionalProperties": False
            }
            return schema
        except Exception as e:
            logging.error(f"Error getting validation schema: {e}")
            return None

    def identify_pos(self, word, phrase):
        messages = self.messages.copy()
        messages.append({
            "role": "user",
            "content": f"{self.translated_content_keys['part_1']} '{word}' {self.translated_content_keys['part_2']} '{phrase}' {self.translated_content_keys['part_3']}:\n {{'{self.translated_content_keys['part_4']}': '<POS>'}}"
        })
        logging.info(f"Messages: {messages}")
        backup_messages = messages.copy()

        retries = 0
        while retries < self.max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=0.0
                )
                response_message = json.loads(response.choices[0].message.content)
                try:
                    validate(instance=response_message, schema=self.get_validation_schema())
                    logging.info(f"\n\nresponse_message: {json.dumps(response_message, indent=4)}")
                    return response_message[f"{self.translated_content_keys['part_4']}"]
                except ValidationError as e:
                    logging.error(f"Validation error: {e}")
                    raise e
            except Exception as e:
                retries += 1
                messages = backup_messages
                logging.error(f"Error identifying part of speech: {e}")
        return None

if __name__ == "__main__":
    pos_identifier = POSIdentifier(language="Hungarian", data_dir="data", translate=False)
    word = "kutya"
    phrase = "A kutya színe az én szemem."
    pos = pos_identifier.identify_pos(word=word, phrase=phrase)
    print(f"The part of speech for '{word}' in the phrase '{phrase}' is: {pos}")