import re
import json
from nltk.stem import SnowballStemmer
from api_clients import AnthropicClient, OpenAIClient

class DefinitionChecker:
    def __init__(self, api_type="openai", model="gpt-3.5-turbo"):
        if api_type.lower() == "openai":
            self.client = OpenAIClient(model)
        elif api_type.lower() == "anthropic":
            self.client = AnthropicClient(model)
        else:
            raise ValueError("Invalid api_type. Choose 'openai' or 'anthropic'.")

    def check_definition(self, word, definition, language):
        # Step 1: Basic checks
        if self.basic_check(word, definition, language):
            return True
        
        # Step 2: LLM audit
        return self.llm_audit(word, definition, language)

    def basic_check(self, word, definition, language):
        # Simple string matching
        if word.lower() in definition.lower():
            return False
        
        # Stemming (if supported for the language)
        try:
            stemmer = SnowballStemmer(language)
            word_stem = stemmer.stem(word)
            def_words = re.findall(r'\w+', definition.lower())
            if any(stemmer.stem(w) == word_stem for w in def_words):
                return False
        except:
            pass  # Stemming not supported for this language
        
        return True

    def llm_audit(self, word, definition, language):
        prompt = f"""
        Language: {language}
        Word being defined: {word}
        Definition: {definition}

        Task: Analyze the definition and determine if it inappropriately uses the word being defined or any closely related forms. Consider conjugations, declensions, compounds, and semantic similarities. If issues are found, suggest alternatives.

        Output your analysis in JSON format with these keys:
        - valid: boolean indicating if the definition is valid
        - issues: list of any problematic words or phrases found
        - suggestions: list of suggested fixes if issues were found

        JSON response:
        """

        messages = [
            {"role": "system", "content": "You are an expert lexicographer tasked with auditing definitions."},
            {"role": "user", "content": prompt}
        ]

        result = self.client.create_chat_completion(messages)
        return result['valid']

# Usage
if __name__ == "__main__":
    checker = DefinitionChecker(api_type="anthropic", model="claude-3-sonnet-20240229")
    # Or use OpenAI: checker = DefinitionChecker(api_type="openai", model="gpt-3.5-turbo")

    word = "run"
    definition = "To move swiftly on foot, where the feet leave the ground for an instant between steps."
    language = "english"

    is_valid = checker.check_definition(word, definition, language)
    print(f"Definition is valid: {is_valid}")