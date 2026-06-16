"""
╔══════════════════════════════════════════════════════════════════════════════╗
║         CONSENSUS AI — FULL PIPELINE RUNNER                                ║
║         One command runs Phase 1 (broadcast) + Phase 2 (consensus)        ║
╚══════════════════════════════════════════════════════════════════════════════╝

HOW TO RUN:
────────────
  Default question:
    c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe run_consensus_ai.py

  Custom question (put it in quotes):
    c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe run_consensus_ai.py "How do vaccines work?"

INSTALL PACKAGES (run once if not done yet):
─────────────────────────────────────────────
  c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe -m pip install openai groq cohere google-genai python-dotenv scikit-learn

FULL PIPELINE:
───────────────
  Your Question
       │
       ├──► gpt-4o-mini       (OpenAI — OPENAI_API_KEY)          ─┐
       ├──► gemini-2.0-flash  (Google — GOOGLE_API_KEY)           │  Phase 1
       ├──► llama-3.3-70b     (Groq   — GROQ_API_KEY)            │  All 5 run
       ├──► llama-3.1-8b:free (OpenRouter — OPENROUTER_API_KEY)   │  simultaneously
       └──► command-r-plus    (Cohere — COHERE_API_KEY)           ─┘
                │
       [5 responses collected → responses.json]
                │
       [TF-IDF Similarity Matrix]  ← how much does each response agree with others?
                │
       [Consensus Score per model] ← rank by majority agreement
                │
       [Top 3 selected]            ← highest agreement models
                │
       [Judge: Llama 3.3 70B (Groq, FREE)] ← synthesises final answer
                │
       [FINAL CONSENSUS ANSWER] ✅  → consensus_result.json
"""

import asyncio
import sys
from phase1_broadcast import broadcast_to_all_models, save_responses
from phase2_consensus import run_consensus


async def main():
    # ── Get query from command line or use default ────────────────────────
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        # ─── CHANGE THIS QUERY TO ASK DIFFERENT QUESTIONS ────────────────
        query = "What causes inflation and how does a central bank control it?"
        #
        # Other example questions to try:
        #   query = "Explain how vaccines work at the molecular level"
        #   query = "What is quantum entanglement and why does it matter?"
        #   query = "What are the main causes of climate change?"
        #   query = "How does a neural network learn from data?"
        #   query = "What is the difference between DNA and RNA?"

    # ── Phase 1: Broadcast to all 5 models ───────────────────────────────
    broadcast_result = await broadcast_to_all_models(query)
    save_responses(broadcast_result, "responses.json")

    # ── Phase 2: Consensus scan + final answer ────────────────────────────
    await run_consensus(
        responses_file="responses.json",
        top_k=3,           # Send top 3 most-agreeing models to the Judge
        save_output=True   # Save result to consensus_result.json
    )


if __name__ == "__main__":
    asyncio.run(main())
