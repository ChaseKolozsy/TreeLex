import json
import yaml
import re

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