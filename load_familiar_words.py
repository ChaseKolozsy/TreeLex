from definition_generator import DefinitionGenerator
import sys

def process_text_file(file_path):
    # Create an instance of DefinitionGenerator
    definition_generator = DefinitionGenerator(list_filepath=file_path)
    
    # Run the generator and mark all words as familiar
    definition_generator.run(familiar=True)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_definition_generator.py <path_to_text_file>")
    else:
        text_file_path = sys.argv[1]
        process_text_file(text_file_path)