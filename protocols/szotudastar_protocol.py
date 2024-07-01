import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import json
from utils.general_utils import load_config, save_to_file
from pathlib import Path
from utils.web_scraping_utils import scrape_dictionary_for_fields
from utils.session_utils import save_session, load_session
from agents.root_extractor import RootExtractor
from utils.general_utils import load_json_from_file


class SzotudastarProtocol:
    def __init__(self, config, data_dir):
        self.config = config
        self.data_dir = Path(data_dir)
        self.login_url = config['login_url']
        self.session_file = config['session_file']
        self.credentials_file = Path(config['credentials_file'])
        self.urls = config['urls']
        self.base_url = config['base_url']
        self.fields_path = Path(config['data_files']['fields'])
        self.html_exclusions = config['html_exclusions']

        self.target_root_path = Path(config['data_files']['root'])
        if self.target_root_path.exists():
            self._target_root = load_json_from_file(self.target_root_path)
        else:
            self._target_root = None

    def setup(self):
        if not self._target_root:
            data_dir = self.data_dir
            roots_dir = data_dir / "roots"
            dict_dir = data_dir / self.config['name']

            if not data_dir.exists():
                data_dir.mkdir(parents=True)
            if not roots_dir.exists():
                roots_dir.mkdir(parents=True)
            if not dict_dir.exists():
                dict_dir.mkdir(parents=True)

            config = load_config(dict_dir / self.credentials_file)
            username = config['username']
            password = config['password']

            session = self.get_session()
            if not session:
                session = self.login(username, password)
            samples = scrape_dictionary_for_fields(self.urls, session)
            save_to_file(samples, dict_dir / self.fields_path)

            root_extractor = RootExtractor()
            self._target_root = root_extractor.extract_root(samples)

            with open(roots_dir / self.target_root_path, "w") as f:
                json.dump(self._target_root, f, indent=2, ensure_ascii=False)

    def login(self):
        session = self.get_session()
        if session:
            return session

        session = requests.Session()
        login_page = session.get(self.login_url)
        login_page.raise_for_status()



        config = load_config(self.credentials_file)
        username = config['username']
        password = config['password']

        soup = BeautifulSoup(login_page.text, 'html.parser')
        login_form = soup.find('form', {'id': 'login'})
        if not login_form:
            raise Exception("Login form not found")

        redirect_to = login_form.find('input', {'name': 'redirect_to'})['value']

        login_data = {
            'log': username,
            'pwd': password,
            'redirect_to': redirect_to,
        }

        login_action_url = login_form['action']
        login_action_url = urljoin(self.login_url, login_action_url)

        login_response = session.post(login_action_url, data=login_data)
        login_response.raise_for_status()

        if "Login failed" in login_response.text or "login_error" in login_response.url:
            raise Exception("Login failed")

        save_session(session, self.session_file)
        print("Created and saved new session")

        return session

    def get_session(self):
        session = load_session(self.session_file)
        if session:
            response = session.get(self.login_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            login_form = soup.find('form', {'id': 'login'})
            if not login_form:
                print("Loaded existing session")
                return session
            else:
                print("Existing session expired, creating new session")

    def get_url(self, word):
        return self.base_url.format(word)

    def get_html_exclusions(self):
        return self.html_exclusions

    def get_target_root(self):
        return self._target_root['root']['class']

if __name__ == "__main__":
    config = load_json_from_file("data/dict_configs/Hungarian_dict_config.json")
    protocol = SzotudastarProtocol(config, "data")
    protocol.setup()

    print(protocol.get_target_root())
    print(protocol.get_html_exclusions())
    print(protocol.get_url("kép"))

    ## Iterate over the attributes of the protocol object
    #for attr_name in dir(protocol):
    #    # Get the value of the attribute using getattr
    #    attr_value = getattr(protocol, attr_name)
    #    # Print the attribute name and its value
    #    print(f"Attribute: {attr_name}, Value: {attr_value}")