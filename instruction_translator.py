import openai
import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InstructionTranslator:
    def __init__(self, language, model="gpt-4o", base_instructions={}, outfile=Path("data/translated_instructions.json")):
        self.client = openai.OpenAI()
        self.language = language
        self.model = model
        self.max_retries = 3
        self.translated_instructions = ""
        self.translate_instructions(base_instructions=base_instructions, outfile=outfile)

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

    def translate_instructions(self, base_instructions: dict, outfile: str):
        if not outfile.suffix == ".json":
            raise ValueError("Outfile must be a json file")

        messages = []
        for key, value in base_instructions.items():
            messages.append({
                "role": "user",
                "content": f"Translate '{value}' to {self.language} with json format:\n instructions: <translation>"
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
                        #validate(instance=response_message, schema=self.get_validation_schema())
                        logging.info(f"\n\nresponse_message: {json.dumps(response_message, indent=4)}")
                        for response_key, translated_value in response_message.items():
                            self.translated_instructions = translated_value
                        break
                    except ValidationError as e:
                        logging.error(f"Validation error: {e}")
                        raise e
                except Exception as e:
                    retries += 1
                    messages = backup_messages
                    logging.error(f"Error translating instructions: {e}")

        try:
            with open(outfile, "w", encoding="utf-8") as f:
                f.write(json.dumps(self.translated_instructions, indent=4))
        except Exception as e:
            logging.error(f"Error writing to file {outfile}: {e}")

if __name__ == "__main__":
    translator = InstructionTranslator(language="Spanish")
    base_instructions = {
        "instruction1": "Please follow the steps carefully.",
    }
    translator.translate_instructions(base_instructions=base_instructions, outfile="translated_instructions.json")
    print(translator.get_translated_instructions())