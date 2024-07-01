import pickle
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s - %(filename)s - %(funcName)s')

def save_session(session, filename='session.pkl'):
    with open(filename, 'wb') as f:
        pickle.dump(session, f)

def load_session(filename='session.pkl'):
    if os.path.exists(filename):
        with open(filename, 'rb') as f:
            return pickle.load(f)
    return None