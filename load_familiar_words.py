from matcher import Matcher
from definition_generator import DefinitionGenerator
from pathlib import Path
import sys
import logging

def process_text_file(file_path, language="Hungarian", native_language="English"):
    list_filepath = file_path
    logging.info(f"list_filepath: {list_filepath}")

    #definition_generator = DefinitionGenerator(
    #    list_filepath=list_filepath,
    #    language=language,
    #    native_language=native_language
    #)
    #definition_generator.run()

    matcher = Matcher(
        language=language,
        native_language=native_language,
        list_filepath=list_filepath
    )
    matcher.run()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python run_definition_generator.py <path_to_text_file> <language> <native_language>")
    else:
        text_file_path = sys.argv[1]
        language = sys.argv[2]
        native_language = sys.argv[3]
        logging.info(f"text_file_path: {text_file_path}")
        logging.info(f"language: {language}")
        logging.info(f"native_language: {native_language}")
        process_text_file(text_file_path, language=language, native_language=native_language)