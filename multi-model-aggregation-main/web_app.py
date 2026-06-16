import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force UTF-8 output so Unicode box-drawing chars in phase1/phase2 don't crash the worker
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

from database import (init_db, save_query, get_history, get_query,
                       delete_query, get_account, update_account, get_stats)
init_db()

app = FastAPI(title="NEXUS Consensus AI")

# ── Consensus pipeline ────────────────────────────────────────────────────────

async def call_judge(query: str, top_responses: list) -> str:
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        formatted = "\n\n".join([
            f"**Model {i+1} — {r['model']}:**\n{r['response']}"
            for i, r in enumerate(top_responses)
        ])
        prompt = (f"You have received {len(top_responses)} AI responses that show high agreement. "
                  f"Synthesize them into one comprehensive, well-structured answer using markdown.\n\n"
                  f"**Question:** {query}\n\n**Responses:**\n{formatted}")
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You synthesize multiple AI responses into one superior, comprehensive answer."},
                {"role": "user",   "content": prompt}
            ],
            max_tokens=2000, temperature=0.2,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return top_responses[0]['response'] if top_responses else f"Synthesis error: {e}"


async def compute_consensus(broadcast_result: dict) -> dict:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    successful = [r for r in broadcast_result['responses'] if r['status'] == 'success']

    if len(successful) == 0:
        return {"ranked_models": [], "consensus_answer": "All models failed.", "top_k_models": []}

    if len(successful) == 1:
        r = successful[0]
        return {
            "ranked_models": [{"rank":1,"model":r['model'],"provider":r['provider'],
                               "response":r['response'],"consensus_score":1.0,
                               "time_taken_seconds":r.get('time_taken_seconds',0)}],
            "consensus_answer": r['response'],
            "top_k_models": [r['model']],
            "warning": "Only 1 model responded."
        }

    texts = [r['response'] for r in successful]
    vec = TfidfVectorizer(stop_words='english', min_df=1)
    mat = vec.fit_transform(texts)
    sim = cosine_similarity(mat)
    n   = len(texts)
    scores = [round((float(sum(sim[i])) - 1.0) / (n-1), 3) for i in range(n)]

    ranked = sorted(zip(successful, scores), key=lambda x: x[1], reverse=True)
    top3   = [r[0] for r in ranked[:3]]
    judge_answer = await call_judge(broadcast_result['query'], top3)

    return {
        "ranked_models": [
            {"rank": i+1, "model": r[0]['model'], "provider": r[0]['provider'],
             "response": r[0]['response'], "consensus_score": r[1],
             "time_taken_seconds": r[0].get('time_taken_seconds', 0)}
            for i, r in enumerate(ranked)
        ],
        "consensus_answer": judge_answer,
        "top_k_models": [r[0]['model'] for r in ranked[:3]]
    }


# ── Request models ────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    context: list = []        # [{"query": str, "answer": str}, ...] prior conversation turns
    conversation_id: Optional[str] = None

class AccountUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    organization: Optional[str] = None
    avatar_color: Optional[str] = None


# ── API Routes ────────────────────────────────────────────────────────────────

@app.post("/api/query")
async def run_query(req: QueryRequest):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")
    from phase1_broadcast import broadcast_to_all_models

    # Build context-enriched query for the models
    if req.context:
        ctx_lines = "\n\n".join(
            [f"Q: {c['query']}\nA: {c['answer']}" for c in req.context]
        )
        enriched = (
            f"You are answering in a multi-turn conversation. Here is the conversation so far:\n\n"
            f"{ctx_lines}\n\n"
            f"Now answer this follow-up question thoroughly: {req.query}"
        )
    else:
        enriched = req.query

    broadcast_result = await broadcast_to_all_models(enriched)
    broadcast_result['query'] = req.query   # show original (not enriched) in frontend
    consensus_result = await compute_consensus(broadcast_result)

    qid = save_query(
        query_text        = req.query,
        successful_models = broadcast_result.get('successful_responses', 0),
        total_models      = broadcast_result.get('model_count', 5),
        broadcast_time    = broadcast_result.get('total_broadcast_time_seconds', 0),
        responses_json    = broadcast_result.get('responses', []),
        ranked_json       = consensus_result.get('ranked_models', []),
        consensus_answer  = consensus_result.get('consensus_answer', ''),
        conversation_id   = req.conversation_id
    )
    return {"id": qid, "query": req.query,
            "broadcast": broadcast_result, "consensus": consensus_result}

@app.get("/api/history")
async def history(page: int = 1):
    return get_history(page=page)

@app.get("/api/history/{qid}")
async def history_item(qid: int):
    item = get_query(qid)
    if not item: raise HTTPException(404, "Not found")
    return item

@app.delete("/api/history/{qid}")
async def delete_item(qid: int):
    if not delete_query(qid): raise HTTPException(404, "Not found")
    return {"success": True}

@app.get("/api/account")
async def account():
    return get_account()

@app.put("/api/account")
async def save_account(u: AccountUpdate):
    update_account(u.name, u.email, u.organization, u.avatar_color)
    return get_account()

@app.get("/api/stats")
async def stats():
    return get_stats()

@app.get("/")
async def frontend():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")
