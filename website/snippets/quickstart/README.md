# Quickstart snippets

These files are the code shown on the website's quickstart page and landing
page. The pages embed them with the `Snippet` component, and
`.github/workflows/ci-docs-snippets.yml` runs each language's service from the
**published** packages and runs `walkthrough.sh` against it.

- One directory per language: the smallest service that declares two
  capabilities, `search_flights` (read) and `book_flight` (irreversible).
- `walkthrough.sh`: every request the quickstart page shows, with assertions.
- The package versions in these files are set by the release workflow.

To change what the quickstart shows, change these files, not the page.

Run one locally:

```bash
cd python && pip install -r requirements.txt && uvicorn app:app --port 9100
bash ../walkthrough.sh http://localhost:9100
```
