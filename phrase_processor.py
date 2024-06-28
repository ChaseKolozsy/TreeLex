import json
import logging
from pathlib import Path

from utils.general_utils import preprocess_text
from agents.pos_agent import POSAgent
from agents.matcher import Matcher
from agents.definition_extractor import DefinitionExtractor
from utils.api_clients import OpenAIClient, AnthropicClient
import lexiwebdb.client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops
import stanza.client.src.operations.app_ops as stanza_ops
from stanza.client.src.operations.app_ops import language_abreviations
from agents.definition_generator import DefinitionGenerator
from utils.dictionary_loader import DictionaryLoader
from utils.web_scraping_utils import extract_dictionary_data

advanced_model = "claude-3-5-sonnet-20240620"
affordable_model = "claude-3-haiku-20240307"

class PhraseProcessor:
    def __init__(self, language, native_language, api_type="anthropic", model="claude-3-haiku-20240307", dict_config=None, data_dir="data"):
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
        self.pos_agent = POSAgent(
            language=self.language,
            api_type=self.api_type,
            model=model,
            data_dir=str(self.data_dir)
        )
        self.dict_config = dict_config
        self.online_dictionary = False
        if self.dict_config:
            self.online_dictionary = True
            self.dictionary_loader = DictionaryLoader(self.data_dir)
            self.dictionary = self.dictionary_loader.setup_dictionary(dict_config)
            self.definition_extractor = DefinitionExtractor()

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
        model = advanced_model if len(word) < 4 else affordable_model
        pos_agent = POSAgent(
            language=self.language,
            api_type=self.api_type,
            model=model,
            data_dir=str(self.data_dir)
        )
        return pos_agent.identify_pos(word, phrase)

    def get_enumeration(self, word):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
        if response.status_code == 200:
            enumerated_lemmas = response.json()['enumerated_lemmas']
            return str(int(enumerated_lemmas[-1]['enumerated_lemma'].split('_')[1]) + 1)
        logging.info(f"No Base lemma found for word: {word}")
        return None

    def process_phrase(self, phrase, definition_generator):
        phrase_info = self._get_phrase_info(phrase)
        words = preprocess_text(phrase).split()
        entries = []

        for word in words:
            logging.info(f"\n------- word: {word} -----\n")
            try:
                pos = self._get_part_of_speech(word, phrase, phrase_info)
                enumerated_lemmas = self._get_enumerated_lemmas(word)
                
                if enumerated_lemmas:
                    entry = self._process_existing_lemmas(word, phrase, pos, phrase_info, enumerated_lemmas)
                else:
                    entry = self._generate_new_definition(word, phrase, pos, phrase_info, definition_generator)
                
                if entry:
                    entries.append(entry)

            except Exception as e:
                logging.error(f"Error processing word '{word.lower()}': {e}")

        return entries

    def _get_phrase_info(self, phrase):
        if self.use_stanza:
            phrase_info = self.phrase_analysis(phrase)
            logging.info(f"\n------- phrase: {phrase} phrase_info: {json.dumps(phrase_info, indent=4, ensure_ascii=False)} -----\n")
        else:
            logging.info(f"\n------- phrase: {phrase} -----\n")
            phrase_info = None
        return phrase_info

    def _get_part_of_speech(self, word, phrase, phrase_info):
        pos = self.get_pos(word, phrase)
        if not pos and phrase_info:
            pos = self._get_pos_from_phrase_info(word, phrase_info)
        logging.info(f"\n------- pos: {pos} -----\n")
        return pos

    def _get_pos_from_phrase_info(self, word, phrase_info):
        for _, value in phrase_info:
            for token in value:
                if token['text'] == word:
                    return self.pos_deprel_dict[token['pos']]
        return None

    def _get_enumerated_lemmas(self, word):
        response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
        if response.status_code == 200:
            return response.json()['enumerated_lemmas']
        elif self.online_dictionary:
            self._fetch_online_dictionary_data(word)
            response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
            return response.json()['enumerated_lemmas'] if response.status_code == 200 else None
        return None

    def _fetch_online_dictionary_data(self, word):
        url = self.dictionary.get_url(word.lower())
        session = self.dictionary.login()
        exclusions = self.dictionary.get_exclusions()
        target_root = self.dictionary.get_target_root()
        extracted_data = extract_dictionary_data(url, session, exclusions, target_root)
        self.definition_extractor.run(word, extracted_data)

    def _process_existing_lemmas(self, word, phrase, pos, phrase_info, enumerated_lemmas):
        matched_by_pos = self.pos_agent.get_pos_matches(word, pos, enumerated_lemmas)
        logging.info(f"\n\n------- matched_by_pos: {matched_by_pos} -----\n\n")

        if matched_by_pos:
            match, success = self.matcher.match_lemmas({
                "phrase": phrase,
                "base_lemma": word.lower(),
                "phrase_info": phrase_info if self.use_stanza else None,
                "definitions": {
                    lemma['enumerated_lemma']: {
                        "def": lemma['definition'],
                        "pos": lemma['part_of_speech']
                    } for lemma in enumerated_lemmas if lemma['enumerated_lemma'] in matched_by_pos
                }
            })
            if match:
                logging.info(f"\n\nmatch: {match}\n\n")
                return None  # Existing match found, no new entry needed
        return None  # No match found, will generate new definition

    def _generate_new_definition(self, word, phrase, pos, phrase_info, definition_generator):
        definition = definition_generator.generate_definition(word.lower(), phrase, pos, phrase_info)
        if definition:
            return {
                "enumeration": word + '_' + self.get_enumeration(word) if self.get_enumeration(word) else word + '_1',
                "base_lemma": word,
                "part_of_speech": pos,
                "definition": definition
            }
        return None


if __name__ == "__main__":
    phrase_processor = PhraseProcessor("hungarian", "english")
    definition_generator = DefinitionGenerator("hungarian", "english")
    phrase_processor.process_phrase("A kutya szép.", definition_generator)