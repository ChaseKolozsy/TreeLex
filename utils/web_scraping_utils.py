import re
import json
from bs4 import NavigableString
from typing import Dict, List, Optional
from pathlib import Path
import requests
from utils.general_utils import load_config
from utils.dictionary_extractor import DictionaryExtractor

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

def fetch_dictionary_page(url: str, session: Optional[requests.Session] = None) -> str:
    if session:
        response = session.get(url)
    else:
        response = requests.get(url)
    response.raise_for_status()
    return response.text

def extract_dictionary_data(url: str, schema_path: str, exclusions: List[str], session: Optional[requests.Session] = None) -> Dict[str, List[str]]:
    html_content = fetch_dictionary_page(url, session)
    extractor = DictionaryExtractor(html_content, schema_path, exclusions)
    return extractor.get_extracted_data()

def get_or_create_session(config_path: str) -> Optional[requests.Session]:
    try:
        config = load_config(config_path)
        login_url = config['login_url']
        username = config['username']
        password = config['password']
        session_file = Path(config_path).parent / "session.pkl"

        session = get_session(session_file, login_url)
        if not session:
            session = wp_login(login_url, username, password, session_file)
        return session
    except Exception as e:
        print(f"Error creating session: {e}")
        print("Proceeding without a session.")
        return None

if __name__ == "__main__":
    from utils.wp_dict_scraper import get_session, wp_login
    current_dir = Path(__file__).parent.parent
    data_dir = current_dir / "data"
    config_path = data_dir / "online_dict_credentials.yaml"
    output_dir = data_dir / "web_scraping_utils"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Example URLs for different scenarios
    session_required_url = "https://szotudastar.hu/?primarydict&uid=307&q=szép"
    public_url = "https://dictionary.goo.ne.jp/word/調べる"

    schema_path = data_dir / "schema_extractor" / "dictionary_schema.json"

    # Try to get or create a session
    session = get_or_create_session(config_path)
    exclusions = ['szolas', 'osszetett']

    # Example with session (if available)
    if session:
        print("Extracting data from a page that requires login:")
        extracted_data = extract_dictionary_data(session_required_url, schema_path, exclusions, session)
        with open(output_dir / "session_required_data.html", "w") as f:
            f.write(extracted_data)

    # Example without session
    #print("\nExtracting data from a public page:")
    #extracted_data = extract_dictionary_data(public_url, schema_path)
    #with open(output_dir / "public_data.html", "w") as f:
    #    f.write(extracted_data)
