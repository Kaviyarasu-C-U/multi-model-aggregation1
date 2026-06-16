"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          CONSENSUS AI SYSTEM — PHASE 2: CONSENSUS SCANNER                  ║
║          Read 5 LLM responses → find majority agreement → final answer     ║
╚══════════════════════════════════════════════════════════════════════════════╝

WHAT THIS FILE DOES:
─────────────────────
  1. Loads the 5 responses saved by Phase 1 (responses.json)
  2. Computes similarity between every pair of responses (TF-IDF cosine)
  3. Scores each model: how much does it AGREE with the others?
  4. Selects the TOP 3 most-agreeing models (majority consensus)
  5. Sends those 3 to a Judge LLM (Llama 3.3 70B via Groq — FREE)
  6. The Judge synthesises ONE final accurate answer

CONSENSUS ALGORITHM (visual):
──────────────────────────────
  GPT-4o-mini ─────────┐
  Gemini 2.0  ──────── ├──► Similarity Matrix (5×5)
  Llama 3.3   ──────── ┤         │
  Llama 3.1   ──────── ┤    Consensus Score per model
  Command R+  ─────────┘         │
                             Rank by score
                                  │
                           Top 3 selected
                                  │
                          Judge LLM (Groq)
                                  │
                          FINAL ANSWER ✅

HOW TO RUN:
────────────
  Step 1: python phase1_broadcast.py   (or run_consensus_ai.py for both)
  Step 2: python phase2_consensus.py
"""

import json
import os
import time
import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv

# Force UTF-8 output so Unicode box-drawing chars don't crash Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

load_dotenv()

# Keys available — Groq is used for the Judge LLM (free)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — SIMILARITY ENGINE
# Measures how similar two pieces of text are.
#   0.0 = completely different meaning
#   1.0 = identical meaning
# ══════════════════════════════════════════════════════════════════════════════

def compute_similarity_matrix(responses: list[dict]) -> list[list[float]]:
    """
    Builds an N×N matrix where entry [i][j] = semantic similarity
    between response i and response j.

    ALGORITHM: TF-IDF Cosine Similarity
    ──────────────────────────────────────
    Step 1: Convert each response into a TF-IDF vector
            - TF  = Term Frequency: how often a word appears in THIS response
            - IDF = Inverse Doc Frequency: how rare is this word across ALL responses
            - TF-IDF = TF × IDF → words that are frequent here but rare elsewhere score high
            - Result: each response becomes a high-dimensional numeric vector

    Step 2: Compute cosine similarity between every pair of vectors
            - cosine_similarity(A, B) = dot(A,B) / (|A| × |B|)
            - 1.0 = vectors point in the same direction = same topic/meaning
            - 0.0 = perpendicular = totally different content

    WHY NOT JUST COUNT MATCHING WORDS?
    ─────────────────────────────────────
    Common words like "the", "a", "is", "and" appear in every response.
    Counting them would make every pair look similar.
    TF-IDF automatically down-weights common words — only meaningful,
    content-bearing words count toward similarity.

    REQUIRES: pip install scikit-learn
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        texts = [r["response"] for r in responses]

        vectorizer = TfidfVectorizer(
            stop_words="english",   # ignore "the", "a", "is", etc.
            max_features=5000       # use top 5000 most informative words
        )
        tfidf_matrix = vectorizer.fit_transform(texts)

        # Full N×N similarity matrix
        sim_matrix = cosine_similarity(tfidf_matrix).tolist()
        return sim_matrix

    except ImportError:
        # scikit-learn not installed → fall back to simpler word-overlap method
        print("  ⚠  scikit-learn not installed. Using basic word-overlap (Jaccard) similarity.")
        print("     For better accuracy: pip install scikit-learn\n")
        return _jaccard_fallback(responses)


def _jaccard_fallback(responses: list[dict]) -> list[list[float]]:
    """
    Fallback when scikit-learn is not available.

    Jaccard Similarity(A, B) = |A ∩ B| / |A ∪ B|
    where A and B are SETS of unique words.

    Example:
      A = {"inflation", "prices", "money", "supply"}
      B = {"inflation", "prices", "demand", "central"}
      Intersection = {"inflation", "prices"} → size 2
      Union        = 6 words
      Jaccard = 2/6 = 0.33
    """
    import re

    STOP_WORDS = {
        'the','a','an','is','are','was','were','be','been','being',
        'have','has','had','do','does','did','will','would','could',
        'should','may','might','can','this','that','these','those',
        'and','or','but','in','on','at','to','for','of','with','by',
        'from','as','it','its','not','also','which','their','they',
        'what','when','how','why','who','where','than','then','so'
    }

    def tokenize(text):
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return set(w for w in words if w not in STOP_WORDS)

    word_sets = [tokenize(r["response"]) for r in responses]
    n = len(word_sets)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            else:
                union = word_sets[i] | word_sets[j]
                inter = word_sets[i] & word_sets[j]
                matrix[i][j] = len(inter) / len(union) if union else 0.0

    return matrix


def compute_consensus_scores(sim_matrix: list[list[float]]) -> list[float]:
    """
    Converts the N×N similarity matrix into a SINGLE SCORE per model.

    Formula:
      ConsensusScore[i] = average similarity of model i to ALL other models
                          (diagonal excluded — model i vs. itself is always 1.0)

    INTERPRETATION:
      HIGH score → this model agrees with the majority → likely correct
      LOW score  → this model is an outlier → possibly hallucinating or off-topic

    Example with 3 models:
      Similarities:  A↔B = 0.8,  A↔C = 0.7,  B↔C = 0.3
      Score[A] = avg(0.8, 0.7)  = 0.75  ← agrees with most
      Score[B] = avg(0.8, 0.3)  = 0.55
      Score[C] = avg(0.7, 0.3)  = 0.50  ← most isolated
    """
    n = len(sim_matrix)
    scores = []
    for i in range(n):
        others = [sim_matrix[i][j] for j in range(n) if j != i]
        avg = sum(others) / len(others) if others else 0.0
        scores.append(round(avg, 4))
    return scores


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — THE JUDGE LLM
# Takes the top-K most agreeing responses and synthesises a final answer.
# Uses Llama 3.3 70B via Groq (FREE, very fast).
# ══════════════════════════════════════════════════════════════════════════════

async def call_judge_llm(query: str, top_responses: list[dict]) -> str:
    """
    The Judge LLM reads the top-consensus responses and writes ONE final answer.

    Model used: llama-3.3-70b-versatile via Groq (FREE, ~500 tok/s)

    WHY NOT JUST PICK THE TOP RESPONSE?
    ──────────────────────────────────────
    • Different models may say the same thing in different ways
    • Model A might have a detail that Model B omits, and vice versa
    • The Judge can MERGE complementary details into a richer answer
    • The final answer is usually better than any individual response

    The Judge uses temperature=0.2 (very low) for maximum consistency.
    Low temperature = model sticks closely to the input content.
    """
    try:
        from groq import AsyncGroq

        if not GROQ_API_KEY:
            print("  ⚠  GROQ_API_KEY not set — using simple fallback (no synthesis)")
            return _simple_merge_fallback(top_responses)

        client = AsyncGroq(api_key=GROQ_API_KEY)

        # Build the synthesis prompt
        responses_block = ""
        for i, resp in enumerate(top_responses, 1):
            score = resp.get("consensus_score", "N/A")
            responses_block += (
                f"\n{'─'*55}\n"
                f"RESPONSE {i}  |  Model: {resp['model']}"
                f"  |  Consensus Score: {score}\n"
                f"{'─'*55}\n"
                f"{resp['response']}\n"
            )

        judge_prompt = f"""You are a consensus synthesiser. You have received {len(top_responses)} responses from different AI models to the same question. These models were selected because they AGREE with each other the most.

ORIGINAL QUESTION:
{query}

THE {len(top_responses)} HIGHEST-CONSENSUS RESPONSES:
{responses_block}

YOUR INSTRUCTIONS:
─────────────────
1. Find the KEY FACTS and MAIN POINTS that all or most responses agree on
2. If responses differ on a detail, choose the most well-reasoned/supported view
3. MERGE complementary details — if one response adds a useful point the others missed, include it
4. Write ONE clear, structured, comprehensive final answer

The final answer should be BETTER than any individual response above.
Do NOT say things like "the models agree that..." — just write the answer directly.

FINAL CONSENSUS ANSWER:"""

        response = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",   # FREE on Groq
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert consensus synthesiser. You merge multiple AI "
                        "responses into one optimal, accurate, and comprehensive answer. "
                        "You write naturally and directly, not meta-commentary about the process."
                    )
                },
                {"role": "user", "content": judge_prompt}
            ],
            max_tokens=1500,
            temperature=0.2,   # Very low = stays close to input facts, doesn't hallucinate
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"  ⚠  Judge LLM error: {e}")
        return _simple_merge_fallback(top_responses)


def _simple_merge_fallback(top_responses: list[dict]) -> str:
    """Fallback: if the Judge fails, return the highest-scoring response directly."""
    if top_responses:
        best = top_responses[0]
        return (
            f"[No Judge available — showing highest-consensus response directly]\n\n"
            f"Model: {best['model']}  |  Score: {best.get('consensus_score', 'N/A')}\n\n"
            f"{best['response']}"
        )
    return "No consensus could be formed — all models failed or no responses available."


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — MAIN CONSENSUS PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

async def run_consensus(
    responses_file: str = "responses.json",
    top_k: int = 3,
    save_output: bool = True
) -> dict:
    """
    Full pipeline:
      Load → Filter → Similarity Matrix → Score → Rank → Select Top K → Judge → Answer

    Args:
        responses_file : JSON file from Phase 1 (default: responses.json)
        top_k          : Number of top-consensus responses sent to the Judge (default: 3)
        save_output    : Save final result to consensus_result.json (default: True)
    """
    start_time = time.time()

    print(f"\n{'═'*65}")
    print(f"  CONSENSUS AI — PHASE 2: CONSENSUS SCANNER")
    print(f"{'═'*65}\n")

    # ── Step 1: Load Phase 1 output ───────────────────────────────────────
    try:
        with open(responses_file, "r", encoding="utf-8") as f:
            broadcast_data = json.load(f)
    except FileNotFoundError:
        print(f"  ❌  File not found: {responses_file}")
        print(f"      Run Phase 1 first: python phase1_broadcast.py\n")
        return {}

    query     = broadcast_data["query"]
    all_resps = broadcast_data["responses"]
    timestamp = broadcast_data.get("timestamp", "unknown")

    print(f"  Query     : {query[:70]}{'...' if len(query) > 70 else ''}")
    print(f"  Saved at  : {timestamp}")
    print(f"  Models    : {len(all_resps)} total\n")

    # ── Step 2: Filter failed responses ──────────────────────────────────
    print(f"  [{1}/4] Filtering responses...")
    good = [r for r in all_resps if r.get("status") == "success" and r.get("response")]
    bad  = [r for r in all_resps if r.get("status") != "success"]

    for r in good:
        print(f"         ✅  {r['model']:<35} ({r.get('time_taken_seconds','?')}s)")
    for r in bad:
        print(f"         ❌  {r['model']:<35} {r.get('error','?')[:60]}")
    print()

    if len(good) < 2:
        print("  ❌  Need at least 2 successful responses to compute consensus.\n")
        return {}

    # ── Step 3: Similarity matrix ─────────────────────────────────────────
    n = len(good)
    print(f"  [{2}/4] Computing {n}×{n} similarity matrix...")
    sim_matrix = compute_similarity_matrix(good)

    # Pretty-print the matrix
    names = [r["model"] for r in good]
    max_w = max(len(n) for n in names)
    col_header = "  ".join(f"M{i+1:1d}" for i in range(n))
    print(f"\n         {'':>{max_w}}   {col_header}")
    for i, row in enumerate(sim_matrix):
        cells = "  ".join(f"{v:.2f}" for v in row)
        label = f"M{i+1} {names[i]:<{max_w}}"
        print(f"         {label}   {cells}")
    print()

    # ── Step 4: Score and rank ────────────────────────────────────────────
    print(f"  [{3}/4] Scoring consensus agreement per model...\n")
    scores = compute_consensus_scores(sim_matrix)

    for i, r in enumerate(good):
        r["consensus_score"] = scores[i]

    ranked = sorted(good, key=lambda x: x["consensus_score"], reverse=True)

    # Print rankings
    print(f"         {'Rank':<6} {'Model':<35} {'Score':<8} Agreement Bar")
    print(f"         {'─'*70}")
    for rank, r in enumerate(ranked, 1):
        bar_fill = int(r["consensus_score"] * 30)
        bar = "█" * bar_fill + "░" * (30 - bar_fill)
        flag = " 🏆" if rank <= top_k else "   "
        print(f"         #{rank:<5} {r['model']:<35} {r['consensus_score']:.4f}  |{bar}|{flag}")
    print()

    # ── Step 5: Select top K ──────────────────────────────────────────────
    top = ranked[:top_k]
    k   = len(top)
    print(f"  [{4}/4] Sending top {k} consensus responses to Judge LLM (Groq Llama 3.3 70B)...")
    print(f"         Selected: {', '.join(r['model'] for r in top)}\n")

    # ── Step 6: Judge synthesises final answer ────────────────────────────
    final_answer = await call_judge_llm(query, top)

    total_time = round(time.time() - start_time, 2)

    # Print final answer
    print(f"\n{'═'*65}")
    print(f"  ✅  FINAL CONSENSUS ANSWER")
    print(f"{'═'*65}\n")
    print(final_answer)
    print(f"\n{'═'*65}")
    print(f"  Consensus complete — total time: {total_time}s")
    print(f"{'═'*65}\n")

    # ── Build output dict ─────────────────────────────────────────────────
    result = {
        "query":                        query,
        "timestamp":                    datetime.now().isoformat(),
        "phase1_timestamp":             timestamp,
        "total_consensus_time_seconds": total_time,
        "models_evaluated":             len(good),
        "models_failed":                len(bad),
        "top_k_selected":               k,
        "consensus_rankings": [
            {
                "rank":               i + 1,
                "model":              r["model"],
                "provider":           r["provider"],
                "consensus_score":    r["consensus_score"],
                "time_taken_seconds": r.get("time_taken_seconds")
            }
            for i, r in enumerate(ranked)
        ],
        "similarity_matrix": sim_matrix,
        "model_names":       names,
        "final_answer":      final_answer,
        "top_responses_used": [
            {
                "model":           r["model"],
                "consensus_score": r["consensus_score"],
                "response":        r["response"]
            }
            for r in top
        ]
    }

    if save_output:
        out_file = "consensus_result.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"  💾  Full result saved to: {out_file}\n")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    """
    Reads responses.json produced by Phase 1 and runs the consensus pipeline.
    """
    await run_consensus(
        responses_file="responses.json",
        top_k=3,           # Use top 3 most-agreeing models as Judge input
        save_output=True   # Save result to consensus_result.json
    )


if __name__ == "__main__":
    asyncio.run(main())
