import importlib
import json
from pathlib import Path
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(funcName)s')

class DictionaryLoader:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.dict_config_dir = self.data_dir / "dict_configs"

    def load_dictionary(self, language):
        config_file = self.dict_config_dir / f"{language}_dict_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file for {language} not found")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        protocol_class = self.load_protocol_class(config['protocol'], config)
        return protocol_class(config, self.data_dir)

    def load_protocol_class(self, protocol_name, config):
        if 'login_url' not in config or 'credentials_file' not in config:
            protocol_name = "general"
        module = importlib.import_module(f"protocols.{protocol_name}_protocol")
        return getattr(module, f"{protocol_name.capitalize()}Protocol")

    def setup_dictionary(self, config, data_dir):
        dict_name = config['name']
        config_file = self.data_dir / dict_name / f"{dict_name}_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        protocol_class = self.load_protocol_class(config['protocol'])
        protocol_instance = protocol_class(config, data_dir)
        protocol_instance.setup()

    def determine_protocol(self, dict_name):
        # This method should determine which protocol to use based on the dictionary name
        # For now, we'll just return a default protocol
        return "general"

if __name__ == "__main__":
    hungarian_loader = DictionaryLoader()
    protocol = hungarian_loader.load_dictionary("Hungarian")
    protocol.setup()
    print(protocol.get_url("kép"))

    japanese_loader = DictionaryLoader()
    protocol = japanese_loader.load_dictionary("Japanese")
    protocol.setup()
    print(protocol.get_url("気持"))