import json
import logging
from pathlib import Path
from utils.api_clients import OpenAIClient, AnthropicClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(funcName)s')

advanced_model = "claude-3-5-sonnet-20240620"
affordable_model = "claude-3-haiku-20240307"

class DictEntryAnalyzer:
    def __init__(self, language, native_language, api_type="anthropic", model=advanced_model):
        self.language = language
        self.native_language = native_language
        self.api_type = api_type
        self.model = model
        self.client = self._create_client()
        self.max_retries = 3
        self.data_dir = Path("data/")

        self.example_input_file = self.data_dir / "definitions" / "japanese_example.txt"

        with open(self.example_input_file, "r") as f:
            self.example_input_no_split = f.read()
        
        self.example_output_no_split = {
            "primary_definitions": 6,
            "estimated_total_definitions": 6,
            "extremely_liberal_def_estimate": 6,
            "split": False
        }

        self.base_instructions = f"""
            You are an assistant that analyzes dictionary entries. Given a word and its dictionary entry, you will:
            1. Count the total number of primary definitions.
            2. Count the number of all other possible definitions (synonyms, archaic definitions, etc.) 
            3. Err on the side of adding more definitions. Be extremely liberal. If you see an enumeration, count it as a definition.
            4. An entry should be split if it contains more than 20 possible definitions. 

            Input will be in this format:
            {json.dumps(self.example_input_no_split, indent=2, ensure_ascii=False)}

            Your output should be strictly in JSON format like this:
            {json.dumps(self.example_output_no_split, indent=2, ensure_ascii=False)}

            Ensure your response is valid JSON and includes all required fields. Supply no commentary, strictly JSON.
        """

        self.system_message = self.base_instructions
        self.base_message = {
            "role": "system",
            "content": self.system_message
        }

        if self.api_type == "openai":
            self.messages = [self.base_message]
        else:
            self.messages = []

    def _create_client(self):
        if self.api_type.lower() == "openai":
            return OpenAIClient(self.model)
        elif self.api_type.lower() == "anthropic":
            return AnthropicClient(self.model)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")

    def analyze_entry(self, word, entry):
        input_data = {
            "word": word,
            "entry": entry
        }
        message = {"role": "user", "content": json.dumps(input_data, indent=2)}
        self.messages.append(message)

        retries = 0
        while retries < self.max_retries:
            try:
                if self.api_type == "openai":
                    response = self.client.create_chat_completion(self.messages, system=None)
                else:
                    response = self.client.create_chat_completion(self.messages, system=self.system_message)

                analysis = json.loads(response)
                return analysis
            except Exception as e:
                logging.error(f"Error analyzing entry: {e}")
                retries += 1

        logging.error("Max retries reached. Unable to analyze entry.")
        return None

    def run(self, word, entry):
        if self.api_type == "openai":
            self.messages = [self.base_message]
        else:
            self.messages = []
        
        return self.analyze_entry(word, entry)

if __name__ == "__main__":
    analyzer = DictEntryAnalyzer(language="Hungarian", native_language="English")
    print(analyzer.system_message)
    with open("data/definitions/hungarian_example.txt", "r") as f:
        word = f.readline().strip()
        sample_entry = f.read()
    result = analyzer.run(word, sample_entry)
    with open("data/definitions/tmp/entry_info.json", "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    #print(json.dumps(result, indent=2, ensure_ascii=False))
