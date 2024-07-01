import json
import json
from utils.general_utils import save_to_file, load_json_from_file
from pathlib import Path
from utils.web_scraping_utils import scrape_dictionary_for_fields
from agents.root_extractor import RootExtractor

class GeneralProtocol:
    def __init__(self, config, data_dir):
        self._session = None
        self.data_dir = Path(data_dir)

        self.config = config
        self.base_url = config['base_url']
        self.html_exclusions = config['html_exclusions']
        self.urls = config['urls']
        self.fields_path = Path(config['data_files']['fields'])

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

            samples = scrape_dictionary_for_fields(self.urls)
            save_to_file(samples, dict_dir / self.fields_path)

            root_extractor = RootExtractor()
            self._target_root = root_extractor.extract_root(samples)

            with open(roots_dir / self.target_root_path, "w") as f:
                json.dump(self._target_root, f, indent=2, ensure_ascii=False)
        
    def get_url(self, word):
        return self.base_url.format(word)

    def get_target_root(self):
        return self._target_root['root']['class']

    def login(self):
        return self._session
    
    def get_html_exclusions(self):
        return self.html_exclusions

if __name__ == "__main__":
    config = load_json_from_file("data/dict_configs/Japanese_dict_config.json")
    protocol = GeneralProtocol(config)
    urls = [
        "https://dictionary.goo.ne.jp/word/気持",
        "https://dictionary.goo.ne.jp/word/調べる"
    ]
    #dict_name = "goo"
    protocol.setup()
    print(protocol.get_target_root())
    print(protocol.get_html_exclusions())
    print(protocol.get_url("気持"))
    print(protocol.login())

    ## Iterate over the attributes of the protocol object
    #for attr_name in dir(protocol):
    #    # Get the value of the attribute using getattr
    #    attr_value = getattr(protocol, attr_name)
    #    # Print the attribute name and its value
    #    print(f"Attribute: {attr_name}, Value: {attr_value}")