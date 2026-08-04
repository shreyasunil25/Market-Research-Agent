# Market Research Agent

An autonomous market research agent that takes an industry name and produces a structured market report, combining live web research with historical sales data. Built with LangGraph using a supervisor/multi-agent pattern, exposed via FastAPI, and automated end-to-end with n8n.

## What it does

Given an industry keyword, the system:
1. Researches current market trends via live web search
2. Pulls historical sales metrics from a local database
3. Compiles both into a structured Markdown report

## Architecture

```
                    ┌──────────────┐
        ┌──────────▶│  Supervisor  │◀─────────┐
        │           └──────┬───────┘           │
        │                  │ routes to         │
        │      ┌───────────┼───────────┐       │
        │      ▼           ▼           ▼       │
        │  Researcher  SQL Analyst   Writer     │
        │      │           │           │       │
        └──────┘           └───────────┴───────┘
        (each node reports back to Supervisor)
```

| Node | Role | Tools used |
|---|---|---|
| **Supervisor** | Decides which node runs next based on what's already in state (research done? metrics done? report done?) | Plain Python control logic |
| **Researcher** | Fetches live web content on the industry and summarizes it | Tavily Search API + Llama3.2 |
| **SQL Analyst** | Queries historical sales data (revenue, units sold, top companies, YoY trends) for the matching industry | SQLite |
| **Writer** | Compiles research + metrics into a structured Markdown report | Llama3.2 |

The graph is a **hub-and-spoke loop**: the Supervisor is the only node that decides what runs next, and every specialist node reports back to it rather than to each other. This lets the flow adapt (e.g. skip a step, or loop back) rather than always running in a fixed order.

## Tech stack

- **LangGraph** — orchestration / control flow
- **Ollama (Llama3.2)** — local LLM, via `langchain-ollama`
- **Tavily** — live web search API
- **SQLite** — local historical sales database
- **FastAPI** — HTTP interface for the graph
- **n8n** — scheduling, automation, and delivery (PDF conversion + email)

## Setup

**1. Clone and install dependencies**
```bash
git clone <your-repo-url>
cd market-research-agent
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

**2. Set up Ollama**
```bash
ollama pull llama3.2
```
Ollama must be running locally (`ollama serve`, usually starts automatically).

**3. Set your Tavily API key**

Copy `.env.example` to `.env` and fill in your key (get one free at [tavily.com](https://tavily.com)):
```
TAVILY_API_KEY=your_key_here
```

**4. Add your database**

Place your `market_data.db` (SQLite) in the project root. Expected schema:

| Column | Type |
|---|---|
| record_id | — |
| company | TEXT |
| product | TEXT |
| category | TEXT |
| region | TEXT |
| year | INTEGER |
| quarter | — |
| units_sold | INTEGER |
| unit_price | REAL |
| revenue | REAL |
| cost | REAL |
| profit | REAL |
| customer_rating | REAL |
| inventory | — |

Each industry is stored as its own table (e.g. `ev_sales`, `smartphone_sales`).

## Running it

**Start the API:**
```bash
uvicorn app:app --reload --port 8000
```

Test it at `http://127.0.0.1:8000/docs`, or:
```bash
curl -X POST http://127.0.0.1:8000/generate-report -H "Content-Type: application/json" -d "{\"industry\": \"Electric Vehicles\"}"
```

This returns a JSON response with the generated report, and also saves a `.md` file to disk (e.g. `electric_vehicles_report.md`).

**Automating it with n8n:**

The included `n8n-workflow.json` runs:
```
Schedule Trigger → HTTP Request (POST /generate-report) → Markdown → HTML → Convert HTML to PDF → Send email
```

To use it:
1. In n8n, go to **Workflows → Import from File** and select `n8n-workflow.json`
2. Reconnect your own email credentials (Gmail/etc.) — these are stripped from the export for security and aren't included
3. Confirm the HTTP Request node's URL points at your running FastAPI instance (`http://127.0.0.1:8000/generate-report` by default)
4. Adjust the Schedule Trigger's timing as needed, or use the Manual Trigger to run on demand

## Known limitations

- **Industry is currently a fixed input per run** — not yet a dynamic, user-facing search field.
- **Requires local Ollama** — not yet swapped for a hosted LLM API, so deployment beyond your own machine currently needs that change first.
- **Error handling is minimal** — a failed SQL match or Tavily call currently raises rather than gracefully degrading.
- **SQL Analyst only supports industries with a matching table** already loaded into `market_data.db`.

## Project structure

```
market-research-agent/
├── graph/
│   └── market_research_graph.py
├── app.py
├── data/
│   └── market_data.db
├── n8n.json
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
