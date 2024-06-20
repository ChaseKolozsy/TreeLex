
import json
import re
import yaml
from pathlib import Path

def extract_definitions(text):
    data = json.loads(text)
    base_lemma = data.get("base_lemma")
    definitions = data.get("definitions", [])

    extracted_data = []
    for definition in definitions:
        enumerated_lemma = definition.get("enumerated_lemma")
        definition_text = definition.get("definition")
        part_of_speech = definition.get("part_of_speech")

        extracted_data.append({
            "Base Lemma": base_lemma,
            "Enumerated Lemma": enumerated_lemma,
            "Definition": definition_text,
            "Part of Speech": part_of_speech
        })

    return extracted_data

def preprocess_text(text):
    # Remove specified punctuation marks using regular expressions
    text = re.sub(r'[,:;.\-?!\']', '', text)
    return text

def load_config(config_path):
    with open(config_path, 'r') as file:
        if config_path.suffix == '.yaml' or config_path.suffix == '.yml':
            return yaml.safe_load(file)
        elif config_path.suffix == '.json':
            return json.load(file)
        else:
            raise ValueError("Unsupported configuration file format")