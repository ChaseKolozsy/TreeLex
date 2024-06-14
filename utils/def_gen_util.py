
import json
import re

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