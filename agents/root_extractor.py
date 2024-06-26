import json
import logging
from utils.api_clients import OpenAIClient, AnthropicClient
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

advanced_model = "claude-3-5-sonnet-20240620"
affordable_model = "claude-3-haiku-20240307"

class RootExtractor:
    def __init__(self, language="English", api_type="anthropic", model=affordable_model):
        self.language = language
        self.api_type = api_type
        self.model = model
        self.client = self._create_client()
        self.max_retries = 3
        self.data_dir = Path("data/roots/")
        if not Path.exists(self.data_dir):
            Path.mkdir(self.data_dir, parents=True)

        self.example_input_file = self.data_dir / "example_input.txt"
        self.example_output_file = self.data_dir / "example_output.json"

        with open(self.example_input_file, "r") as f:
            self.example_input = f.read()
        
        with open(self.example_output_file, "r") as f:
            self.example_output = json.load(f)


        self.system_message = (
            "You are an AI assistant specialized in extracting structured schema information from HTML class data. "
            "Your task is to analyze the input, which contains information about HTML classes, their hierarchy, and content, "
            "and output the root class that contains the majority of the dictionary information."
            f"Here's an example of the input you'll receive: {self.example_input}\n\n"
            f"And here's an example of the output you should produce: {self.example_output}\n\n"
            "Please follow these guidelines:\n"
            "1. Identify the root class.\n"
            "2. Identify the hierarchical structure based on the 'depth' and 'parent_classes' information.\n"
            "3. Ignore classes that are not relevant to dictionary entries (e.g. ads, footer, header, navigation, etc.).\n"
            "4. Find the deepest class that contains the majority of the dictionary information.\n"
            "Output the result as a JSON object. Do not include any commentary. Strictly output JSON."
        )

    def _create_client(self):
        if self.api_type.lower() == "openai":
            return OpenAIClient(self.model)
        elif self.api_type.lower() == "anthropic":
            return AnthropicClient(self.model)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")

    def extract_root(self, class_samples):
        retries = 0
        while retries < self.max_retries:
            try:
                message = {
                    "role": "user",
                    "content": f"Please analyze the following HTML class data and produce a structured schema:\n\n{json.dumps(class_samples, indent=2)}"
                }
                
                if self.api_type == "openai":
                    response = self.client.create_chat_completion([{"role": "system", "content": self.system_message}, message], system=None)
                else:
                    response = self.client.create_chat_completion([message], system=self.system_message)

                schema = json.loads(response)
                return schema
            except Exception as e:
                logging.error(f"Error extracting schema: {e}")
                retries += 1
                if retries == self.max_retries:
                    raise Exception("Max retries reached. Unable to extract schema.")

    def run(self, class_samples):
        try:
            schema = self.extract_schema(class_samples)
            logging.info("Schema extracted successfully")
            return schema
        except Exception as e:
            logging.error(f"Failed to extract schema: {e}")
            return None

if __name__ == "__main__":
    # Example usage
    extractor = RootExtractor()
    with open("data/roots/dictionary_fields.json", "r") as f:
        sample_input = json.load(f)