import json
import logging
from lexiwebdb.client.src.operations import enumerated_lemma_ops

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

def pos_do_not_match(base_lemmas, pos):
    at_least_one_match = False  # Assume no lemmas match initially
    logging.info(f"\n------- base_lemmas: {base_lemmas} -----\n")
    for lemma in base_lemmas:
        logging.info(f"\n------- lemma: {lemma} -----\n")
        if lemma['part_of_speech'] == pos:
            at_least_one_match = True
            break  # Exit the loop as soon as a mismatch is found
    return not at_least_one_match  # Return True if there is no match

def matches_by_pos(base_lemmas, pos):
    matches = []
    for lemma in base_lemmas:
        if lemma['part_of_speech'] == pos:
            matches.append(lemma)
    return matches

def find_pos_in_phrase_info(word, phrase_info):
    """
    Find the part of speech for a given word in the phrase_info structure.

    :param word: The word to find.
    :param phrase_info: The phrase_info structure containing tokens.
    :return: The part of speech of the word if found, otherwise None.
    """
    for sentence in phrase_info:
        for token in sentence.get("tokens", []):
            if token.get("text") == word:
                return token.get("pos")
    return None

def get_enumeration(word):
    response = enumerated_lemma_ops.get_enumerated_lemma_by_base_lemma(word.lower())
    if response.status_code == 200:
        enumerated_lemmas = response.json()['enumerated_lemmas']
        return str(int(enumerated_lemmas[-1]['enumerated_lemma'].split('_')[1]) + 1)
    else:
        logging.info(f"No Base lemma found for word: {word}")
    
    return None


def add_definition_to_db(entry):
    logging.info(json.dumps(entry, indent=4, ensure_ascii=False))
    data = {
        'enumerated_lemma': entry['enumeration'].lower(),
        'base_lemma': entry['base_lemma'].lower(),
        'part_of_speech': entry['part_of_speech'],
        'definition': entry['definition'],
        'english_translation': '',
        'frequency': 0,  # Assuming initial frequency is 0
        'phrases': entry.get('phrases', []),  
        'story_link': '',  # Assuming no story link is provided
        'media_references': [],  # Assuming no media references are provided
        'object_exploration_link': '',  # Assuming no object exploration link is provided
        'familiar': False,  # Assuming not familiar initially
        'active': False,  # Assuming not active by default
        'anki_card_ids': [] # Assuming no anki card ids are provided
    }
    try:
        response = enumerated_lemma_ops.create_enumerated_lemma(data=data)
        logging.info(json.dumps(response.json(), indent=4))
    except Exception as e:
        logging.error(f"Error creating enumerated lemma: {e}")
        if "Enumerated Lemma already exists" in str(e):
            data['enumerated_lemma'] = data['base_lemma'] + '_' + str(int(data['enumerated_lemma'].split('_')[1]) + 10)
            response = enumerated_lemma_ops.create_enumerated_lemma(data=data)
            logging.info(json.dumps(response.json(), indent=4))

def split_dictionary_content(content, target_lines=100, tolerance=25):
    lines = content.split('\n')
    parts = []
    current_part = []
    line_count = 0
    base_level = min(len(line) - len(line.lstrip('\t')) for line in lines if line.strip())

    for line in lines:
        current_part.append(line)
        line_count += 1

        # Check if we're at a potential split point
        if line.strip() and len(line) - len(line.lstrip('\t')) == base_level + 1:
            if line_count >= target_lines - tolerance:
                parts.append('\n'.join(current_part))
                current_part = []
                line_count = 0
        
        # If we've exceeded the upper limit, force a split at the next opportunity
        elif line_count >= target_lines + tolerance:
            if line.strip() and len(line) - len(line.lstrip('\t')) <= base_level + 1:
                parts.append('\n'.join(current_part))
                current_part = []
                line_count = 0

    # Add any remaining content to the last part
    if current_part:
        parts.append('\n'.join(current_part))

    return parts