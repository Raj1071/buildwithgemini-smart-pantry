# Smart Pantry — AI Kitchen & Culinary Assistant

An intelligent, multi-modal kitchen management agent built with Google's Agent Development Kit (ADK), Vertex AI Agent Engine, and A2UI (Agent-to-User Interface).

![Smart Pantry Demo](demo.gif)

---

## 🌟 Capabilities

Smart Pantry helps users manage their kitchen stock, discover recipes, look up grocery products, calculate nutrition, and generate AI visuals of dishes:

- **Pantry Inventory Management**: Reads and updates live pantry stock stored in Google Cloud Firestore.
- **Cross-Session Memory & Allergy Retention**: Uses Vertex AI Memory Bank to automatically recall user dietary preferences, restrictions, and allergies across sessions.
- **Live Recipe Search**: Searches web recipes dynamically via TheMealDB API and saves custom recipes into Firestore.
- **Grocery & Nutri-Score Lookup**: Fetches branded food item details, categories, and Nutri-Score grades from the Open Food Facts API.
- **AI Food Image Generation**: Generates high-quality AI images of dishes and food items using Vertex AI (`gemini-3.1-flash-lite-image`).
- **AI Culinary Video Generation**: Generates short animated video clips of food preparation using Vertex AI Omni (`gemini-omni-flash-preview`).
- **Agent Code Execution**: Runs Python scripts in an isolated Vertex AI Agent Engine Sandbox for nutrition math and recipe scaling.
- **Structured A2UI Cards**: Renders interactive, rich visual display cards (Basic Catalog v0.8) for cards, rows, columns, and food images.

---

## 🏗️ Architecture & Wired Services

- **Agent Runtime**: Deployed to Vertex AI Agent Engine (Agent Runtime) using the A2A protocol.
- **LLM Engine**: `gemini-flash-latest` (with automatic retry policies).
- **Database**: Google Cloud Firestore (`pantry_items` and `recipes` collections).
- **Object Storage**: Google Cloud Storage public media bucket for food images and video assets.
- **Long-Term Memory**: Vertex AI Memory Bank (`PreloadMemoryTool` and post-turn memory callbacks).
- **Frontend**: Custom FastAPI proxy + HTML/CSS dialogue layout with A2UI card renderer.

---

## 📂 Project Structure

```
smart-pantry/
├── app/
│   └── agent.py              # Main ADK agent definition, tools, callbacks & A2UI instructions
├── frontend/
│   ├── main.py               # FastAPI proxy forwarding A2A protocol requests
│   ├── Procfile              # Uvicorn entrypoint for Cloud Run
│   └── static/
│       └── index.html        # Culinary-themed chat UI & A2UI card renderer
├── agents-cli-manifest.yaml  # Deployment configuration & service metadata
├── pyproject.toml            # Project dependencies
└── demo.gif                  # Inline demo animation
```

---

## 🚀 Local Setup & Run Instructions

### Prerequisites

- **Python**: 3.11+ (managed via `uv`)
- **Google Cloud SDK**: Signed in with valid GCP project permissions (`roles/aiplatform.user`)
- **agents-cli**: Installed via `uv tool install google-agents-cli`

### 1. Install Dependencies

```bash
uv sync
```

### 2. Run Agent Playground (Local ADK Web UI)

To test the agent locally using the ADK development web UI:

```bash
agents-cli playground
```

### 3. Run Custom Web Frontend Locally

To run the custom FastAPI frontend proxy locally:

```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/<REGION>/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"
python main.py
```

Open a web browser and navigate to port `8080` on your machine to interact with the custom UI.

---

## 🧪 Testing & Evaluation

Run unit and integration tests:

```bash
uv run pytest tests/unit tests/integration
```

Run agent evaluation with `agents-cli`:

```bash
agents-cli eval
```

---

## ☁️ Deployment

Deploy the agent to Vertex AI Agent Engine:

```bash
agents-cli deploy
```

Deploy the custom frontend to Google Cloud Run:

```bash
cd frontend
gcloud run deploy smart-pantry-frontend \
  --source . \
  --region us-west1 \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<ENGINE_RESOURCE_NAME>",AGENT_DIRECTORY="app" \
  --allow-unauthenticated
```
