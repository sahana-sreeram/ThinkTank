# Policy Think Tank — Local-First Multi-Agent Policy Analysis

## ADLC - Agentic Development Life Cycle
https://docs.google.com/document/d/1K5HVmgUHhYq4l5B0hAwOyk5NeSeaEf00fSwaBYEQElc/edit?usp=sharing


> **This repository is being refactored** from TAU Group's scientific **ThinkTank**
> into a **local-first multi-agent policy think tank**. You enter a broad policy
> question (e.g. *"What is the environmental impact of adding a new MBTA Line?"*) and the
> system delegates research to stakeholder agents, synthesizes a recommendation,
> and forecasts effects with deterministic Python.
>
> - **Run the app:** `streamlit run app.py` (runs in mock mode with no model needed).
> - **Run tests:** `python -m pytest tests/`
> - **Run evals:** `python evals/run_evals.py`
> - **Architecture:** see [`ARCHITECTURE.md`](ARCHITECTURE.md),
>   [`MODEL_SELECTION.md`](MODEL_SELECTION.md), [`ADLC.md`](ADLC.md).
>
> **Attribution & license.** Adapted from **TAU Group's ThinkTank** (Texas A&M
> University), MIT-licensed — see [`LICENSE`](LICENSE). The original scientific
> virtual-lab documentation is preserved below for reference; the meeting-loop
> entrypoints are being retired in favor of the LangGraph policy workflow.

---

# Policy Think Tank

A **local-first, multi-agent policy analysis system**. You ask a broad policy
question — *"Should Boston implement congestion pricing downtown?"*, *"Should the
state pilot a guaranteed basic income?"* — and a team of AI agents plans the
analysis, researches it, weighs stakeholder perspectives, writes a recommendation
with an implementation plan, and forecasts possible effects. It runs entirely on a
local model via [Ollama](https://ollama.com), and works for **any policy domain**.

> **Adapted from [TAU Group's ThinkTank](https://github.com/taugroup/ThinkTank)**
> (Texas A&M University), MIT-licensed. The original was a scientific-meeting
> simulator; this fork refactors its agent + RAG foundation into a policy think tank.

---

## 💡 What It Does

```
User policy question
        ↓
Policy Director        → defines the objective, picks the stakeholders,
                         and assigns each task its agent type + skills
        ↓
Research agents        → gather objective, cited evidence
        ↓
Stakeholder agents     → analyze from each assigned perspective (skill-grounded)
        ↓
Data Analyst           → synthesizes findings → recommendation + implementation plan
        ↓
Forecasting            → deterministic scenarios (Python — never the model)
        ↓
Final recommendation + evidence + plan + forecast
```
Orchestration is a LangGraph state graph; each step passes structured data
(Pydantic models) to the next, and the Research agents' findings feed both the
stakeholders and the Data Analyst

---

## Requirements

1. Python version >= 3.11
2. git

---

## Setup
### 1. Install Ollama and pull the model

```bash
brew install ollama               # Or follow https://ollama.com/download
ollama pull llama3.1              # This will download the model
ollama serve                      # Starts the Ollama server on localhost:11434
```

### 2. Clone and install Python dependencies

```bash
git clone https://github.com/taugroup/ThinkTank.git
cd ThinkTank

# Create a clean environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# To handle mermaid code from LLMs
npm install -g @mermaid-js/mermaid-cli
```

### 3. Run the script

```bash
streamlit run app.py
```

### 4. Meeting transcript can be downloaded as a Word(.docx) file from the app.

---

## Citation
```text
@article{surabhi2025thinktank,
  title={ThinkTank: A Framework for Generalizing Domain-Specific AI Agent Systems into Universal Collaborative Intelligence Platforms},
  author={Surabhi, Praneet Sai Madhu and Mudireddy, Dheeraj Reddy and Tao, Jian},
  journal={arXiv preprint arXiv:2506.02931},
  year={2025}
}
```

## Team
- (In no particular order) Praneet Sai Madhu Surabhi, Dheeraj Mudireddy, Sujith Julakanti {MS. Data Science '25, TAU Group}
- Advisor: Prof. Dr. Jian Tao, Asst. Dir. of TAMIDS, Dir. of Digital Twin Lab
