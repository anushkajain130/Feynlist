***

# Feynlist

Feynlist is a professional-grade, AI-powered productivity operating system. It integrates an event-driven architecture with a multi-agent framework to provide automated task management, deep performance analytics, and behavioral coaching. The system leverages the Google Gemini API to orchestrate five specialized AI personas that monitor user progress and provide contextual interventions.

## Core System Architecture

The repository is built on a modular, decoupled architecture consisting of several key layers:

*   **Multi-Agent Orchestrator:** Manages the lifecycle and interaction flow of the Council of Agents, enforcing global cooldowns and sequential response patterns.
*   **Event-Driven Rules Engine:** Monitors system events such as task completions, missed deadlines, and productivity spikes to trigger specific agent behaviors.
*   **Hybrid Memory Layer:** Combines in-process short-term session memory with an asynchronous SQLite long-term storage system. It includes an LLM-powered summarization pipeline to condense session data into behavioral insights.
*   **Modular Tool Registry:** Provides agents with secure, typed interfaces to interact with system data, including task repositories, analytics trends, and memory retrieval.
*   **Stateless Analytics Pipeline:** Computes daily metrics using Exponential Weighted Moving Averages (EWMA) and composite scoring algorithms.

## The Council of Agents

The system features five distinct AI personas, each defined by unique YAML configurations and specific operational scopes:

| Agent | Coaching style | Proactive triggers wired today |
| :--- | :--- | :--- |
| **Freya** | Direct and honest | Missed task, day start |
| **Anya** | Warm and rest-aware | Workload signal (moderate or severe), streak broken, end-of-day review |
| **ZeroTwo** | Analytical | Scheduled check-in |
| **Albedo** | Playful celebrator | Streak milestone |
| **Mohini** | Calm, energy-focused | None yet; replies when you message her |

All five also reply when you message them directly.

## Technical Specification

### Backend and Database
*   **Language:** Python 3.13+
*   **Framework:** FastAPI for REST and WebSocket communication.
*   **Database:** Asynchronous SQLite (aiosqlite) with automated SQL migrations.
*   **Scheduling:** APScheduler for background analytics and periodic event triggers.

### AI and Data
*   **Inference:** Google Gemini 2.5 Pro and Flash models.
*   **Validation:** Pydantic V2 for all internal data structures and API schemas.
*   **Logging:** Structured logging via Loguru.
*   **Migration:** Automated migration scripts for transitioning legacy CSV data into structured SQLite.

## Performance Metrics

Feynlist utilizes a proprietary scoring system to evaluate productivity:

1.  **Discipline:** A percentage-based metric tracking the consistent initiation of scheduled tasks.
2.  **Alertness:** A focus-quality metric derived from user-reported attention levels relative to task difficulty.
3.  **Aura:** A composite momentum score calculated as: `sqrt(Discipline) * sqrt(PS_Hours/Target) * log(1 + Streak)`.
4.  **Retention Streak:** A count of consecutive days maintained without a reset event.

## Installation and Deployment

### 1. Environment Setup
Clone the repository and install the package dependencies:

```bash
git clone https://github.com/your-username/feynlist.git
cd feynlist
pip install .
```

### 2. Configuration
Create a `.env` file in the project root. Refer to `.env.example` for the full list of required variables:

```text
GEMINI_API_KEY=your_api_key_here
DATABASE_PATH=feynlist.db
LOG_LEVEL=INFO
```

### 3. Database Initialization
Run the migration script to initialize the SQLite schema and import historical data:

```bash
python scripts/migrate_csv_to_sqlite.py
```

### 4. Running the API
Start the FastAPI server using Uvicorn:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Project Structure

```text
feynlist/
├── agents/             # Persona configurations and LLM runtimes
├── analytics/          # Metric computation and trend analysis
├── api/                # FastAPI routers and Pydantic schemas
├── config/             # Global settings and environment management
├── core/               # Domain models and exception definitions
├── data/               # Repositories and SQL migration files
├── events/             # Event bus and rules engine logic
├── memory/             # Long-term storage and session consolidation
├── notifications/      # Background scheduler and event triggers
└── tools/              # Modular functions accessible by AI agents
```

## API Documentation

Once the server is running, interactive documentation is available at the following endpoints:

*   **Swagger UI:** `http://localhost:8000/docs`
*   **ReDoc:** `http://localhost:8000/redoc`

## License

This project is licensed under the MIT License. See the LICENSE file for details.
