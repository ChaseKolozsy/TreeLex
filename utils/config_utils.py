import json
import yaml

def load_config(config_path):
    with open(config_path, 'r') as file:
        if config_path.suffix == '.yaml' or config_path.suffix == '.yml':
            return yaml.safe_load(file)
        elif config_path.suffix == '.json':
            return json.load(file)
        else:
            raise ValueError("Unsupported configuration file format")