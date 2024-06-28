import importlib
import json
from pathlib import Path

class DictionaryLoader:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)

    def load_dictionary(self, language):
        config_file = self.dict_config_dir / f"{language}_config.json"
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file for {language} not found")

        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        protocol_class = self.load_protocol_class(config['protocol'])
        return protocol_class(config)

    def load_protocol_class(self, protocol_name):
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