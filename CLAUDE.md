# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Read `AGENTS.md` first: it maps each kind of task to a skill in `skills/` (read that `SKILL.md` before the
task) and holds the original goals of the TFM. Decisions that changed since then are in
`docs/IMPLEMENTATION_ROADMAP.md`, which prevails over the other specifications in `docs/`.

## Commands

The local environment is Python 3.12 in `.venv` (same as Docker, CI and Render) and Node ≥ 20.19.

```sh
docker compose up --build                     # db + app on http://127.0.0.1:8000 (demo@scoremaster.local / scoremaster-demo)
docker compose up -d db                       # only PostgreSQL 17, on 127.0.0.1:5433 (credentials in .env)

npm --prefix frontend ci && npm --prefix frontend run build   # React → backend/app/static/frontend (FastAPI serves it at /)
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m backend.app.seed_demo     # demo user (DEMO_USER_EMAIL / DEMO_USER_PASSWORD)
.venv/bin/python -m uvicorn backend.app.main:app --reload
```

Tests:

```sh
export TEST_DATABASE_URL=$(grep ^DATABASE_URL .env | cut -d= -f2-)   # without it ~120 PostgreSQL tests are skipped
.venv/bin/python -m pytest -q backend/test
.venv/bin/python -m pytest -q backend/test/test_evaluation_api.py -k llm   # one file / matching tests
node --test backend/test/frontend/*.test.mjs  # frontend modules (they import frontend/src directly, no bundler)
.venv/bin/python -m evaluation.baseline       # frozen legacy capture: must keep matching
```

Each PostgreSQL test runs in its own schema migrated with Alembic (`postgres_engine` fixture in
`backend/test/conftest.py`). By default a fixed test user replaces the session; tests marked
`real_auth` use real sessions and CSRF (see the `clients` fixture in `test_library_api.py`). The conftest
also turns off the background audio preparation (`PLAYBACK_WARMUP=0`) and the database caches.

Browser walkthroughs are plain Node scripts `backend/test/frontend/*.e2e.mjs` run against a live server, as
in CI (`.github/workflows/ci.yml`): build the frontend, migrate, seed, start uvicorn on port 8006, then
`SCOREMASTER_URL=http://127.0.0.1:8006 PLAYWRIGHT_MODULE=<dir>/node_modules/playwright node backend/test/frontend/<name>.e2e.mjs`.
Playwright is installed outside the repo (`npm install --prefix <dir> playwright@1.63.0 axe-core@4.10.2`, then `playwright install chromium`).
`accessibility.e2e.mjs` audits every view with axe-core (WCAG 2.1 A and AA, light, dark and phone): the project must stay
WCAG 2.1 AA compliant (legal requirement for the author), so any violation fails CI.

There is no linter. CI also runs `pip-audit -r requirements.txt` and `npm --prefix frontend audit --omit=dev`.

## Architecture

Principle of the project: **data → algorithms → rules → generative AI**. ScoreLint (deterministic) is the
only source of musical facts; the LLM only explains or gives an independent opinion, never replaces them.

- `backend/domain`: framework-free model (`models.py`: `Score` → `ScorePart` → `ScoreMeasure` → `ScoreNote`,
  written pitch plus the part's transposition), instrument catalogue and resolver, timing helpers and the
  grade scale (`difficulty_scale.py`: index 0–10 → grades 1–6, rubric aligned with the publishers' Grade 1–6) and
  the publishers' grading guides as data (`grade_rubric.py`, difficulty-v3: the grades come from it).
- `backend/parsers`: MusicXML/.mxl → domain `Score` with music21 (`musicxml_parser.py`), sounding-pitch audio
  timelines (`playback.py`), `score_codec.py` (Score ⇄ JSON) and `reader.py`.
- `backend/analyzers` + `backend/rules`: the engines — difficulty (`rubric_grade.py` grades by the guides; the
  technical index stays for critical passages and explanations) and critical passages, band fit, rehearsal
  plan and proposal, concert series (`concert_plan.py`), evaluation sample, passage features for the LLM.
- `backend/application`: use cases and ports (`Protocol` repositories, AI port in `ai.py`, explanation and
  review services). `backend/infrastructure`: PostgreSQL repositories (SQLAlchemy) and AI providers
  (`ai/demo_provider.py`, `ai/gemini_provider.py`, prompts in `ai/prompts.py`).
- `backend/app`: FastAPI routes (`main.py` plus `*_routes.py`), dependency wiring (`dependencies.py`), security
  middleware (CSP, HSTS in production, Origin check) and `seed_demo.py`.
- `frontend/src`: React views (Resumen, Repertorio, Mi banda, Conciertos, Ensayos, Valoraciones,
  Configuración); API helpers and pure functions live in plain `.js` modules so Node tests can import them.

Cross-cutting rules that span many files:

- **Admin role**: only accounts in `ADMIN_EMAILS` (`is_admin` in `dependencies.py`) create and manage evaluation
  campaigns and see the musicians' emails and results; any other account, the demo included, only rates the
  campaigns it is invited to.
- **Ownership**: every query is filtered by the signed-in user; another user's object answers 404, the same as
  a missing one. State-changing requests need the session cookie plus the `X-CSRF-Token` header.
- **music21 is slow** (minutes per band score on Render's free plan): each uploaded file is parsed once, keyed
  by the sha256 of the bytes. The parsed `Score` and the audio timeline are kept in memory and in the
  `prepared_works` table; `reader.py` runs one music21 reading at a time (512 MB of memory); missing works are
  prepared at startup; `POST /playback` answers 202 and the browser polls while a long work is prepared.
- **AI layer**: evidence is built only from stored analyses and bounded; answers are Pydantic-validated and
  every cited id (`P1…` passages, `B1…` blocks, instrument names) is checked against the evidence; on any
  failure the deterministic demo answers and the UI says why. The demo is never presented as AI. Prompts,
  evidence and passage features are versioned (bump the version when the meaning changes) and valid answers
  are cached (`ai_explanations`). Gemini is used only with `GEMINI_API_KEY` (`GEMINI_MODEL`,
  `GEMINI_REVIEW_MODEL`, `GEMINI_REQUESTS_PER_MINUTE`); tests use fakes and never call Google.
- **Evaluation** (`evaluation/`, `docs/EVALUATION_AND_FEEDBACK.md`): campaign passages store ScoreLint's
  prediction (method A); the LLM's independent review (method B) must never receive ScoreLint's grade, index,
  dimensions or findings; the hybrid (C) is a rule preregistered on 2026-10-13 and must not be tuned on the
  musicians' ratings. `python -m evaluation.campaign_report <export.json>` produces the comparison.

## Conventions

- TDD: write the failing test first; refactors keep characterization tests. One objective per PR; squash merge.
- Branch names `feat/`, `fix/`, `docs/`. PR titles, bodies and squash messages in Spanish, without any
  attribution to Claude. Comments and identifiers in the code are in English; docs are in Spanish.
- Migrations live in `migrations/versions` with sequential ids (`0011_…`); check `alembic heads` when two
  branches add one.
- Never commit `test-scores/local/` (commercial scores), `backups/` (database copies), `evaluation/exports/`
  (real ratings) or local virtualenvs such as `.venv-3.9/`. Review `git status` before `git add -A`: a branch
  created before a `.gitignore` change can still pick them up.
- Deployment is the Render Blueprint `render.yaml` (free plan: 512 MB, slow CPU) with the data in Neon's free
  PostgreSQL (`DATABASE_URL` is a secret; Render's free database expired after 30 days); the procedure, the
  move to Neon and the backup scripts (`scripts/backup_db.sh`, `scripts/restore_db.sh`) are in
  `docs/DEPLOYMENT.md`.

# React Development & UI/UX Guidelines

## UX & Usability Principles
- **Accessibility (a11y):** Strictly adhere to WCAG 2.1 AA standards. Always include semantic HTML, proper `aria-*` attributes when building custom elements, and explicit `htmlFor` on labels.
- **State-Driven UX:** Always implement explicit loading, empty, and error states for asynchronous components to prevent Layout Shifts (CLS).
- **Visual Hierarchy:** Maintain a clear layout distinction using a strict 4px/8px spacing system. Ensure text elements have correct line-heights (minimum 1.5 for body text) for scannability.
- **Interactive States:** Every interactive component (`<button>`, `<a>`, custom clickable elements) must have polished `:hover`, `:focus-visible`, and `:active` styles.
- **Touch Targets:** Ensure interactive elements on mobile views have a minimum touch target size of 44x44px with adequate spacing.

## React Code Quality & Architecture
- **Functional Components:** Use functional components with hooks. Prefer semantic HTML tags (`<nav>`, `<main>`, `<aside>`, `<header>`, `<footer>`) over generic `<div>` soup.
- **Styles:** plain CSS in `frontend/src/styles.css` (no Tailwind, Sass or CSS modules); tokens live in its single `:root`. `backend/test/frontend/styles.test.mjs` keeps each top-level selector declared once and every class used by a component.
- **Component Isolation:** Keep components modular and reusable. Pass layout/spacing responsibilities via props or controlled class wrappers rather than hardcoding strict outer margins.

## Build and Commands
- Frontend while developing: `npm --prefix frontend run watch` (rebuilds into `backend/app/static/frontend`)
  next to `.venv/bin/python -m uvicorn backend.app.main:app --reload`; there is no separate Vite dev server.
- There is no linter or formatter configured in the frontend.
