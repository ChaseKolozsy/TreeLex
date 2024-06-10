# TreeLex
A Branching Logic and Definition Generation Tool

## Objective
To generate definitions for words, manage the creation of branches, and handle recursive definitions and circular definition checks.

## Responsibilities
- Interact with the WordWebDB_API to fetch and store definitions and branches.
- Generate definitions using GPT-3.5 or other AI models.
- Implement branching logic to create, complete, and validate branches.
- Check for and handle circular definitions.
- Provide a user interface or API for initiating definition generation and branch creation.

## Components
- **Definition Generator**: Module to generate word definitions using an AI model.
- **Branch Manager**: Module to manage in-memory branches, check for circular definitions, and ensure branch completion.
- **WordWebDB_Client**: Module to interact with WordWebDB_API for data storage and retrieval.
- **WordWebDB_API**: Flask application to serve the API to modify the WordWebDB.
- **Controller**: Flask application or script to orchestrate the definition generation and branching process.

## Directory Structure

```
BranchingTool/
├── Dockerfile
├── docker-compose.yml
├── app.py
├── definition_generator.py
├── branch_manager.py
├── api
│   ├── Dockerfile
│   ├── README.md
│   ├── app.py
│   ├── blueprint_Enumerated_Lemmas.py
│   ├── blueprint_Phrases.py
│   ├── models.py
│   ├── requirements.txt
│   └── .env
├── client
│   ├── src
│   │   ├── operations
│   │   │   ├── app_ops.py
│   │   │   ├── enumerated_lemma_ops.py
│   │   │   ├── phrase_ops.py
│   ├── requirements.txt
│   └── .env
└── .env
```


## Workflow

### Generate Definitions
1. Use the `definition_generator.py` to generate definitions for a given lemma.
2. Store the generated definitions in the WordWebDB_API via API calls.

### Manage Branches
1. Use the `branch_manager.py` to manage the current branch in memory.
2. Check for circular definitions and ensure the branch is complete.
3. Once complete, store the branch structure in the WordWebDB_API.

### API Client
1. Use the `wordwebdb_client.py` to interact with the WordWebDB_API.
2. Fetch existing definitions and store new definitions and branches.

## Example Docker Compose Setup
Here is an example `docker-compose.yml` setup to run both components in separate containers and enable communication between them:

```
services:
  wordwebdb_api:
    build: ./api
    container_name: wordwebdb_api
    ports:
      - "5001:5001"
    depends_on:
      - postgres

  treelex:
    build: .
    container_name: treelex
    ports:
      - "5002:5002"
    depends_on:
      - postgres

  postgres:
    image: postgres:latest
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
  ```
