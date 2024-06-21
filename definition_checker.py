import re
import json
import logging
from nltk.stem import SnowballStemmer
from api_clients import AnthropicClient, OpenAIClient

class DefinitionChecker:
    SUPPORTED_LANGUAGES = {
        'english': 'english',
        'hungarian': 'hungarian',
        # Add more supported languages here
    }

    def __init__(self, api_type="anthropic", model="claude-3-haiku-20240307"):
        self.client = self._create_client(api_type, model)
        self.api_type = api_type

    def _create_client(self, api_type, model):
        if api_type.lower() == "openai":
            return OpenAIClient(model)
        elif api_type.lower() == "anthropic":
            return AnthropicClient(model)
        else:
            raise ValueError("Invalid api_type. Choose 'openai' or 'anthropic'.")

    def check_definition(self, word, definition, language, pos=None):
        language = language.lower()
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")

        print(f"Checking definition for word: {word}")
        result = self.basic_check(word, definition, language)
        if result is None:
            return self.llm_audit(word, definition, language, pos)
        else:
            return result
        

    def basic_check(self, word, definition, language):
        if word.lower() in definition.lower():
            print(f"Word {word} found in definition: {definition}")
            return False
        
        stemmer = SnowballStemmer(self.SUPPORTED_LANGUAGES[language])
        word_stem = stemmer.stem(word)
        print(f"Word stem: {word_stem}")
        def_words = re.findall(r'\w+', definition.lower())
        print(f"Definition words: {def_words}")
        if any(stemmer.stem(w) == word_stem for w in def_words):
            return False
        
        return None

    def llm_audit(self, word, definition, language, pos=None):
        prompt = f"""
        Language: {language}
        Word being defined: {word}
        Definition: {definition}
        Part of Speech: {pos if pos else 'Not specified'}

        Task: Analyze the definition and determine if it:
        1. Inappropriately uses the word being defined or any closely related forms.
        2. Matches the given part of speech (if specified).
        3. Is at an appropriate difficulty level for language learners.

        Consider conjugations, declensions, compounds, and semantic similarities.

        Output your analysis in JSON format with these keys:
        - valid: boolean indicating if the definition is valid
        - issues: list of any problematic aspects found
        - suggestions: list of suggested fixes if issues were found

        JSON response:
        """

        system = "You are an expert lexicographer tasked with auditing definitions for language learners. You only output json"
        if self.api_type == "openai":
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            result = json.loads(self.client.create_chat_completion(messages, system=None))
        else:
            messages = [ {"role": "user", "content": prompt} ]
            result = json.loads(self.client.create_chat_completion(messages, system=system))

        return result['valid']

# Usage
if __name__ == "__main__":
    checker = DefinitionChecker(api_type="anthropic", model="claude-3-sonnet-20240229")
    word = "run"
    definition = "To move swiftly on foot, where the feet leave the ground for an instant between steps."
    definition = "The infinitive of running"
    language = "english"
    pos = "verb"

    is_valid = checker.check_definition(word, definition, language, pos)
    print(f"Definition is valid: {is_valid}")