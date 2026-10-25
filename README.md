# College Handbook Portal (RAG chatbot)

Students log in and chat with the **Student Handbook**. Faculty log in and chat with the **Faculty Handbook**.
Answers are short, in simple English, and show the **handbook page and section** they came from.
The two handbooks are completely separate, and the **backend** enforces it.

```
Browser (Next.js on Vercel)  --HTTPS + JWT-->  FastAPI (Render)
                                                 | role comes from the verified token + database, never from the request
                                   +-------------+-------------+
                              student role                 faculty role
                                   v                           v
                        Student index (own folder)   Faculty index (own folder)
                        BM25 + FAISS                 BM25 + FAISS
                                   +-------------+-------------+
                                                 v
                                   LLM (free tier, OpenAI-compatible API)
```

## 1. Run it locally

Needs Python 3.11+ and Node 20+.

```bash
# --- backend ---
cd backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python scripts/init_env.py           # creates .env, random JWT secret + demo passwords (printed once)
```
Open `backend/.env` and paste your free LLM key into `LLM_API_KEY=` (no card needed: https://console.groq.com/keys).

```bash
python -m app.rag.ingest             # ONE-TIME: builds both knowledge bases (downloads the ~130 MB embedding model)
python scripts/eval_retrieval.py     # optional: retrieval quality check + scores for tuning
python -m pytest tests -q            # optional: 49 tests
uvicorn app.main:app --reload --port 8000
```
```bash
# --- frontend (new terminal) ---
cd frontend
cp .env.example .env.local           # Windows: copy .env.example .env.local
npm install
npm run dev                          # http://localhost:3000
```
Log in with `student1` / `faculty1` and the passwords `init_env.py` printed (also stored in `backend/.env`).
**Accounts from college IDs (recommended).** List the IDs in `backend/users.csv` (columns `id,name,role`; only `id` is required, role defaults to `student`, use `faculty` for staff), then run:
```bash
python scripts/import_users.py users.csv
```
Each new ID gets its own random temporary password, saved to `credentials_<date-time>.csv` and printed. Give each person only their own row, then delete the file. At first login the user must choose their own password; after that there is no "change password" option in the chat. On the login page, "Forgot password?" tells people to contact the college office; the administrator then runs `python scripts/reset_password.py <id>` to issue a new temporary password (they must choose a new one at next login, and all their old sessions are signed out). Set the office contact line shown there in `frontend/lib/brand.ts` (`RESET_CONTACT`). `users*.csv` and `credentials_*.csv` are git-ignored because they hold real IDs and passwords.

**Optional self sign-up.** Login page → "Create an account" appears only when you set an access code in `backend/.env` (`STUDENT_SIGNUP_CODE`, `FACULTY_SIGNUP_CODE`). Keep the faculty code private; without it nobody can get a faculty account. Leave a code empty to close sign-up for that role (recommended once your roster is imported, so nobody can register someone else's ID first).
You can also add a user manually: `python scripts/add_user.py <id> "<Full Name>" <student|faculty>`.
If you replace a handbook PDF in `backend/data/handbooks/`, re-run `python -m app.rag.ingest`.

## 2. How the separation is enforced
- Two endpoints, `POST /api/student/chat` and `POST /api/faculty/chat`, each guarded by `require_role(...)`. Wrong role gives **403**.
- The role is read from the **database row** of the user in a verified, non-revoked JWT. If the token's role claim disagrees with the database it is rejected. Anything a client sends in the body (`role`, `handbook`) is ignored.
- Each role has its own folder (`data/index/<role>/`) with its own chunks and FAISS index. The loader refuses an index containing chunks from another role, and the pipeline re-checks every chunk before building the prompt.
- Chat history is always queried by the logged-in user's id.
- `backend/tests/test_isolation.py` inspects the actual LLM prompt to prove no text from the other handbook is ever included.

## 3. How answers stay accurate
1. **Page-aware extraction** (PyMuPDF): headings (bold lines), tables (kept as Markdown), printed and PDF page numbers, table-of-contents pages excluded.
2. **Hybrid retrieval**: BM25 keyword search + embeddings (`bge-small-en-v1.5`) in FAISS, merged by reciprocal-rank fusion. Top 5 chunks.
3. **Relevance gate**: obviously unrelated questions are refused without calling the LLM.
4. **Strict prompt**: use only the excerpts, answer `NOT_FOUND` if the answer isn't there, keep numbers exact, never merge rules for different groups (UG/PG/PhD/Agriculture, teaching/non-teaching), cite `[n]`.
5. Only the excerpts the model actually cited are shown as sources.

Tuning: run `python scripts/eval_retrieval.py`. If valid questions are wrongly refused, lower `DENSE_MIN_SCORE` / `MIN_COVERAGE`; if off-topic questions get through, raise them.

## 4. Deploy (free)

**Backend on Render**
1. Push the repo to GitHub (**private** recommended: it contains the handbooks and index). Commit `backend/data/index/` (the built indexes; run the ingest step first).
2. Render > New > Blueprint > select the repo (uses `render.yaml`). Or create a Web Service manually: root dir `backend`, build `pip install -r requirements.txt && python -m app.rag.embeddings --warmup`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'`.
3. Environment variables: `LLM_API_KEY`, `LLM_REASONING_EFFORT=low`, `EXTRA_USERS` (accounts re-created at every start, format `id|name|role|password;id|name|role|password`), `STUDENT_SIGNUP_CODE`, `FACULTY_SIGNUP_CODE`, `DEMO_STUDENT_PASSWORD`, `DEMO_FACULTY_PASSWORD`, `CORS_ORIGINS` (your Vercel URL, no trailing slash), `ENV=production`, `JWT_SECRET` (auto-generated by the blueprint).

**Frontend on Vercel**
1. Import the repo, set **Root Directory = `frontend`** (Next.js is auto-detected).
2. Environment variable: `NEXT_PUBLIC_API_URL=https://<your-service>.onrender.com`.
3. Deploy, then put the Vercel URL into Render's `CORS_ORIGINS` (for preview URLs also set `CORS_ORIGIN_REGEX`).

## 5. Free-tier limits you should know
- **LLM (Groq)**: Groq now restricts its Llama models to Enterprise accounts (a normal key gets a 404), so the defaults are `openai/gpt-oss-120b` with `openai/gpt-oss-20b` as automatic fallback. Free-plan limits and model names change: check your own limits at https://console.groq.com/settings/limits and the model list at https://console.groq.com/docs/models. Gemini and OpenRouter presets are in `.env.example`. Free tiers may use prompts to improve their service: don't type personal data into questions.
- **Render free**: sleeps after ~15 min idle (first request can take about a minute; the UI shows a "waking up" note), 512 MB RAM, and the **disk is wiped on every restart, redeploy and spin-down (Render's docs), so accounts created on the site and all chat history are lost.** Accounts listed in `EXTRA_USERS` (and the two demo accounts) are re-created at every start, so use those for a demo. Locally users are kept in `backend/data/portal.db`. For a real deployment with many users, move the user table to a free hosted database (for example Neon Postgres); ask for this step when you are ready. If the embedding model runs out of memory, set `RETRIEVAL_MODE=bm25` (keyword-only, tiny memory). Confirm current limits at https://render.com/pricing.
- **Vercel Hobby**: free for personal, non-commercial use.

## 6. Files
```
backend/app/main.py          API routes, CORS, error handling
backend/app/security.py      bcrypt, JWT, role guards, rate limiting
backend/app/db.py            SQLite: users, per-user history, revoked tokens
backend/app/rag/ingest.py    PDF -> page-aware chunks -> FAISS (run once)
backend/app/rag/store.py     per-role knowledge base, hybrid search, relevance gate
backend/app/rag/pipeline.py  prompt, anti-hallucination rules, citations
backend/app/rag/llm.py       OpenAI-compatible client with fallback model
backend/scripts/             init_env.py, add_user.py, eval_retrieval.py
backend/tests/               49 tests (auth, isolation, RAG, LLM errors)
frontend/app/                landing, login, dashboard
frontend/components/         Chat, SourceList, MessageText, Brand
frontend/lib/                api client, theme, brand (edit brand.ts to rebrand)
```
Note: the "Faculty Handbook" PDF is titled *Staff Handbook* and covers teaching and non-teaching staff; the assistant labels rules by group.
