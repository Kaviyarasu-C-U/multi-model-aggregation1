# NEXUS — Multi-Model Consensus AI 🌌

NEXUS is a cutting-edge web application that orchestrates multiple Large Language Models (LLMs) to answer your queries. Instead of relying on a single AI, NEXUS parallel-broadcasts your prompt to 5 distinct models, analyzes their responses, and synthesizes a single, highly accurate "Consensus Answer."

---

## 🚀 Key Features

*   **Parallel Processing Engine**: Simultaneously queries 5 leading open and proprietary models to gather diverse perspectives in parallel (Total time ≈ time taken by the slowest model).
*   **Consensus Synthesis**: Employs TF-IDF cosine similarity to rank model responses and measures semantic agreement.
*   **Judge LLM Synthesis**: Auto-selects the top 3 highest-agreement models and utilizes Meta's Llama 3.3 70B (via Groq) to merge complementary details into a unified ultimate response.
*   **Resilient Architecture**: Automatically detects and gracefully skips models that encounter API limits (e.g., rate limits, out of credits) or network errors without interrupting the consensus pipeline.
*   **Fallback Similarity Engine**: Utilizes Jaccard word-overlap similarity logic if `scikit-learn` is not installed, ensuring full functionality in simple environments.
*   **Persistent SQLite Storage**: Local conversation threading, user account management, and query statistics are stored inside a local SQLite database (`consensus_ai.db`).
*   **Responsive Glassmorphic UI**: Beautiful 3-column layout featuring real-time visual progress arcs, dynamic SVG loading micro-animations, and complete viewport scalability.

---

## 🤖 The AI Roster

NEXUS integrates the following models using their developer tiers:
1.  **Gemini 2.5 Flash** (Google API)
2.  **Gemini 2.5 Flash-Lite** (Google API)
3.  **Llama 3.3 70B** (Groq API)
4.  **Llama 3.1 8B** (Cerebras API)
5.  **Command A** (Cohere API)

---

## 🛠️ Technology Stack

*   **Backend**: Python, FastAPI, SQLite
*   **Frontend**: HTML5, Vanilla JavaScript, CSS3 (harmony color system, custom animations)
*   **AI Integration**: Asyncio for concurrent requests, `scikit-learn` for similarity matrix calculations, official API client libraries (`google-genai`, `groq`, `cohere`, `openai`).

---

## ⚙️ Setup & Installation

1.  **Navigate to the project root directory** in your terminal.
2.  **Create and activate your Python virtual environment**:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate
    ```
3.  **Install the required dependencies**:
    ```bash
    pip install fastapi uvicorn pydantic python-dotenv scikit-learn groq httpx google-genai cohere openai
    ```
4.  **Configure Environment Variables**:
    Create a `.env` file in the root directory and add your API keys:
    ```env
    GEMINI_API_KEY=your_key_here
    GROQ_API_KEY=your_key_here
    CEREBRAS_API_KEY=your_key_here
    COHERE_API_KEY=your_key_here
    ```

---

## 🖥️ Running the Application

### 1. Web Application (UI)
Start the local server using Uvicorn:
```bash
python -m uvicorn web_app:app --reload --port 8000
```
Alternatively, double-click `start_web.bat` to automatically open the server and open Chrome.

Then, navigate to **[http://localhost:8000](http://localhost:8000)** in your browser.

### 2. Command Line Pipeline
To test the consensus pipeline directly from the command line:
```bash
python run_consensus_ai.py "Your custom query goes here"
```
Or run the phases individually:
*   **Phase 1 Only (Broadcast)**: `python phase1_broadcast.py` (saves responses to `responses.json`)
*   **Phase 2 Only (Consensus & Synthesis)**: `python phase2_consensus.py` (reads `responses.json` and writes `consensus_result.json`)
