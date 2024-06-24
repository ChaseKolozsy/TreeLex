import pickle
import os
import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from urllib.parse import urlparse
from collections import defaultdict
from utils.general_utils import load_config
import time
from pathlib import Path
from utils.definition_utils import get_class_samples 

def save_session(session, filename='session.pkl'):
    with open(filename, 'wb') as f:
        pickle.dump(session, f)

def load_session(filename='session.pkl'):
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)
    return None

def get_session(filename='session.pkl', login_url='https://szotudastar.hu/'):
   session = load_session(filename)
   if session:
        # Test if the session is still valid
        response = session.get(login_url)
        
        # Check for elements that indicate a logged-in state
        soup = BeautifulSoup(response.text, 'html.parser')
        login_form = soup.find('form', {'id': 'login'})
        
        if not login_form:  # If there's no login form, we're likely logged in
            print("Loaded existing session")
            return session
        else:
            print("Existing session expired, creating new session")

def wp_login(login_url, username, password, session_file='session.pkl'):
    session = get_session(session_file, login_url)
    if session:
        return session

    # If no valid session, create a new one
    session = requests.Session()
    login_page = session.get(login_url)
    login_page.raise_for_status()

    soup = BeautifulSoup(login_page.text, 'html.parser')
    
    # Find the login form
    login_form = soup.find('form', {'id': 'login'})
    if not login_form:
        raise Exception("Login form not found")

    # Extract the redirect_to value
    redirect_to = login_form.find('input', {'name': 'redirect_to'})['value']

    login_data = {
        'log': username,
        'pwd': password,
        'redirect_to': redirect_to,
    }

    # The actual login URL might be different from the page URL
    login_action_url = login_form['action']
    
    # Use urljoin to handle relative URLs
    login_action_url = urljoin(login_url, login_action_url)
    
    login_response = session.post(login_action_url, data=login_data)
    login_response.raise_for_status()

    # Check if login was successful
    if "Login failed" in login_response.text or "login_error" in login_response.url:
        raise Exception("Login failed")

    # Save the new session
    save_session(session, session_file)
    print("Created and saved new session")

    return session

def scrape_dictionary(urls, session):
    all_fields = defaultdict(set)
    
    for url in urls:
        try:
            # Use the session to access the dictionary page
            dictionary_page = session.get(url)
            dictionary_page.raise_for_status()
            soup = BeautifulSoup(dictionary_page.text, 'html.parser')

            # Rest of the scraping logic remains the same
            body = soup.find('body')
            class_samples = get_class_samples(body)
            print(len(class_samples))
            for cls in class_samples:
                print(json.dumps(cls, indent=2, ensure_ascii=False))
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
        time.sleep(1)

    ## Convert sets to lists for JSON serialization
    #return {k: list(v) for k, v in all_fields.items()}
    

def save_to_file(data, filename='dictionary_fields.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    current_dir = Path(__file__).parent
    data_dir = current_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)

    config = load_config(data_dir / "online_dict_credentials.yaml")

    login_url = config['login_url']
    username = config['username']
    password = config['password']
    session_file = data_dir / "session.pkl"

    # Example usage
    urls = [
        'https://szotudastar.hu/?primarydict&uid=307&q=egy',
    ]

    session = get_session(session_file, login_url)
    if not session:
        session = wp_login(login_url, username, password, session_file)
    fields = scrape_dictionary(urls, session)
    #save_to_file(fields)
    #print("Fields have been saved to dictionary_fields.json")