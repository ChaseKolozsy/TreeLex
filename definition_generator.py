import client.src.operations.app_ops as app_ops
import client.src.operations.attribute_ops as attribute_ops
import client.src.operations.branch_node_ops as branch_node_ops
import client.src.operations.branch_ops as branch_ops
import client.src.operations.grammar_ops as grammar_ops
import client.src.operations.object_ops as object_ops
import client.src.operations.phrase_ops as phrase_ops
import client.src.operations.routine_ops as routine_ops
import client.src.operations.state_ops as state_ops
import client.src.operations.verb_ops as verb_ops

from api.models import Enumerated_Lemmas
import client.src.operations.enumerated_lemma_ops as enumerated_lemma_ops
import openai


import json
import time
import logging
from datetime import datetime
from pathlib import Path
import re

def preprocess_text(text):
    # Remove specified punctuation marks using regular expressions
    text = re.sub(r'[,:;.\-?!\']', '', text)
    return text


class DefinitionGenerator:
    """
    """
    def __init__(self, list_filepath, language='Hungarian', filepath_ids='nursery_ids.txt', model="gpt-3.5-turbo-16k"):
        self.model = model
        self.client = openai.OpenAI()
        self.language = language
        self.assistant_id = None
        self.thread_id = None
        self.sleep_interval = 5  # seconds
        self.max_retries = 3
        self.filepath_ids = filepath_ids

        self.list_filepath = list_filepath
        self.definitions = []
        self.string_list = []
        self.missing_definitions = []
        self.instructions = "You are an expert lexicographer with a deep understanding " \
                            "of etymology and semantics. Your task is to provide clear, " \
                            "concise, and accurate definitions for words, ensuring that " \
                            "each definition captures the essence and nuances of the word. " \
                            f"You will be defining words in the {self.language} language, " \
                            "drawing on your extensive knowledge to offer precise and " \
                            "contextually appropriate explanations."

        self.is_phrase_list = False

    def create_assistant(self, language, instructions=None):
        """
        #######################################################################
        TLDR: creates the assistant and thread, saving their IDs for future reference.
        #######################################################################

        Creates a definition generation assistant and a thread, saving their
        IDs. It uses the provided language and instructions for configuring the
        assistant. The assistant's name reflects its purpose and target language.
        IDs are stored as instance variables and in a file for persistence.

        Parameters:
        - language (str): Language for definition generation, e.g., 'English'.
        - instructions (str): Description of the task for the assistant.

        Side Effects:
        - Initializes an assistant and a thread with OpenAI API, saving their IDs.
        - Writes the assistant and thread IDs to a file specified by
          'self.filepath_ids'.

        Returns:
        - None
        """
        if not instructions:
            instructions = self.instructions
        client = self.client
        self.assistant = client.beta.assistants.create(
                name=f"{language}_DefinitionGenerator",
                instructions=instructions,
                model=self.model
         )
        self.assistant_id = self.assistant.id
        self.thread = self.client.beta.threads.create(messages=[{"role": "user", "content": ""}])
        self.thread_id = self.thread.id

        with open(self.filepath_ids, 'w', encoding='utf-8') as f:
            f.write(f"{self.assistant_id}\n")
            f.write(f"{self.thread_id}\n")


    def initialize_assistant(self, instructions=None):
        """
        #######################################################################
        TLDR: loads assistant and thread ids from a file for pregenerated assistant
        #######################################################################

            Initializes the assistant by reading its ID and the thread ID from
            a file, preparing it for interaction based on predefined instructions.
            The method allows for updating the assistant's instructions dynamically
            if needed, setting them as an instance variable for future reference.
            It primarily focuses on setting up communication channels with the
            assistant by retrieving its ID and the associated thread ID from a
            persistent storage file specified by 'self.filepath_ids'.

            This method is essential for resuming interaction with an already
            created assistant and thread, ensuring that subsequent operations can
            leverage these IDs for communication with the OpenAI API.

            Parameters:
            - instructions (str, optional): Instructions for the assistant's task,
              defaulting to the instance's 'self.instructions' if not explicitly
              provided. This allows for dynamic adjustment of the assistant's
              operational context.

            Side effects:
            - Reads 'self.filepath_ids' to obtain and set 'self.assistant_id' and
              'self.thread_id' for use in API interactions.
            - Optionally updates 'self.instructions' based on the parameter provided,
              enhancing the adaptability of the assistant's task description.
            - Prints the assistant and thread IDs to the console for immediate
              verification, aiding in debugging and operational monitoring.
        """
        if not instructions:
            instructions = self.instructions
        with open(self.filepath_ids, 'r', encoding='utf-8') as f:
            self.assistant_id = f.readline().strip()
            self.thread_id = f.readline().strip()
            print(f'Assistant ID: {self.assistant_id}, Thread ID: {self.thread_id}')

    def load_list(self):
        """
        #######################################################################
        TLDR: 
            Loads the list of strings from a specified file.
            Each line in the file represents a separate string in the list.
        #######################################################################

        Loads a list of strings from a file specified by 'self.list_filepath'.

        This method reads each line from the specified file, treating each line as
        a separate string. It strips whitespace from the start and end of each line
        before adding it to 'self.string_list'. This list is used for further
        processing and operations within the NurseryRhymeGenerator class.

        Side effects:
        - Sets 'self.string_list' with the strings read from the file, where each
          string corresponds to a line in the file, with leading and trailing
          whitespace removed.
        """
        with open(self.list_filepath, 'r', encoding='utf-8') as file:
            self.string_list = [line.strip() for line in file.readlines()][3:]

    def analyze_list_content(self):
        """
        #######################################################################
        TLDR:
            Analyzes the list of strings to determine if they are 
            predominantly single words or phrases.
            Sets a flag to indicate if the list contains mostly phrases.
        #######################################################################

            Analyzes the list of strings to determine if they are predominantly 
            single words or phrases. Sets a flag to indicate if the list contains 
            mostly phrases.

            This method first checks if the list is not empty and contains more 
            than three items, as analysis starts from the fourth item. If the 
            list is too short, it assumes the list contains words and sets 
            'self.is_phrase_list' to False.

            For lists with more than three items, it counts how many of these 
            (starting from the fourth item) are phrases (defined as containing 
            more than one word). It then calculates the percentage of phrases 
            in the analyzed part of the list.

            If more than 50% of the analyzed items are phrases, 'self.is_phrase_list' 
            is set to True, indicating the list predominantly contains phrases. 
            Otherwise, it is set to False. The result of the analysis is printed 
            out.

            Side effects:
            - Sets 'self.is_phrase_list' based on whether the majority of the 
              list content are phrases or single words.
            - Outputs to console the result of the analysis.
        """
        # Ensure there's a list to analyze and it has more than 3 items (as we start analyzing from the 4th item)
        if not self.string_list or len(self.string_list) <= 3:
            print("List is too short to analyze. Assuming it contains words.")
            self.is_phrase_list = False
            return

        # Count how many items from the 4th one onward are phrases (i.e., contain more than one word)
        phrase_count = sum(1 for line in self.string_list[3:] if len(line.split()) > 1)

        # Calculate the percentage of phrases
        total_lines_to_analyze = len(self.string_list) - 3
        percentage_phrases = (phrase_count / total_lines_to_analyze) * 100

        # Set the flag based on whether more than 50% are phrases
        self.is_phrase_list = percentage_phrases > 50

        print(f"List analyzed. Contains {'mostly phrases' if self.is_phrase_list else 'mostly single words'}.")

    def create_definitions(self):
        """
        #######################################################################
        TLDR:
            Calls the DefinitionGenerator assistant to generate definitions
            from the list of strings.
        #######################################################################

            Invokes the DefinitionGenerator assistant to generate definitions
            using the provided list of strings as reference material. The method
            formats the string list into a single string with each item separated
            by newlines, then sends this formatted string as a prompt to the assistant
            within a message. Subsequently, it initiates a run to generate the definitions
            based on these instructions.

            The process involves creating a message in the assistant's thread with the
            reference material and starting a new run with specific instructions for
            definition creation. The method waits for the run to complete by calling
            'wait_for_run_completion', passing the thread and run IDs.

            Preconditions:
            - The assistant and thread should already be initialized and their IDs
              stored in 'self.assistant_id' and 'self.thread_id'.

            Postconditions:
            - Initiates the creation of definitions by the assistant and waits
              for completion.

            Side effects:
            - Sends a message to the assistant and starts a run in the OpenAI API,
              which may consume API quota.
            - Definitions are generated and their creation is awaited, potentially
              delaying the execution flow until completion.
        """
        # Prepare the reference material from the loaded string list
        reference = '\n'.join(self.string_list)
        message = f'Please create definitions for the following words: \n\n"""{reference}"""\n'
        message_response = self.client.beta.threads.messages.create(
            thread_id=self.thread_id,
            role="user",
            content=message
        )
        
        run = self.client.beta.threads.runs.create(
            thread_id=self.thread_id,
            assistant_id=self.assistant_id,
            instructions=self.instructions
        )
        response = self.wait_for_run_completion(self.thread_id, run.id)
        return response

    def wait_for_run_completion(self, thread_id, run_id):
        """
        #######################################################################
        TLDR:
            Waits for a run to complete and prints the elapsed time. Once completed,
            it retrieves the response and returns the response
        #######################################################################

            Polls the status of a specified run within a thread and waits until the run
            is completed. It regularly checks the run status at intervals defined by
            'sleep_interval'. Upon completion, it calculates and prints the total elapsed
            time, retrieves the final message from the thread (assumed to contain the
            generated nursery rhyme), and writes this content to the file specified by
            'self.nursery_rhyme_filepath'.

            Parameters:
            - thread_id (str): The ID of the thread containing the run.
            - run_id (str): The ID of the run to wait for completion.
            - sleep_interval (int, optional): The time in seconds between status checks.
              Defaults to 5 seconds.

            Preconditions:
            - A run should have been started in the specified thread, and both IDs
              should be correctly provided.

            Postconditions:
            - The method waits until the specified run is completed and returns the response

            Side effects:
            - Periodically sends requests to the OpenAI API, potentially consuming API
              quota.
            - Outputs the completion time to the console.
        """
        while True:
            try:
                run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
                if run.completed_at:
                    # Get messages here once Run is completed
                    messages = self.client.beta.threads.messages.list(thread_id=thread_id)
                    last_message = messages.data[0]
                    response = last_message.content[0].text.value
                    return response
            except Exception as e:
                logging.error(f"An error occurred while retrieving the run: {e}")

            time.sleep(self.sleep_interval)


    def run(self): 
        """
        #######################################################################
        TLDR:
            Orchestrates the entire process of generating, validating, and 
            revising nursery rhymes.
        #######################################################################

            Coordinates the full workflow for generating, assessing, and refining
            definitions based on a given list of strings or phrases. This method
            encapsulates the sequence of operations required to create definitions,
            perform validation through fuzzy matching, and incorporate any missing elements
            identified during the validation process into a revised version of the nursery rhyme.

            The workflow includes initializing the assistant and thread for communication with
            the Definition Generator, loading and analyzing the input list, setting up the
            connection to the database for storing the definitions, generating the initial 
            definitions. It further handles the inclusion of missing words in a given phrase
            that for some reason were not generated by the assistant.

            Preconditions:
            - 'self.list_filepath' should be set to the path of the file containing the list
              of strings or phrases for the nursery rhyme.
            - Necessary configurations and credentials for interacting with the 
              Definition Generator and any other utilized services should be correctly set up.

            Postconditions:
            - Generates an initial version of the definitions and stores them in the database.
            - Performs validation to identify and incorporate missing elements, resulting in a
              complete set of definitions.

            Side effects:
            - Interacts with external services (e.g., Definition Generator) to generate 
              definitions, potentially incurring processing time and resource usage.
            - Modifies the database by writing the generated definitions.
        """
        self.create_assistant(self.language)
        self.initialize_assistant()
        self.load_list()
        self.create_definitions()
        # TODO: validate the definitions
        # TODO: if there are missing definitions, ask assistant to generate them 
        # TODO: save the definitions to the database
