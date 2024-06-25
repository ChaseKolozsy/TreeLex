from bs4 import BeautifulSoup
import json
from typing import Dict, Any, List

class DictionaryExtractor:
    def __init__(self, html_content: str, schema_path: str):
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.schema = self._load_schema(schema_path)

    def _load_schema(self, schema_path: str) -> Dict[str, Any]:
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def extract(self) -> Dict[str, Any]:
        return self._extract_recursive(self.schema['root'], self.soup)

    def _extract_recursive(self, schema_node: Dict[str, Any], soup_element: BeautifulSoup) -> Dict[str, Any]:
        result = {}
        if 'class' in schema_node:
            elements = soup_element.find_all(class_=schema_node['class'])
            if elements:
                if 'content' in schema_node:
                    result[schema_node['content']] = [el.get_text(strip=True) for el in elements]
                if 'children' in schema_node:
                    for child in schema_node['children']:
                        for element in elements:
                            child_result = self._extract_recursive(child, element)
                            for key, value in child_result.items():
                                if key in result:
                                    result[key].extend(value)
                                else:
                                    result[key] = value
        return result

    def get_extracted_data(self) -> Dict[str, List[str]]:
        extracted_data = self.extract()
        # Flatten the structure and ensure all values are lists
        return {k: v if isinstance(v, list) else [v] for k, v in extracted_data.items()}