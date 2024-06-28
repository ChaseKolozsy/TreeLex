import json
import json
from utils.general_utils import save_to_file, load_json_from_file
from pathlib import Path
from utils.web_scraping_utils import scrape_dictionary_for_fields
from agents.root_extractor import RootExtractor

class GeneralProtocol:
    def __init__(self, config):
        self.config = config
        self.base_url = config['base_url']
        self.target_root_path = Path(config['target_root_path'])
        if self.target_root_path.exists():
            self._target_root = load_json_from_file(self.target_root_path)
        else:
            self._target_root = None
        self._session = None

    def setup(self):
        if not self._target_root:
            current_dir = Path(__file__).parent.parent
            data_dir = current_dir / "data"
            roots_dir = data_dir / "roots"
            language_dir = data_dir / self.config['name']
            if not data_dir.exists():
                data_dir.mkdir(parents=True)
            if not roots_dir.exists():
                roots_dir.mkdir(parents=True)
            if not language_dir.exists():
                language_dir.mkdir(parents=True)

            samples = scrape_dictionary_for_fields(self.config['urls'])
            save_to_file(samples, language_dir / self.config['data_files']['fields'])

            root_extractor = RootExtractor()
            self._target_root = root_extractor.extract_root(samples)

            with open(roots_dir / self.config['data_files']['root'], "w") as f:
                json.dump(self._target_root, f, indent=2, ensure_ascii=False)
        
    def get_url(self, word):
        return self.base_url.format(word)

    def get_target_root(self):
        return self._target_root

    def login(self):
        return self._session

if __name__ == "__main__":
    protocol = GeneralProtocol()
    urls = [
        "https://dictionary.goo.ne.jp/word/気持",
        "https://dictionary.goo.ne.jp/word/調べる"
    ]
    dict_name = "goo"
    protocol.setup(dict_name, urls)