# QA Test Intelligence Agent

An AI agent that monitors test run history, detects flaky tests, and alerts engineering teams with actionable insights — built for the Google Cloud Rapid Agent Hackathon.

## What it does
- Connects to MongoDB to query real test run history
- Detects flaky tests by analyzing pass/fail patterns
- Identifies correlations with environment, branch, and time of day
- Delivers plain-language summaries with severity ratings and recommended actions

## Tech Stack
- **Google Cloud Agent Builder** — agent orchestration
- **Gemini 2.5 Pro** — reasoning model
- **MongoDB Atlas** — test run history storage (MCP integration)
- **Google Cloud Run** — hosts the MongoDB MCP server

## Setup

### 1. Seed the database
```bash
pip install pymongo
python seed_qa_data.py
```

### 2. Deploy the MCP server
```bash
gcloud run deploy qa-mcp-server \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars MDB_MCP_CONNECTION_STRING="your_connection_string" \
  --port 3000
```

### 3. Connect to Agent Builder
Add the Cloud Run URL as an MCP Server tool in Google Cloud Agent Builder.

## Example queries
- "Which tests are most flaky right now?"
- "Why is the List users paginated test failing so much?"
- "Give me a summary I can share with my engineering team"

## License
MIT
