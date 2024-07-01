import json
import yaml
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(funcName)s')

def load_config(config_path):
    with open(config_path, 'r') as file:
        if config_path.suffix == '.yaml' or config_path.suffix == '.yml':
            return yaml.safe_load(file)
        elif config_path.suffix == '.json':
            return json.load(file)
        else:
            raise ValueError("Unsupported configuration file format")

def preprocess_text(text):
    # Remove specified punctuation marks using regular expressions
    text = re.sub(r'[,:;.\-?!\']', '', text)
    return text


def save_to_file(data, filename='data/schema_extractor/dictionary_fields.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_json_from_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)