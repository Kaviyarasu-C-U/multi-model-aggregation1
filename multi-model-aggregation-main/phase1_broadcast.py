"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          CONSENSUS AI SYSTEM — PHASE 1: BROADCAST LAYER                    ║
║          Send one query to 5 LLMs in parallel, collect all responses       ║
╚══════════════════════════════════════════════════════════════════════════════╝

5 MODELS — ONE PER API KEY IN YOUR .env:
──────────────────────────────────────────
  Key                  Provider     Model
  ─────────────────────────────────────────────────────────────────────
  OPENAI_API_KEY    →  OpenAI    →  gpt-4o-mini          (fast + cheap)
  GOOGLE_API_KEY    →  Google    →  gemini-2.0-flash      (new SDK)
  GROQ_API_KEY      →  Groq      →  llama-3.3-70b         (free, fast)
  OPENROUTER_API_KEY→  OpenRouter→  llama-3.1-8b:free     (always free)
  COHERE_API_KEY    →  Cohere    →  command-r-plus        (reasoning)

INSTALL REQUIRED PACKAGES (run once):
───────────────────────────────────────
  c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe -m pip install openai groq cohere google-genai python-dotenv

HOW TO RUN:
────────────
  Full pipeline (Phase 1 + Phase 2):
    c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe run_consensus_ai.py

  Phase 1 only (broadcast):
    c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe phase1_broadcast.py

  Phase 2 only (consensus scan — needs responses.json from Phase 1):
    c:\\Users\\hp\\Documents\\LLM\\.venv\\Scripts\\python.exe phase2_consensus.py

ARCHITECTURE:
──────────────
  Your Query
      │
      ├──► gpt-4o-mini       (OpenAI)      ─┐
      ├──► gemini-2.0-flash  (Google)       │  All 5 run at the SAME TIME
      ├──► llama-3.3-70b     (Groq)         │  Total time = slowest model
      ├──► llama-3.1-8b      (OpenRouter)   │
      └──► command-r-plus    (Cohere)      ─┘
               │
       [5 responses collected]
               │
         responses.json  →  Phase 2 (consensus scanner)
"""

import asyncio
import json
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Force UTF-8 output so Unicode box-drawing chars don't crash Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ─── Load all 5 API keys from .env ──────────────────────────────────────────
load_dotenv()

# ── All 5 use FREE APIs — no billing required ───────────────────────────────
GROQ_API_KEY     = os.getenv("GROQ_API_KEY")      # FREE ─ deepseek-r1 + llama-3.3-70b
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")  # FREE ─ llama-3.3-70b + llama-3.1-8b (ultra-fast)
COHERE_API_KEY   = os.getenv("COHERE_API_KEY")    # FREE ─ command-a-03-2025 (1000 calls/month)
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY")    # FREE ─ kept in .env for future use

# ─── Shared system prompt for all models ────────────────────────────────────
SYSTEM_PROMPT = (
    "You are a highly accurate AI assistant. "
    "Answer the user's question with clear reasoning, "
    "factual accuracy, and detailed analysis."
)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — INDIVIDUAL MODEL CALLERS
# Each function = one API provider. Same input, same output structure.
# ══════════════════════════════════════════════════════════════════════════════

async def call_gemini_flash(query: str) -> dict:
    """
    Model  : gemini-2.5-flash  (Google)
    Key    : GEMINI_API_KEY
    Cost   : FREE — Google AI Studio free tier

    Gemini 2.5 Flash is Google's latest and most capable Flash model.
    It features built-in thinking/reasoning capabilities.

    REPLACED: deepseek-r1-distill-llama-70b — that model was DECOMMISSIONED by Groq.
    """
    start_time = time.time()
    model_name = "Gemini 2.5 Flash"

    try:
        import google.genai as genai
        from google.genai import types

        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in .env")

        client = genai.Client(api_key=GEMINI_API_KEY)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=query,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1000,
                    temperature=0.3,
                )
            )
        )

        answer_text = response.text

        return {
            "model":              model_name,
            "provider":           "Google (Gemini 2.5 Flash)",
            "status":             "success",
            "response":           answer_text,
            "time_taken_seconds": round(time.time() - start_time, 2),
            "tokens_used":        None
        }

    except Exception as e:
        return {
            "model":              model_name,
            "provider":           "Google (Gemini 2.5 Flash)",
            "status":             "error",
            "response":           None,
            "error":              str(e),
            "time_taken_seconds": round(time.time() - start_time, 2)
        }


async def call_gemini_flash_lite(query: str) -> dict:
    """
    Model  : gemini-2.5-flash-lite  (Google)
    Key    : GEMINI_API_KEY  (same key — separate per-model quota)
    Cost   : FREE — Google AI Studio free tier

    Gemini 2.5 Flash-Lite is lighter and faster than Flash.
    Same API key, different model name = its own separate daily quota counter.

    REPLACED: llama-3.3-70b on Cerebras — that model name was wrong (404 error).
    The correct Cerebras name is 'llama3.3-70b' but we use Gemini here instead
    for better response diversity (Google vs Meta architecture).
    """
    start_time = time.time()
    model_name = "Gemini 2.5 Flash-Lite"

    try:
        import google.genai as genai
        from google.genai import types

        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in .env")

        client = genai.Client(api_key=GEMINI_API_KEY)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=query,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=1000,
                    temperature=0.3,
                )
            )
        )

        answer_text = response.text

        return {
            "model":              model_name,
            "provider":           "Google (Gemini 2.5 Flash-Lite)",
            "status":             "success",
            "response":           answer_text,
            "time_taken_seconds": round(time.time() - start_time, 2),
            "tokens_used":        None
        }

    except Exception as e:
        return {
            "model":              model_name,
            "provider":           "Google (Gemini 2.5 Flash-Lite)",
            "status":             "error",
            "response":           None,
            "error":              str(e),
            "time_taken_seconds": round(time.time() - start_time, 2)
        }


async def call_groq(query: str) -> dict:
    """
    Model  : llama-3.3-70b-versatile  (Groq)
    Key    : GROQ_API_KEY
    Cost   : FREE on Groq's free tier (generous rate limits)

    Groq is an AI inference company with custom hardware (LPU chips)
    that runs Llama models 10-20x faster than standard GPU inference.
    llama-3.3-70b is Meta's latest 70B parameter instruction-tuned model.
    """
    start_time = time.time()
    model_name = "Llama 3.3 70B (Groq)"

    try:
        from groq import AsyncGroq

        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not found in .env")

        client = AsyncGroq(api_key=GROQ_API_KEY)

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": query}
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        answer_text = response.choices[0].message.content

        return {
            "model":              model_name,
            "provider":           "Groq (Meta Llama)",
            "status":             "success",
            "response":           answer_text,
            "time_taken_seconds": round(time.time() - start_time, 2),
            "tokens_used":        response.usage.total_tokens
        }

    except Exception as e:
        return {
            "model":              model_name,
            "provider":           "Groq (Meta Llama)",
            "status":             "error",
            "response":           None,
            "error":              str(e),
            "time_taken_seconds": round(time.time() - start_time, 2)
        }


async def call_cerebras_llama8b(query: str) -> dict:
    """
    Model  : llama3.1-8b  (Cerebras)
    Key    : CEREBRAS_API_KEY  (same key as above — Cerebras hosts multiple models)
    Cost   : $0.00 — Completely FREE

    Llama 3.1 8B is a smaller, lighter model than Llama 3.3 70B.
    On Cerebras hardware it still runs extremely fast.

    WHY USE BOTH 70B AND 8B FROM CEREBRAS?
    • Different model SIZES give different response perspectives
    • 8B models tend to be more concise and direct
    • 70B models tend to be more thorough and detailed
    • Having both sizes improves consensus quality:
      if 70B and 8B AGREE → very high confidence in that answer
    • Both use the same API key — zero extra setup
    """
    start_time = time.time()
    model_name = "Llama 3.1 8B (Cerebras)"

    try:
        from openai import AsyncOpenAI

        if not CEREBRAS_API_KEY:
            raise ValueError("CEREBRAS_API_KEY not found in .env")

        client = AsyncOpenAI(
            api_key=CEREBRAS_API_KEY,
            base_url="https://api.cerebras.ai/v1",
        )

        response = await client.chat.completions.create(
            model="llama3.1-8b",   # Llama 3.1 8B — fast and efficient on Cerebras
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": query}
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        answer_text = response.choices[0].message.content

        return {
            "model":              model_name,
            "provider":           "Cerebras (FREE)",
            "status":             "success",
            "response":           answer_text,
            "time_taken_seconds": round(time.time() - start_time, 2),
            "tokens_used":        response.usage.total_tokens if response.usage else None
        }

    except Exception as e:
        return {
            "model":              model_name,
            "provider":           "Cerebras (FREE)",
            "status":             "error",
            "response":           None,
            "error":              str(e),
            "time_taken_seconds": round(time.time() - start_time, 2)
        }


async def call_cohere(query: str) -> dict:
    """
    Model  : command-a-03-2025  (Cohere)
    Key    : COHERE_API_KEY
    Note   : Cohere's LATEST and most capable model (released March 2025)

    command-r-plus was REMOVED by Cohere on September 15, 2025.
    command-a-03-2025 is their current flagship — better than command-r-plus.
    Cohere provides a free trial tier (1000 calls/month).
    """
    start_time = time.time()
    model_name = "Command A (Cohere)"

    try:
        import cohere

        if not COHERE_API_KEY:
            raise ValueError("COHERE_API_KEY not found in .env")

        client = cohere.AsyncClientV2(api_key=COHERE_API_KEY)

        response = await client.chat(
            model="command-a-03-2025",   # command-r-plus was removed Sep 2025
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": query}
            ],
            max_tokens=1000,
            temperature=0.3,
        )

        answer_text = response.message.content[0].text

        return {
            "model":              model_name,
            "provider":           "Cohere",
            "status":             "success",
            "response":           answer_text,
            "time_taken_seconds": round(time.time() - start_time, 2),
            "tokens_used": (
                response.usage.tokens.input_tokens + response.usage.tokens.output_tokens
                if response.usage and response.usage.tokens else None
            )
        }

    except Exception as e:
        return {
            "model":              model_name,
            "provider":           "Cohere",
            "status":             "error",
            "response":           None,
            "error":              str(e),
            "time_taken_seconds": round(time.time() - start_time, 2)
        }


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — THE BROADCAST ENGINE
# Fires all 5 model calls simultaneously using asyncio.gather()
# Total time = time of the SLOWEST model (not sum of all 5)
# ══════════════════════════════════════════════════════════════════════════════

async def broadcast_to_all_models(query: str) -> dict:
    """
    Sends the query to ALL 5 models at the same time and collects results.

    KEY CONCEPT — asyncio.gather():
    ─────────────────────────────────────────────────────────────────────────
    Sequential (old way):              Parallel with gather (our way):
      OpenAI   waits 3s                OpenAI    ─┐
      Google   waits 2s                Google    ─┤  all start at t=0
      Groq     waits 1s      →         Groq      ─┤  finish around t=3s
      OpenRtr  waits 3s                OpenRtr   ─┤  (slowest wins)
      Cohere   waits 2s                Cohere    ─┘
      Total = 11 seconds               Total = ~3 seconds
    ─────────────────────────────────────────────────────────────────────────
    """
    print(f"\n{'═'*65}")
    print(f"  CONSENSUS AI — PHASE 1: BROADCAST")
    print(f"{'═'*65}")
    print(f"  QUERY : {query[:72]}{'...' if len(query) > 72 else ''}")
    print(f"  TIME  : {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'─'*65}")
    print(f"  Model              Provider           Status")
    print(f"{'─'*65}")

    broadcast_start = time.time()

    # All 5 start at the SAME TIME
    # return_exceptions=True → if one fails, others keep running
    results = await asyncio.gather(
        call_gemini_flash(query),      # GEMINI_API_KEY    → gemini-2.5-flash            🟢 FREE
        call_gemini_flash_lite(query), # GEMINI_API_KEY    → gemini-2.5-flash-lite       🟢 FREE
        call_groq(query),              # GROQ_API_KEY      → llama-3.3-70b              🟢 FREE
        call_cerebras_llama8b(query),  # CEREBRAS_API_KEY  → llama3.1-8b               🟢 FREE
        call_cohere(query),            # COHERE_API_KEY    → command-a-03-2025          🟢 FREE
        return_exceptions=True
    )

    total_time = round(time.time() - broadcast_start, 2)

    # ── Print results summary ─────────────────────────────────────────────
    print(f"\n  ALL RESPONSES RECEIVED — Total time: {total_time}s")
    print(f"{'─'*65}\n")

    for result in results:
        if isinstance(result, Exception):
            print(f"  [CRASH] Unexpected asyncio error: {result}\n")
            continue

        model   = result.get("model", "Unknown")
        status  = result.get("status", "unknown")
        elapsed = result.get("time_taken_seconds", "?")
        tokens  = result.get("tokens_used")
        tok_str = f"  [{tokens} tokens]" if tokens else ""

        if status == "success":
            preview = result["response"][:180].replace("\n", " ")
            print(f"  ✅  {model} ({elapsed}s){tok_str}")
            print(f"      └─ {preview}...\n")
        else:
            error = result.get("error", "Unknown error")
            print(f"  ❌  {model} ({elapsed}s)")
            print(f"      └─ ERROR: {error}\n")

    # ── Build structured output for Phase 2 ──────────────────────────────
    broadcast_result = {
        "query":                         query,
        "timestamp":                     datetime.now().isoformat(),
        "total_broadcast_time_seconds":  total_time,
        "model_count":                   len(results),
        "successful_responses":          sum(
            1 for r in results
            if isinstance(r, dict) and r.get("status") == "success"
        ),
        "responses": [r for r in results if isinstance(r, dict)]
    }

    return broadcast_result


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SAVE / LOAD HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def save_responses(broadcast_result: dict, filename: str = "responses.json"):
    """Saves all 5 model responses to a JSON file for Phase 2 to read."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(broadcast_result, f, indent=2, ensure_ascii=False)

    success = broadcast_result["successful_responses"]
    total   = broadcast_result["model_count"]

    print(f"{'═'*65}")
    print(f"  PHASE 1 COMPLETE")
    print(f"{'─'*65}")
    print(f"  ✅  Saved to          : {filename}")
    print(f"  ✅  Successful models : {success} / {total}")
    if success < total:
        print(f"  ⚠   Failed models   : {total - success} (see errors above)")
    print(f"  ▶   Next step        : run phase2_consensus.py")
    print(f"{'═'*65}\n")


def load_responses(filename: str = "responses.json") -> dict:
    """Loads saved responses — useful for re-running Phase 2 without new API calls."""
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    """
    Change the query here to ask any question.
    Best on factual / analytical / scientific questions.
    """
    # ── Your question goes here ───────────────────────────────────────────
    query = "What causes inflation and how does a central bank control it?"

    # ── Broadcast → Collect → Save ────────────────────────────────────────
    result = await broadcast_to_all_models(query)
    save_responses(result, "responses.json")


if __name__ == "__main__":
    asyncio.run(main())