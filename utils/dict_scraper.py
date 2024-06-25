import requests
import json
from bs4 import BeautifulSoup
from pathlib import Path
from utils.web_scraping_utils import get_class_and_id_samples
from collections import OrderedDict
import time

def hash_dict(obj):
    """Create a hashable representation of an object, excluding 'text' field."""
    if isinstance(obj, dict):
        return tuple(sorted((k, hash_dict(v)) for k, v in obj.items() if k != 'text'))
    elif isinstance(obj, list):
        return tuple(hash_dict(e) for e in obj)
    else:
        return obj

def scrape_dictionary_for_fields(urls):
    all_samples = set()
    
    for url in urls:
        try:
            # Access the dictionary page
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            body = soup.find('body')
            class_samples = get_class_and_id_samples(body)
            # Convert each sample to a hashable representation and add to the set
            all_samples.update(hash_dict(sample) for sample in class_samples)
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
        time.sleep(1)

    # Convert the set of hashable representations back to a list of dictionaries
    unique_samples = [OrderedDict(sample) for sample in all_samples]

    print(f"Number of unique samples: {len(unique_samples)}")
    return unique_samples

def save_to_file(data, filename='data/roots/dictionary_fields.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    from agents.root_extractor import RootExtractor
    current_dir = Path(__file__).parent.parent
    data_dir = current_dir / "data/roots"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)

    # Example usage with a dictionary that doesn't require login
    # Replace these URLs with the actual dictionary URLs you want to scrape
    urls = [
        'https://dictionary.goo.ne.jp/word/調べる',
        'https://dictionary.goo.ne.jp/word/捜す',
        'https://dictionary.goo.ne.jp/word/履歴',
    ]

    samples = scrape_dictionary_for_fields(urls)
    save_to_file(samples)

    root_extractor = RootExtractor()
    root = root_extractor.extract_root(samples)
    
    # Save the extracted schema
    with open(data_dir / "general_dictionary_root.json", "w") as f:
        json.dump(root, f, indent=2, ensure_ascii=False)
