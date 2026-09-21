# AITHENA Eagle Eye

A locally hosted contract-intelligence prototype. Upload one or more PDF, PNG,
JPEG, DOCX, or TXT contracts—or a complete folder—to extract CUAD clauses,
model-grounded parties, explicit dates, deterministic fixed-term end dates, and
possible contradictions within or across related contracts, then persist them
in a normalized PostgreSQL schema. The frontend presents extracted events in a
monthly calendar, exports the same events as an `.ics` file, and provides a
linked conflict-review workspace.

## Run locally

1. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Start PostgreSQL. With Docker Compose installed:

   ```bash
   docker compose up -d postgres
   ```

   Alternatively, create a local PostgreSQL database and set `DATABASE_URL`
   using the format in `.env.example`.

3. Install and build the Svelte 5 TypeScript frontend:

   ```bash
   cd frontend
   npm install
   npm run build
   cd ..
   ```

4. Start the Flask server. The current database schema is created automatically:

   ```bash
   flask --app backend.app run --debug --port 8000
   ```

5. Open <http://127.0.0.1:8000>.

For frontend development with hot reloading, keep Flask running on port 8000
and run `npm run dev` from `frontend/`. Open <http://127.0.0.1:5173>; Vite
proxies `/api` requests to Flask.

Model weights, caches, virtual environments, and local database data are excluded
from Git. Installing requirements installs the Python libraries; Hugging Face
weights download automatically to `.models` when each extractor is first used.
The first upload needs internet access and may take several minutes while models
download. Subsequent uploads reuse the cached weights on that computer. Extraction
runs inside the local Python process; contract contents are not sent to model
providers.

## Delete all contract data

With PostgreSQL running through Compose, this command permanently deletes every
upload, contract, extracted text, clause, conflict, party, and date while
retaining the database schema. It uses the same `DATABASE_URL` as the Flask
application and reports how many top-level records it removed:

```bash
.venv/bin/flask --app backend.app reset-database --yes
```

Reload any open Eagle Eye browser tab after running the command; the frontend
keeps its current workspace in memory until the page is refreshed.

## Current storage model

Each upload selection is represented by an `upload_batches` row. Each file is
stored in `contracts`, with extracted results stored as rows in
`contract_clauses`, `contract_party_mentions`, and `contract_dates`. Exact
formatted text is retained in `contract_texts`; canonical entities and their
observed names are stored in `parties` and `party_aliases`. Dates use the native
PostgreSQL `date` type so calendar and range queries do not depend on formatted
JSON strings.

See [DOCS.md](DOCS.md) for the complete schema, extraction behavior, API, and
prototype limitations.

## Development checks

Keep the Compose PostgreSQL service running, install the development tools,
and run the complete local quality gate. Persistence tests use isolated
PostgreSQL schemas and remove them after each test.

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
python -m unittest discover -s tests -v
cd frontend
npm run check
npm run build
```
