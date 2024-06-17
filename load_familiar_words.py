from matcher import Matcher
from pathlib import Path
import sys
import logging

def process_text_file(file_path):
    current_dir = Path.cwd()
    data_dir = current_dir / "data"
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
    logging.info(f"data_dir: {data_dir}")
    list_filepath = data_dir / "list.txt"

    matcher = Matcher(
        language="Hungarian",
        native_language="English",
        list_filepath=list_filepath
    )
    matcher.run()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_definition_generator.py <path_to_text_file>")
    else:
        text_file_path = sys.argv[1]
        process_text_file(text_file_path)