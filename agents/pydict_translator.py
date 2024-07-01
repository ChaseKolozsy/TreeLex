import openai
import json
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s')
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s')

class PydictTranslator:
    def __init__(self, language, model="gpt-3.5-turbo-0125"):
        self.client = openai.OpenAI()
        self.language = language
        self.model = model
        self.max_retries = 3
        self.translated_word_phrase = {}
        self.base_message = {
            "role": "system",
            "content": f"You are a helpful assistant that translates python dictionary entries to {self.language}."
        }
        self.messages = [self.base_message]

    def get_validation_schema(self):
        try:
            schema = {
                "type": "object",
                "patternProperties": {
                    ".*": {"type": "string"}
                },
                "additionalProperties": False
            }
            return schema
        except Exception as e:
            logging.error(f"Error getting validation schema: {e}")
            return None

    def translate_dictionaries(self, base: dict, outfile: Path):
        if not outfile.suffix == ".json":
            raise ValueError("Outfile must be a json file")
        print(f"Translating {len(base)} entries to {self.language}")

        messages = self.messages.copy()
        backup_messages = messages.copy()
        for key, value in base.items():
            messages.append({
                "role": "user",
                "content": f"Translate '{value}' to {self.language} with json format:\n {key}: <translation>"
            })
            logging.info(f"Messages: {messages}")

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
                        for response_key, translated_value in response_message.items():
                            self.translated_word_phrase[key] = translated_value
                        break
                    except ValidationError as e:
                        logging.error(f"Validation error: {e}")
                        raise e
                except Exception as e:
                    retries += 1
                    messages = backup_messages
                    logging.error(f"Error translating dictionary: {e}")
                messages = backup_messages

        try:
            with open(outfile, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.translated_word_phrase, indent=4))
        except Exception as e:
            logging.error(f"Error writing to file {outfile}: {e}")

    def get_translated_word_phrase(self):
        return self.translated_word_phrase

if __name__ == "__main__":
    translator = PydictTranslator(language="Spanish")
    base_dict = {
        "hello": "A greeting",
        "world": "The earth, together with all of its countries and peoples"
    }
    translator.translate_dictionaries(base=base_dict, outfile="translated_dict.json")
    print(translator.get_translated_word_phrase())
