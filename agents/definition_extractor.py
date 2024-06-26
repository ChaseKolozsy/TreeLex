import json
import logging
from pathlib import Path
from utils.api_clients import OpenAIClient, AnthropicClient
from utils.definition_utils import get_enumeration, add_definition_to_db, split_dictionary_content

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

advanced_model = "claude-3-5-sonnet-20240620"
affordable_model = "claude-3-haiku-20240307"

class DefinitionExtractor:
    def __init__(self, language="English", api_type="anthropic", model=affordable_model):
        self.language = language
        self.api_type = api_type
        self.model = model
        self.client = self._create_client()
        self.max_retries = 3
        self.data_dir = Path("data")
        if not Path.exists(self.data_dir):
            Path.mkdir(self.data_dir, parents=True)

        self.example_input_file = self.data_dir / "definitions" / "japanese_example.txt"
        self.example_output_file = self.data_dir / "definitions" / "example_output.json"

        with open(self.example_input_file, "r") as f:
            self.example_input = f.read()
        
        with open(self.example_output_file, "r") as f:
            self.example_output = json.load(f)

        self.system_message = (
            "You are an AI assistant specialized in extracting definitions from dictionary entries. "
            "Your task is to analyze the input, which contains a dictionary entry, and output a structured JSON object "
            "containing all definitions, their parts of speech, and example phrases if available."
            f"Here's an example of the input you'll receive: {self.example_input}\n\n"
            f"And here's an example of the output you should produce: {self.example_output}\n\n"
            "Please follow these guidelines:\n"
            "1. Extract all definitions for the given word and assume all defintions are for the provided word.\n"
            "2. Include the part of speech for each definition.\n"
            "3. Include example phrases if they are provided in the dictionary entry.\n"
            "4. Output the result as a JSON object with the following structure:\n"
            "   {\n"
            "     \"word\": \"provided_word\",\n"
            "     \"definitions\": [\n"
            "       {\n"
            "         \"def\": \"First definition\",\n"
            "         \"pos\": \"part of speech\",\n"
            "         \"phrase\": \"Example phrase (if available)\"\n"
            "       },\n"
            "       ...\n"
            "     ]\n"
            "   }\n"
            "Output the result as a JSON object. Do not include any commentary. Strictly output JSON."
        )

    def _create_client(self):
        if self.api_type.lower() == "openai":
            return OpenAIClient(self.model)
        elif self.api_type.lower() == "anthropic":
            return AnthropicClient(self.model)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")

    def extract_definitions(self, word, dictionary_entry):
        retries = 0
        while retries < self.max_retries:
            try:
                message = {
                    "role": "user",
                    "content": f"Please extract definitions from the following dictionary entry:\n\n{dictionary_entry} for word {word}."
                }
                
                if self.api_type == "openai":
                    response = self.client.create_chat_completion([{"role": "system", "content": self.system_message}, message], system=None)
                else:
                    response = self.client.create_chat_completion([message], system=self.system_message)

                extracted_data = json.loads(response)
                return extracted_data
            except Exception as e:
                logging.error(f"Error extracting definitions: {e}")
                retries += 1
                if retries == self.max_retries:
                    raise Exception("Max retries reached. Unable to extract definitions.")

    def process_definitions(self, word, extracted_data):
        definitions = extracted_data["definitions"]
        entries = []

        for definition in definitions:
            entry = {
                "base_lemma": word,
                "part_of_speech": definition["pos"],
                "definition": definition["def"],
                "phrase": definition.get("phrase", "")
            }
            try:
                enumeration = word + '_' + get_enumeration(word)
            except Exception as e:
                logging.error(f"{e}: initializing first entry.")
                enumeration = word + "_1"
                entry["enumeration"] = enumeration
                entries.append(entry)
                add_definition_to_db(entries)

            entry["enumeration"] = enumeration
            entries.append(entry)
        add_definition_to_db(entries)
        return entries

    def run(self, word, dictionary_entry):
        dictionary_entry = split_dictionary_content(dictionary_entry)
        processed_entries = []
        try:
            for part in dictionary_entry:
                extracted_data = self.extract_definitions(word, part)
                logging.info("Definitions extracted successfully")
                processed_entries.extend(self.process_definitions(word, extracted_data))
                logging.info("Definitions processed and added to the database")
            return processed_entries
        except Exception as e:
            logging.error(f"Failed to extract or process definitions: {e}")
            return None

if __name__ == "__main__":
    # Example usage
    extractor = DefinitionExtractor()
    with open("data/definitions/hungarian_example.txt", "r") as f:
        word = f.readline().strip()
        sample_entry = f.read()

    results = extractor.run(word, sample_entry)
    for result in results:
        print(json.dumps(result, indent=2, ensure_ascii=False))