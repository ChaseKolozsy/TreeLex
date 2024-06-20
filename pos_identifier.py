import openai
import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class POSIdentifier:
    def __init__(self, language, model="gpt-3.5-turbo-0125"):
        self.client = openai.OpenAI()
        self.language = language
        self.model = model
        self.max_retries = 3
        self.base_message = {
            "role": "system",
            "content": f"You are a helpful assistant that identifies the part of speech of a word in a given phrase in {self.language}."
        }
        self.messages = [self.base_message]

    def get_validation_schema(self):
        try:
            schema = {
                "type": "object",
                "properties": {
                    "part_of_speech": {"type": "string"}
                },
                "required": ["part_of_speech"],
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
            "content": f"Identify the part of speech of the word '{word}' in the phrase '{phrase}' with json format:\n {{'part_of_speech': '<POS>'}}"
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
                    return response_message['part_of_speech']
                except ValidationError as e:
                    logging.error(f"Validation error: {e}")
                    raise e
            except Exception as e:
                retries += 1
                messages = backup_messages
                logging.error(f"Error identifying part of speech: {e}")
        return None

if __name__ == "__main__":
    pos_identifier = POSIdentifier(language="English")
    word = "top"
    phrase = "The boy played with his top."
    pos = pos_identifier.identify_pos(word=word, phrase=phrase)
    print(f"The part of speech for '{word}' in the phrase '{phrase}' is: {pos}")