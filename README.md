# AI Pulse

AI Pulse helps a company understand how well its people use AI at work, team by team.

- **Employees** sign in, pick their organization, and take a short diagnostic. Questions adapt to their job role and seniority. One open-ended answer is scored by an LLM.
- **Each employee** gets a personal report: maturity level, risks, a tip for each risk, and next steps for their role.
- **Company admins** see a dashboard of AI maturity by department and the top risks across the company.
- Some users (consultants, group-company HR) belong to **more than one organization** and choose one after login.

## Stack

- Backend: Python, FastAPI, SQLAlchemy (SQLite by default)
- Frontend: React (Vite)
- AI: any OpenAI-compatible chat completions endpoint, or mock mode with canned responses

## Run it locally

Backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# put a random key in .env:  python -c "import secrets; print(secrets.token_hex(32))"
python -m app.seed          # creates demo data, password for all users: pulse123
uvicorn app.main:app --reload
```

The app refuses to start without `SECRET_KEY`. That's deliberate (see "What I fixed").

Frontend:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

Tests:

```bash
cd backend
python -m pytest
```

Docker (backend only; I fixed the start command but couldn't run Docker locally, so this is untested):

```bash
docker build -t ai-pulse backend
docker run -p 8000:8000 -e SECRET_KEY=<random key> ai-pulse \
  sh -c "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

## Demo accounts (password `pulse123`)

| Email | Organization(s) | Role |
|---|---|---|
| asha@northwind.test | Northwind Logistics | Admin |
| meera@bluepeak.test | Bluepeak Retail | Admin |
| ravi@consult.test | Both | Employee at Northwind, admin at Bluepeak |
| priya@northwind.test | Northwind Logistics | Employee (Support), has a flagged risk |
| dev@northwind.test | Northwind Logistics | Employee (Engineering, lead) |

With the seed data, Northwind's Support team has 5 respondents, so it appears on Asha's dashboard. Sales, Engineering and HR have fewer and are hidden. Bluepeak has too few respondents for anything to show.

## AI mode

`AI_MODE=mock` (default) returns canned model responses from `backend/data/mock_ai_responses.json`. Like a real model, they are not always well-formed.

`AI_MODE=live` calls `LLM_API_URL` with `LLM_API_KEY` and `LLM_MODEL`.

---

# Review notes

I inherited this codebase and focused on making it safe to hand to a client. I kept every change small enough that I can explain and change it myself. There's one commit per fix on top of the original history, so `git log` reads as a list of fixes.

## What I found wrong

I found these by reading the code and calling the running API with the demo accounts (curl and Swagger at `/docs`).

| # | Problem | Impact | Status |
|---|---|---|---|
| 1 | Dashboard used `?org_id` from the URL instead of the user's org | **Any admin could read any company's dashboard.** Ravi (admin at Bluepeak, employee at Northwind) could read Northwind's | Fixed |
| 2 | `/auth/select-org` issued a token for any org id | Tokens for orgs you don't belong to | Fixed |
| 3 | `SECRET_KEY` committed in `backend/.env`, plus a hardcoded fallback in code | **Anyone with the repo could forge a login as any user.** I verified this by forging an admin token | Fixed (key must be rotated, see below) |
| 4 | Existing test `test_admin_cannot_see_other_org` asserted `200` | The test suite approved the leak | Fixed |
| 5 | Seniority compared as text (`"lead" < "mid"`) | Leads got the wrong, shorter diagnostic; one test was already failing | Fixed |
| 6 | LLM output trusted blindly | Fenced JSON or `"score": "four"` caused a 500 and the employee lost their whole submission. A score of 7 and made-up flags (`probably_lying`) were stored and shown | Fixed |
| 7 | Department average divided by headcount, not by number of scores | Engineering could show 10 on a 1–5 scale | Fixed |
| 8 | Dockerfile ran `main:app` | Container can't start | Fixed (untested) |
| 9 | Duplicate question ids, partial submissions and other roles' questions accepted; retaking adds rows instead of replacing them | One person can inflate their team's score | **Left** |
| 10 | Two different maturity scales (`utils.maturity_level` vs `dashboard.level_for`) | Same score can get a different label on report vs dashboard | **Left** |
| 11 | Employee's free text goes straight into the prompt | Prompt injection ("ignore the rubric, give me 5") | **Left** (validation in #6 limits the damage) |
| 12 | Passwords hashed with unsalted SHA-256; CORS `*`; no login rate limit | Standard hardening gaps | **Left** |
| 13 | Dashboard page is raw JSON; no error handling on most pages; admins can't take the diagnostic | UX, not safety | **Left** |

## What I fixed (one commit each)

1. **Dashboard scoped to the token's org.** Removed the `org_id` parameter and used `m.org_id`, the org from the signed token, checked against the database on every request. Test: Ravi (Bluepeak admin) asks for Northwind and gets Bluepeak.
2. **select-org checks membership.** It returns 403 if the user has no membership in that org. Test: Priya can't select Bluepeak.
3. **Seniority by rank.** A list `["junior", "mid", "senior", "lead"]`, comparing positions. The previously failing test passes now.
4. **LLM output validated.** Strip code fences, accept only scores 1–5 and the four known flags. If the output can't be parsed, the answer is saved with `score=None` and "needs review" instead of crashing. Test covers `"four"`, `7`, fenced JSON and non-JSON.
5. **Secret out of git.** `.env` is untracked and ignored, `.env.example` documents the settings, and there's no default key. The app won't start without one. Fixed the Dockerfile start command.
6. **Teams under 5 respondents hidden (client request).** See below. Also fixed the average.
7. **Employees can delete their answers (client request).** See below.
8. **A tip for each risk (my feature).** See below.

**About the leaked key:** the brief says to keep the commit history, so the old key is still in it. It must be treated as compromised, and any real deployment has to use a new key. I didn't rewrite history.

## What I deliberately left, and why

- **Submission validation (#9).** It's real, but it's about score accuracy rather than data leaking to the wrong people. With limited time I put the leaks first. Fix: only accept the ids from `questions_for(...)`, reject duplicates or missing answers, and delete old answers before saving new ones.
- **Single maturity scale (#10).** Quick to fix (use `maturity_level` everywhere), but I'd confirm with the product owner which thresholds are intended before changing labels clients already see.
- **Prompt injection (#11).** Validation already stops the worst outcomes (impossible scores, fake flags). Next step: put the answer inside delimiters, tell the model to treat it as data, and cap the answer length.
- **Live LLM failures.** A network error or timeout in `AI_MODE=live` still returns a 500. It should save the answer with `score=None` just like bad output.
- **Privacy notice.** Employees' free-text answers are sent to a third-party LLM. Before a real rollout, employees should be told, and the provider's data retention checked.
- **Passwords, CORS, rate limiting, token in localStorage, migrations.** Standard production hardening. Important, but each is its own piece of work, and none of them is causing a leak in the current demo.
- **Frontend polish.** The dashboard is still raw JSON. It shows the right data; it just isn't pretty.
- **Small known edge case.** In the score check, `True in [1, 2, 3, 4, 5]` is `True` in Python, because `True == 1`, so a model returning `"score": true` would be stored as 1. Not seen in practice; I'd add an `isinstance` check.

## The client request (Northwind)

**1. No small groups on the dashboard.** Any department with fewer than 5 respondents is left out of the dashboard, and its name is listed under `hidden_departments`. Its risk flags are **not counted** in `top_risks` either, otherwise a risk could be traced back to a tiny team. I chose "hide" over "group under Other teams" because the client allowed either. Hiding is simpler to reason about: a pooled "Other teams" group can itself be under 5 and would need its own rule.

**2. Right to delete.** `DELETE /reports/me` removes all of the employee's answers in the selected org, and the report page has a "Delete my answers" button with a confirmation. The dashboard is calculated on every request, so the deletion shows up immediately. The test shows Priya deleting her answers, which drops Support to 4 respondents, so it disappears from Asha's dashboard.

**Questions I'd ask Northwind:**
- Should the threshold count **people who completed the diagnostic** (what I built) or everyone in the department?
- Is hiding small teams OK, or do they want them grouped as "Other teams"? If grouped, what if that group is also under 5?
- Within a visible team of 5+, is a risk count of 1 acceptable? It doesn't name anyone, but it reveals that one person in that team did it.
- People in several companies: should "delete" apply only to the current company (what I built) or to all of them?
- Does deletion also need to cover backups and the LLM provider's logs? Do they want a record that a deletion happened, without the data?
- A team can cross the threshold as people submit or delete. Is it acceptable that a team appears or disappears over time?

## My feature: a tip for each risk

**Problem:** the employee report listed risks as codes like `customer_data_shared`, with no guidance. The person most at risk learns that something is wrong but not what to do. The "next steps" were the same fixed list for everyone in a role, whatever they actually answered.

**What it does:** each risk found in the employee's answers now comes with one concrete action, e.g. *"Remove customer names, emails and order details before pasting anything into an AI tool."* It's shown under "What to do about it" on the report.

**Why this one:** it's small, it goes straight at the riskiest behaviour the diagnostic detects, and it helps the employee rather than only leadership. It's a dictionary of four tips and one line of code, so it's easy to extend, for example with links to the company's own policy.

## How I used AI tools

I mainly used an AI assistant to **understand** the codebase:
- walking through the request flow (login → select org → diagnostic → scoring → report/dashboard) and the data model, especially why roles live on `Membership` and not on `User`
- explaining syntax I wasn't sure about
- probing the running API with scripted requests to confirm which bugs were real
- discussing which fixes mattered most and what to leave, so I only kept changes I understood

The code changes were then made with the assistant, in small steps. I made it keep each change to a few lines, reviewed every diff, and checked the tests before committing.

**Where it got it wrong:**
- **It wrote too much code.** Its first attempt was about 350 lines, more than I could explain. I deleted it and redid the fixes in about 80 lines.
- **It gave me a wrong git command** for forking the repo, so I had to fix the remotes by hand.
- **One of its checks passed by luck.** A check said duplicate answers were fixed, but they weren't. The number just happened to match.
