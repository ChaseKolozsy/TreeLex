import json
import re
import yaml
from pathlib import Path
import logging
from lexiwebdb.client.src.operations import enumerated_lemma_ops
from bs4 import BeautifulSoup, NavigableString

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


def add_definition_to_db(entries):
    for entry in entries:
        logging.info(json.dumps(entry, indent=4, ensure_ascii=False))
        data = {
            'enumerated_lemma': entry['enumeration'].lower(),
            'base_lemma': entry['base_lemma'].lower(),
            'part_of_speech': entry['part_of_speech'],
            'definition': entry['definition'],
            'english_translation': '',
            'frequency': 0,  # Assuming initial frequency is 0
            'phrase': '',  # Assuming no phrase is provided
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

def get_class_samples(soup):
    """
    Extract relevant class IDs from the BeautifulSoup object and return a list of samples with hierarchical information.

    :param soup: BeautifulSoup object
    :return: List of dictionaries containing class name, sample element, and hierarchical information
    """
    class_samples = {}
    
    # Patterns for exact matches or hyphenated classes
    exact_or_hyphenated = [
        r'(?:^|\b|-)(ad|ads|x|btn)(?:$|\b|-)',
    ]
    
    # Patterns for substring matches
    substring_patterns = [
        r'advertisement', r'banner', r'menu', r'nav', r'navigation', r'footer', r'header',
        r'sidebar', r'social', r'share', r'button', r'popup', r'modal', r'cookie', r'search',
        r'logo', r'branding', r'copyright', r'related', r'recommended', r'sponsored', r'widget',
        r'twitter', r'facebook', r'instagram', r'linkedin', r'pinterest', r'youtube', r'tiktok', 
        r'vimeo', r'close', r'search-icon', r'search-input', r'search-button'
    ]
    
    irrelevant_regex = re.compile('|'.join(exact_or_hyphenated + substring_patterns), re.IGNORECASE)

    def is_relevant(class_name, tag):
        if irrelevant_regex.search(class_name):
            return False
        if tag.name in ['script', 'style', 'noscript', 'iframe']:
            return False
        return True

    def process_tag(tag, depth=0, parent_classes=None):
        if isinstance(tag, NavigableString):
            return

        classes = tag.get('class', [])
        relevant_classes = [cls for cls in classes if is_relevant(cls, tag)]

        for class_name in relevant_classes:
            if class_name not in class_samples:
                text = tag.get_text(strip=True)
                if text:  # Only add if there's actual text content
                    class_samples[class_name] = {
                        'class': class_name,
                        'tag': tag.name,
                        'text': text[:50],  # First 50 characters of text
                        'attributes': {k: v for k, v in tag.attrs.items() if k != 'class'},
                        'depth': depth,
                        'parent_classes': [cls for cls in (parent_classes or []) if is_relevant(cls, tag)]
                    }

        for child in tag.children:
            if isinstance(child, NavigableString):
                continue
            process_tag(child, depth + 1, relevant_classes)

    # Start processing from the main content area if it exists, otherwise use the body
    main_content = soup.find(['main', 'article', 'div#content', 'div.content'])
    root = main_content if main_content else (soup.body if soup.body else soup)
    process_tag(root)

    return list(class_samples.values())