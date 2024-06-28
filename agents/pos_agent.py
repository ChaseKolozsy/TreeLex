import json
import logging
from jsonschema import validate
from jsonschema.exceptions import ValidationError
from agents.instruction_translator import InstructionTranslator
from agents.pydict_translator import PydictTranslator
from pathlib import Path
from utils.api_clients import OpenAIClient, AnthropicClient
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class POSAgent:
    def __init__(self, language, api_type="anthropic", model="claude-3-haiku-20240307", data_dir="data", translate=False):
        self.api_type = api_type.lower()
        self.client = self._create_client(model)
        self.data_dir = Path(data_dir)
        self.language = language
        self.model = model
        self.max_retries = 1
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
        self.pos_deprel_dict = self.load_pos_deprel_dict()
        self.pos_deprel_terms = self.pos_deprel_dict.keys()

        if api_type == "openai":
            self.base_message = {
                "role": "system",
            "content": self.translated_content
        }
            logging.info(f"Base message: {self.base_message}")
            self.messages = [self.base_message]
        elif api_type == "anthropic":
            self.system_message = self.translated_content
            self.messages = []

    def _create_client(self, model):
        if self.api_type == "openai":
            return OpenAIClient(model)
        elif self.api_type == "anthropic":
            return AnthropicClient(model)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")

    def load_pos_deprel_dict(self):
        try:
            with open(Path(self.data_dir) / "pos_deprel_dict.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: pos_deprel_dict.json file not found in {self.data_dir}")
            return {}

    def load_translated_content(self):
        try:
            with open(self.data_dir / "translated_content.json", "r", encoding="utf-8") as f:
                tmp = json.load(f)
                self.translated_content = tmp
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_content.json file not found.")
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
        logging.info(f"\n\n ------- Messages: {messages} -------- \n")
        backup_messages = messages.copy()
        

        retries = 0
        while retries < self.max_retries:
            response_message = ""
            try:
                if self.api_type == "openai":
                    response_message = self.client.create_chat_completion(messages, system=None)
                else:
                    response_message = self.client.create_chat_completion(messages, system=self.system_message)
                try:
                    logging.info(f"\n\nresponse_message: {response_message}")
                    #validate(instance=response_message, schema=self.get_validation_schema())
                    #return response_message[f"{self.translated_content_keys['part_4']}"]
                    return response_message.split(': ')[1].replace('}', '').replace("'", "")
                except ValidationError as e:
                    logging.error(f"Validation error: {e}")
                    raise e
            except Exception as e:
                retries += 1
                messages = backup_messages
                logging.error(f"Error identifying part of speech: {e}")
        return None

    def get_pos_matches(self, base_lemma, pos, enumerated_lemmas, cache=False):
        stored_pos_list = [{lemma["enumerated_lemma"]: str(lemma["part_of_speech"])} for lemma in enumerated_lemmas]
        matched_lemmas = []
        count = 1

        for lemma in stored_pos_list:
            enumerated_lemma = f'{base_lemma}_{count}'
            count += 1
            # Perfect match
            if pos.lower() == lemma[enumerated_lemma].lower():
                matched_lemmas.append(enumerated_lemma)
                continue
            # Partial match (compound words)
            pos_parts = pos.lower().replace('-', ' ').replace('_', ' ').split(' ')
            stored_pos_parts = lemma[enumerated_lemma].lower().replace('-', ' ').replace('_', ' ').split(' ')
            common_parts = set(pos_parts) & set(stored_pos_parts)
            if common_parts:
                matched_lemmas.append(enumerated_lemma)
                continue

            # Synonymous match using chat completions
            if len(lemma[enumerated_lemma]) <= 4 or cache:
                synonymous = self.check_synonymous_pos(pos, lemma[enumerated_lemma])
                if synonymous:
                    matched_lemmas.append(enumerated_lemma)
            time.sleep(0.10)

        return matched_lemmas

    def check_synonymous_pos(self, pos1, pos2):
        prompt = f"""Compare the parts of speech '{pos1}' and '{pos2}' in {self.language}:
                    1. Score their similarity from 0 to 1:
                    - 0: Completely unrelated
                    - 1: Exactly synonymous
                    2. Respond only with a JSON object: {{"score": <FLOAT_VALUE>}}
                    Example: {{"score": 0.8}}"""
        system_message = f"You are a linguistic expert in {self.language}. Your task is to determine how closely related two parts of speech are. " \
            f"Strictly output JSON. No commentary"
        
        if self.api_type == "openai":
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
            response = self.client.create_chat_completion(messages, system=None)
        elif self.api_type == "anthropic":
            messages = [
                {"role": "user", "content": prompt}
            ]
            response = self.client.create_chat_completion(messages, system=system_message)
            response_value = response.split(': ')[1][:-1]
            logging.info(f"\n\nresponse_value: {response_value}\n\n")

        try:
            score = float(response_value)
            return True if score > 0.6 else False  # You can adjust this threshold
        except (ValueError, KeyError) as e:
            logging.error(f"Invalid response from AI: {response}")
            return False
    


if __name__ == "__main__":
    # Example usage with OpenAI
    #pos_identifier_openai = POSAgent(language="Hungarian", api_type="openai", model="gpt-3.5-turbo-0125", data_dir="data", translate=False)
    #word = "kutya"
    #phrase = "A kutya színe az én szemem."
    #pos_openai = pos_identifier_openai.identify_pos(word=word, phrase=phrase)
    #print(f"OpenAI - The part of speech for '{word}' in the phrase '{phrase}' is: {pos_openai}")

    ## Example usage with Anthropic
    pos_identifier_anthropic = POSAgent(language="Hungarian", api_type="anthropic", model="claude-3-haiku-20240307", data_dir="data", translate=False)
    #pos_anthropic = pos_identifier_anthropic.identify_pos(word=word, phrase=phrase)
    #print(f"Anthropic - The part of speech for '{word}' in the phrase '{phrase}' is: {pos_anthropic}")
    #print(pos_identifier_anthropic.check_synonymous_pos("NOUN", "főnév"))

    import lexiwebdb.client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops
    word = "szép"
    upos = 'ADJ'
    pos = pos_identifier_anthropic.pos_deprel_dict[upos]
    enumerated_lemmas = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word).json()['enumerated_lemmas']
    matches = pos_identifier_anthropic.get_pos_matches(word, pos, enumerated_lemmas)
    print(f"len(matches): {len(matches)}, matches: {matches}")