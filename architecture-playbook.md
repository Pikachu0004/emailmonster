# Architecture Playbook

Default stacks and layouts to reach for when the user hasn't specified one. Deviate when the user has a stated preference, existing codebase convention, or constraint (hosting target, team skillset, etc.) — these are sane defaults, not rules.

## Picking a stack (when none is given)

| Project type | Default stack |
|---|---|
| Full-stack web app | TypeScript, Next.js (App Router), Postgres, Drizzle or Prisma as ORM, Tailwind for styling |
| API-only backend | TypeScript + Fastify/Express, or Python + FastAPI; Postgres; typed request/response schemas (Zod / Pydantic) |
| Mobile app | React Native + Expo (cross-platform) unless the user wants native iOS/Android specifically |
| CLI tool | TypeScript (Node) for JS ecosystems, or Python with `click`/`typer`, packaged properly (not a single loose script) |
| Data/ML pipeline | Python, with explicit dependency pinning (`pyproject.toml` / `requirements.txt` with versions, not bare `pip install`) |
| Static/marketing site | Astro or plain HTML/CSS if no interactivity is needed — don't reach for a full SPA framework when you don't need one |

Bias toward boring, widely-supported choices over the newest library. Novelty is a cost, not a feature, unless the user specifically wants to use something new.

## Standard full-stack folder layout

```
project-root/
├── apps/
│   ├── web/              # frontend
│   └── api/               # backend (if separate from web)
├── packages/
│   └── shared/             # shared types, validation schemas, utils
├── db/
│   ├── schema.ts           # or schema.prisma
│   └── migrations/
├── .env.example             # every env var the app needs, with placeholder values
├── .github/workflows/        # CI (lint, typecheck, test on push)
└── README.md
```

For smaller single-app projects, collapse `apps/web` and `apps/api` into one Next.js (or equivalent) app with API routes — don't over-engineer a monorepo for a project that doesn't need one. Introduce the monorepo split only when there are genuinely two or more deployable units.

## API contract discipline

- Define request/response types in one place (shared package, or an OpenAPI spec) and derive both the client and server from it — never maintain the same shape by hand in two places.
- Validate at the boundary: every API route validates its input against a schema (Zod, Pydantic, etc.) before touching business logic. Untrusted input is untrusted until validated, full stop.
- Version breaking API changes (`/v1/`, `/v2/`) rather than silently changing a contract that something else depends on.

## Environment & config

- Every required environment variable is listed in `.env.example` with a placeholder — a new developer (or a future agent run) should never have to guess what's needed.
- Secrets are read from environment variables, never committed, never hardcoded "temporarily."
- Fail fast and loud on startup if a required env var is missing — don't let the app boot into a half-configured state and fail mysteriously later.

## Database & migrations

- Schema changes go through migrations, not manual `ALTER TABLE` run once and forgotten.
- Every migration should be reversible or at least clearly documented if it isn't.
- Seed scripts for local dev data are separate from migrations — don't mix schema changes with data population.

## Monorepo vs. polyrepo

Default to a single repo unless the user has multiple teams, independent deploy cadences, or explicitly asks for separation. A monorepo with clear internal package boundaries (`packages/*`) gets most of the benefit of separation without the coordination overhead of multiple repos.

## Red flags to avoid

- A `utils.ts` or `helpers.py` that becomes a dumping ground for unrelated functions — group by domain instead.
- Business logic living inside route handlers or React components — pull it into a service/domain layer that can be tested without spinning up a server or a browser.
- Configuration values scattered across the codebase instead of centralized in one config module.
- "Temporary" scripts or hacks left in the main codebase without a clear removal plan.
