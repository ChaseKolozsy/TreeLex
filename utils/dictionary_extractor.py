from bs4 import BeautifulSoup
from typing import List, Union, Optional
import logging
import json


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(funcName)s')

class DictionaryExtractor:
    def __init__(self, html_content: str, target_root=None, exclusions: Optional[List[str]] = None):
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.exclusions = exclusions or []
        self.target_root = target_root

    def _load_schema(self, schema_path: str):
        with open(schema_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def extract(self):
        root = self.target_root
        root_element = self.soup.find(class_=root) or self.soup.find(id=root)
        if root_element:
            return html_to_tree(root_element.prettify(), self.exclusions)
        else:
            return html_to_tree(self.soup.find('body').prettify(), self.exclusions)

    def get_extracted_data(self):
        return self.extract()


def html_to_tree(html: str, exclusions: List[str] = []) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    return _process_element(soup.find(), 0, exclusions)

def _process_element(element: Union[BeautifulSoup, str], depth: int, exclusions: List[str]) -> str:
    if element is None:
        return ""

    result = []
    indent = "\t" * depth

    if isinstance(element, str):
        content = element.strip()
        if content:
            result.append(f"{indent}{content}")
    else:
        # Check if the element should be excluded
        if any(excl in (element.get('class', []) + [element.get('id', '')]) for excl in exclusions):
            return ""

        if element.get('class'):
            result.append(f"{indent}({' '.join(element.get('class'))})")
        
        for child in element.children:
            if isinstance(child, str):
                content = child.strip()
                if content:
                    result.append(f"{indent}\t{content}")
            else:
                result.append(_process_element(child, depth + 1, exclusions))

    return "\n".join(filter(None, result))

if __name__ == "__main__":
    # Example usage
    html_content = """
    <div class="result">
        <div class="entry ertelmezo">
            <div class="entryname">értelmező</div>
            <div class="ertelmezo">
                <span class="headword">szép</span>
                <span class="sense">I.</span>
                <span class="freq">5</span>
                <span class="pos">melléknév</span>
                <span class="conjugate">~ek, ~et, ~en</span>
                <ul>
                    <li>1. Tetszést keltő, gyönyörködtető. <i>Szép hangja van. Szép az arca és az alakja is. Szép ez a váza.</i></li>
                </ul>
            </div>
        </div>
        <div class="exclude-me">This should be excluded</div>
    </div>
    """

    # Example with exclusions
    exclusions = ['exclude-me', 'freq']
    tree = html_to_tree(html_content, exclusions)
    print(tree)

    # Example usage of DictionaryExtractor
    extractor = DictionaryExtractor(html_content, 'data/schema_extractor/dictionary_schema.json', exclusions)
    extracted_data = extractor.get_extracted_data()
    print(extracted_data)