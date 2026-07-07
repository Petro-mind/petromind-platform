# 🏭 PetroMind Platform — Predictive Maintenance AI System

An intelligent predictive maintenance platform for industrial turbofan engines. PetroMind ingests real-time sensor data, predicts Remaining Useful Life (RUL), classifies failure risk, retrieves maintenance knowledge from technical manuals, and provides actionable recommendations through an interactive AI chat interface.

This is the **parent repository** that orchestrates all PetroMind components via git submodules.

---

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Repository Structure](#repository-structure)
- [Submodules](#submodules)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Data & Models](#data--models)
- [Running the System](#running-the-system)
- [Testing](#testing)
- [Submodule Management](#submodule-management)
- [Development Workflow](#development-workflow)

---

## 🏗 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     petromind-platform (Main Repo)               │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  app.py / run_api.py / requirements.txt / .env / config    │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │  petromind/       │  │  base-pipeline/ │  │ PetroMind-    │  │
│  │  (Agent Submodule)│  │  (Same Repo)    │  │ RAG-book/     │  │
│  │                   │  │                 │  │ (RAG Submodule)│  │
│  │  ┌─────────────┐  │  │ ┌───────────┐  │  │ ┌───────────┐  │  │
│  │  │ Agent Core  │  │  │ │ ML Models │  │  │ │ Pinecone  │  │  │
│  │  │ Orchestrator│  │  │ │ LSTM RUL  │  │  │ │ Hybrid    │  │  │
│  │  │ Planner     │◄─┼──┼─┤ Classifier│  │  │ │ Retriever │  │  │
│  │  │ Executor    │  │  │ │ Training  │  │  │ │ Indexer   │  │  │
│  │  │ Reflection  │  │  │ └───────────┘  │  │ └───────────┘  │  │
│  │  │ Guardrails  │  │  └─────────────────┘  └────────────────┘  │
│  │  └─────────────┘  │                                          │
│  │                   │                                          │
│  │  ┌─────────────┐  │  ┌─────────────────┐                    │
│  │  │ ML Inference │  │  │ ncmpass-pipeline │                    │
│  │  │ RUL Service  │◄─┼──┤ (Same Repo)     │                    │
│  │  │ Classifier   │  │  │ ┌─────────────┐  │                    │
│  │  │ Prediction   │  │  │ │ N-CMAPSS    │  │                    │
│  │  └─────────────┘  │  │ │ Loader       │  │                    │
│  │                   │  │ │ Checkpoints  │  │                    │
│  │  ┌─────────────┐  │  │ └─────────────┘  │                    │
│  │  │ Real-Time   │  │  └─────────────────┘                    │
│  │  │ Monitor     │  │                                          │
│  │  └─────────────┘  │  ┌─────────────────┐                    │
│  │                   │  │ tests/           │                    │
│  │  ┌─────────────┐  │  │ ┌─────────────┐  │                    │
│  │  │ RAG Bridge  │◄─┼──┼─┤ Integration  │  │                    │
│  │  └─────────────┘  │  │ │ Tests        │  │                    │
│  └──────────────────┘  │ └─────────────┘  │                    │
│                        └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
petromind-platform/                         ← Main Repo (GitHub)
│
├── petromind/                              ← SUBMODULE → Agent Repo
│   ├── agent/                              (github.com/.../Petro-mind_Agentic_Part)
│   ├── api/
│   ├── config/
│   ├── db/
│   ├── inference/
│   ├── ingestion/
│   ├── llm/
│   ├── monitoring/
│   ├── pipeline/
│   ├── rag/
│   └── README.md
│
├── PetroMind-RAG-book/                     ← SUBMODULE → RAG Repo
│   ├── database.py                         (github.com/.../PetroMind-RAG-book)
│   ├── retriever.py
│   ├── parser.py
│   ├── main.py
│   └── ...
│
├── base-pipeline/                          ← Direct (same repo)
│   └── pipeline/
│       ├── lstm_model.py
│       ├── rul_model.py
│       ├── dataset.py
│       ├── features.py
│       ├── config.py
│       └── __init__.py
│
├── ncmpass-pipeline/                       ← Direct (same repo)
│   ├── ncmapss_loader.py
│   ├── ncmapss.py
│   ├── train_ncmapss.py
│   ├── benchmark_models.py
│   ├── benchmark_ncmapss.py
│   ├── diagnose_ncmapss.py
│   ├── test_ncmapss.py
│   ├── requirements.txt
│   ├── INTEGRATION_README.md
│   ├── setup_integration.sh
│   └── checkpoints_ncmapss_rul/           ← After training
│   └── checkpoints_ncmapss_cls/           ← After training
│
├── tests/                                  ← Direct (same repo)
│   ├── test_models.py
│   ├── test_pipeline.py
│   ├── test_severe.py
│   ├── test_agent_full_workflow.py
│   ├── test_full_workflow.py
│   ├── test_realtime_pipeline.py
│   ├── test_severe_comprehensive.py
│   ├── test_severe_enhanced.py
│   ├── verify_pinecone.py
│   ├── verify_rag_integration.py
│   └── ...
│
├── System_Analysis/                        ← Direct (docs)
│   └── PetroMind_System_Analysis.md
│
├── plans/                                  ← Direct (docs)
│   └── plan.md
│
├── data/                                   ← Created / mounted (gitignored)
│   └── N-CMAPSS_DS02-006.h5
│
├── app.py                                  ← Gradio UI entry point
├── run_api.py                              ← FastAPI server runner
├── requirements.txt                        ← All dependencies
├── .env.example                            ← Environment template
├── .gitignore                              ← Git ignore rules
├── pyrightconfig.json                      ← Type checker config
│
├── drop_tables.py                          ← Dev utilities
├── fix_db.py
│
├── PetroMind_AI_Agent_Architecture_Guide.pdf
├── PetroMind_Implementation_Plan.md
├── PetroMind_Project_Context.md
├── PetroMind_System_Analysis.md
├── tool_analysis_recommendations.md
│
└── README.md                               ← This file
```

---

## 🔗 Submodules

This repo uses git submodules for component isolation:

| Submodule | Folder | Repository |
|-----------|--------|------------|
| **Agent** | `petromind/` | `Petro-mind_Agentic_Part` |
| **RAG** | `PetroMind-RAG-book/` | `PetroMind-RAG-book` |

### Adding Submodules

```bash
git submodule add https://github.com/YOUR_ORG/Petro-mind_Agentic_Part.git petromind
git submodule add https://github.com/YOUR_ORG/PetroMind-RAG-book.git PetroMind-RAG-book
git commit -m "chore: add agent and RAG submodules"
```

---

## ✅ Prerequisites

- **Python 3.10+**
- **PostgreSQL** (optional — falls back to in-memory)
- **Groq** or **HuggingFace** API key (optional — mock mode without)
- **Pinecone** API key (optional — RAG falls back to mock)
- **Tavily** API key (optional — web search disabled)
- **N-CMAPSS Dataset** — `N-CMAPSS_DS02-006.h5`
- **Model Checkpoints** — `best_model.pt` for RUL and Classifier

---

## 🚀 Quick Start

```bash
# 1. Clone with all submodules
git clone --recurse-submodules https://github.com/YOUR_ORG/petromind-platform.git
cd petromind-platform

# (If already cloned without submodules)
git submodule update --init --recursive

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 5. Place data files
# N-CMAPSS_DS02-006.h5 → data/
# Trained checkpoints  → ncmpass-pipeline/checkpoints_*/

# 6. Run the application
python app.py --mode full
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Optional | Groq LLM provider key |
| `LLM_PROVIDER` | Optional | `"groq"` or `"hf"` (default: `"groq"`) |
| `LLM_MODEL` | Optional | Model ID (default: `"llama-3.3-70b-versatile"`) |
| `HF_API_TOKEN` | Optional | HuggingFace Inference API token |
| `PINECONE_API_KEY` | Optional | Pinecone vector database key |
| `POSTGRES_URL` | Optional | PostgreSQL connection string |
| `TAVILY_API_KEY` | Optional | Web search API key |

Without an LLM provider, the agent runs in **mock/rule-based mode** — validates sensor files, runs ML predictions, retrieves from RAG, and generates template responses.

---

## 📊 Data & Models

### N-CMAPSS Dataset

```bash
# Place at:
data/N-CMAPSS_DS02-006.h5
```

Download from [NASA N-CMAPSS repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/).

### Model Checkpoints

Required at:

```
ncmpass-pipeline/checkpoints_ncmapss_rul/best_model.pt
ncmpass-pipeline/checkpoints_ncmapss_cls/best_model.pt
```

**Option A — Train:**

```bash
cd ncmpass-pipeline
python train_ncmapss.py --model-type rul
python train_ncmapss.py --model-type classifier
```

**Option B — Download pre-trained checkpoints from your organization's storage.**

---

## 🖥 Running the System

### Gradio UI (Default)

```bash
python app.py --mode full
```

Opens browser at `http://127.0.0.1:7860`

### Chat Only

```bash
python app.py --mode chat
```

### Real-Time Monitor Only

```bash
python app.py --mode realtime
```

### FastAPI Server

```bash
python run_api.py
```

API at `http://127.0.0.1:8000` — interactive docs at `/docs`.

---

## 🧪 Testing

```bash
# Verify models load correctly
python test_models.py

# Full integration test
python test_pipeline.py

# Agent + guardrails + alert tests
python test_severe.py

# Run all tests
python -m pytest tests/
```

---

## 🔧 Submodule Management

### Update All Submodules

```bash
git submodule update --remote --merge
git commit -m "chore: update submodules to latest"
```

### Update a Specific Submodule

```bash
cd petromind
git checkout main
git pull
cd ..
git commit -m "chore: update petromind submodule"
```

### Working on Submodules Locally

```bash
# Make changes inside petromind/ or PetroMind-RAG-book/
# Commit and push from within each submodule directory
# Then update the parent reference:
git add petromind PetroMind-RAG-book
git commit -m "chore: update submodule references"
```

---

## 🧠 Key Design Features

- **Graceful Degradation:** Every component has a fallback — no LLM → rule-based, no database → in-memory, no Pinecone → mock RAG
- **Safety Guardrails:** Prompt injection detection, output filtering, reflection-based self-checking
- **Observability:** Event bus for real-time tracing, structured JSON logging, tool latency tracking
- **Real-Time Monitoring:** Background thread reads SCADA data, buffers sliding windows, runs predictions, evaluates alert thresholds
- **Alert Throttling:** 2-minute cooldown per asset prevents alert storms
