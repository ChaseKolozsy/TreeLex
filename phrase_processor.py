import json
import logging
from pathlib import Path

from utils.definition_utils import preprocess_text, pos_do_not_match, find_pos_in_phrase_info
from agents.pos_identifier import POSIdentifier
from agents.matcher import Matcher
from utils.api_clients import OpenAIClient, AnthropicClient
import lexiwebdb.client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops
import stanza.client.src.operations.app_ops as stanza_ops
from stanza.client.src.operations.app_ops import language_abreviations

class PhraseProcessor:
    def __init__(self, language, native_language, api_type, model, data_dir):
        self.language = language
        self.native_language = native_language
        self.api_type = api_type
        self.model = model
        self.data_dir = Path(data_dir)
        
        self.client = OpenAIClient(model) if api_type.lower() == "openai" else AnthropicClient(model)
        self.matcher = Matcher(None, language, native_language, api_type, model)
        
        self.use_stanza = True
        try:
            self.set_stanza_language()
        except Exception as e:
            logging.error(f"{e}")
            self.use_stanza = False

        self.pos_deprel_dict_file = self.data_dir / "pos_deprel_dict.json"
        self.pos_deprel_dict = self.load_or_generate_pos_deprel_dict()

    def set_stanza_language(self):
        stanza_ops.select_language(stanza_ops.language_abreviations[self.language])

    def phrase_analysis(self, phrase):
        return stanza_ops.process_text(phrase)

    def load_translated_pos(self):
        try:
            with open(f"{self.data_dir}/translated_pos.json", "r", encoding="utf-8") as f:
                self.translated_pos = json.load(f)
        except FileNotFoundError:
            logging.error(f"Error: {self.data_dir}/translated_pos.json file not found.")

    def load_or_generate_pos_deprel_dict(self):
        if self.pos_deprel_dict_file.exists():
            with open(self.pos_deprel_dict_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            pos_deprel_dict = self.generate_pos_deprel_dict()
            with open(self.pos_deprel_dict_file, 'w', encoding='utf-8') as f:
                json.dump(pos_deprel_dict, f, ensure_ascii=False, indent=4)
            return pos_deprel_dict

    def load_or_generate_pos_deprel_dict(self):
        if self.pos_deprel_dict_file.exists():
            with open(self.pos_deprel_dict_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            pos_deprel_dict = self.generate_pos_deprel_dict()
            with open(self.pos_deprel_dict_file, 'w', encoding='utf-8') as f:
                json.dump(pos_deprel_dict, f, ensure_ascii=False, indent=4)
            return pos_deprel_dict


    def get_translated_term(self, term):
        system = f"You are a helpful assistant that translates linguistic terms to {self.language} as would be seen inside of a {self.language} dictionary, and you will strictly output json in accordance with the user's request.."
        if self.api_type.lower() == "anthropic":
            client = AnthropicClient(self.model)
            prompt = f"\n\nTranslate the following linguistic term to {self.language}, output json with key: {term} and value: <translated_term> . Use the full term, no abbreviations. The term is: {term}"
            messages = [{"role": "user", "content": prompt}]
            translation = client.create_chat_completion(messages=messages, system=system)
        else:
            client = OpenAIClient(self.model)
            prompt = f"\n\nTranslate the following linguistic term to {self.language}, output json with key: {term} and value: <translated_term> . Use the full term, no abbreviations. The term is: {term}"
            messages = [{"role": "user", "content": prompt}]
            translation = client.create_chat_completion(messages=messages, system=system)

        try:
            translated_json = json.loads(translation)
            return translated_json[term]
        except (json.JSONDecodeError, KeyError):
            logging.error(f"Failed to parse response for term: {term}")
            return None


    def get_pos(self, word, phrase):
        advanced_model = "claude-3-5-sonnet-20240620"
        model = advanced_model if len(word) < 4 else self.model
        pos_identifier = POSIdentifier(
            language=self.language,
            api_type=self.api_type,
            model=model,
            data_dir=str(self.data_dir)
        )
        return pos_identifier.identify_pos(word, phrase)

    def get_enumeration(self, word):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
        if response.status_code == 200:
            enumerated_lemmas = response.json()['enumerated_lemmas']
            return str(int(enumerated_lemmas[-1]['enumerated_lemma'].split('_')[1]) + 1)
        logging.info(f"No Base lemma found for word: {word}")
        return None

    def process_phrase(self, phrase, definition_generator):
        if self.use_stanza:
            phrase_info = self.phrase_analysis(phrase)
            logging.info(f"\n------- phrase: {phrase} phrase_info: {json.dumps(phrase_info, indent=4, ensure_ascii=False)} -----\n")
        else:
            logging.info(f"\n------- phrase: {phrase} -----\n")
            phrase_info = None

        words = preprocess_text(phrase).split()
        logging.info(f"\n------- words: {words}-----\n")

        entries = []
        for word in words:
            logging.info(f"\n------- word: {word} -----\n")
            try:
                response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
                pos = self.get_pos(word, phrase)
                logging.info(f"\n------- pos: {pos} -----\n")

                if response.status_code == 200:
                    enumerated_lemmas = response.json()['enumerated_lemmas']
                    logging.info(f"\n------- enumerated_lemmas: {enumerated_lemmas} -----\n")

                    pos_no_match = pos_do_not_match(enumerated_lemmas, pos) 
                    logging.info(f"\n------- pos_no_match: {pos_no_match} -----\n")
                    
                    if not pos_no_match:
                        match = self.matcher.match_lemmas({
                            "phrase": phrase,
                            "base_lemma": word.lower(),
                            "phrase_info": phrase_info if self.use_stanza else None,
                            "definitions": {
                                lemma['enumerated_lemma']: {
                                    "def": lemma['definition'],
                                    "pos": lemma['part_of_speech']
                                } for lemma in enumerated_lemmas
                            }
                        })
                        if match[0]:  # If a match is found, skip definition generation
                            continue
                
                # If no match found, or no definitions exist, or no matching POS, generate a new definition
                if not match[0] or response.status_code == 404:
                    definition = definition_generator.generate_definition(word.lower(), phrase, pos, phrase_info)
                    if definition:
                        entry = {
                            "enumeration": word + '_' + self.get_enumeration(word) if self.get_enumeration(word) else word + '_1',
                            "base_lemma": word,
                            "part_of_speech": pos,
                            "definition": definition
                        }
                        entries.append(entry)

            except Exception as e:
                logging.error(f"Error processing word '{word.lower()}': {e}")

        return entries

# ... (rest of the file remains the same)