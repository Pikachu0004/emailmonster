# Agent-Building Patterns

Use this when the task is to design, build, or improve an AI agent — not just a regular feature. An "agent" here means something that uses an LLM to decide which actions to take, possibly across multiple steps, usually by calling tools.

## 1. Scope the agent in one sentence

If you can't state what the agent does in a single sentence ("answers customer billing questions using our order database" / "turns a GitHub issue into a draft PR"), the scope is too loose. A vague scope produces a vague, unreliable agent. Narrow it before designing anything else.

Prefer several narrow, reliable agents over one agent that tries to do everything. A narrow agent is easier to prompt well, easier to test, and fails in more predictable ways.

## 2. Tool design

- Each tool should do one clearly-named thing. `search_orders(customer_id)` is good; `do_customer_stuff(action, params)` is not — the model can't reliably decide what to put in a generic `action` field.
- Validate tool inputs with a schema. Don't trust the model to always produce well-formed arguments — validate and return a clear error the model can recover from, rather than crashing.
- Make tools idempotent where possible (safe to call twice). Agents retry; a non-idempotent side-effecting tool (e.g., "charge card") needs explicit guardrails — confirmation steps, idempotency keys, or human-in-the-loop — not just a hope that the model calls it once.
- Return structured, parseable results from tools, not a wall of prose the model has to re-interpret.
- Keep the tool list short and relevant to the task at hand. Every extra tool is something the model might misuse or get confused by.

## 3. System prompt as a contract

A good agent system prompt specifies, explicitly:

- **Role & scope** — what the agent is for, and just as importantly, what it's *not* for.
- **Constraints** — hard rules it must never break (e.g., "never issue a refund over $X without confirmation").
- **Output contract** — the exact format expected (plain text, JSON schema, a specific tool call), so downstream code can rely on it.
- **Failure/escalation behavior** — what to do when it's unsure, when a tool fails, or when a request is out of scope (ask, refuse, hand off to a human) — don't leave this implicit and hope the model improvises sensibly.

Avoid vague instructions like "be helpful and accurate" — that's not actionable. Specific, falsifiable instructions ("always cite the order ID you used" / "never fabricate a tracking number") are what actually change behavior.

## 4. State and memory

Decide deliberately:

- **Stateless per call** — simplest, safest, fine for most single-shot tasks.
- **Conversation-scoped memory** — needed for multi-turn tasks; budget how much history gets passed back in, since context isn't free (cost, latency, and the model attending to less-relevant old content).
- **Persistent memory across sessions** — only when there's a real need (a long-running project, personalization). Persistent memory adds real complexity: what gets stored, how it's invalidated, and what happens when it's wrong.

Don't default to "give it all the context, always" — irrelevant context degrades performance as often as it helps.

## 5. Orchestration: single agent vs. multi-agent

Start with a single agent. Split into multiple agents/subagents only when there's a concrete reason:

- Genuinely distinct expertise/instructions that conflict if combined into one prompt.
- A task that benefits from parallelism (e.g., researching several independent sources at once).
- Isolating a risky capability (e.g., code execution) behind its own tightly-scoped agent.

Multi-agent systems add coordination overhead and new failure modes (agents talking past each other, duplicated work). Don't reach for it as a default.

## 6. Error handling & retries

- Treat every tool call as something that can fail: timeout, bad input, upstream service down. Catch it and decide explicitly what the agent does next (retry with backoff, try an alternative, report to the user) — don't let an unhandled exception silently kill the run.
- Cap retries. An agent that retries forever on a persistent failure burns cost and time for no benefit.
- When the agent truly can't complete the task, it should say so clearly rather than fabricating a plausible-sounding but false result.

## 7. Evaluation before shipping

Write a small test set before calling the agent done:

- A handful of typical, expected inputs — does it behave correctly?
- At least one edge case (empty input, maximum-length input, conflicting instructions).
- At least one adversarial case (a user trying to get it to break a stated constraint, e.g., issue an unauthorized refund or ignore its scope).

Run the agent against these and check the actual output, not just "it probably handles this." If you can execute code in this environment, write this as an actual runnable eval script, not just a mental checklist.

## 8. Observability

Log, at minimum: which tools were called, with what arguments, what they returned, and the final decision/output. When something goes wrong in production, this is the difference between a five-minute diagnosis and an unreproducible mystery.

## Common anti-patterns

- A single tool with a huge free-form `input: string` parameter instead of a validated schema.
- A system prompt that's a wall of personality/tone instructions but never says what to do when something fails.
- No limit on tool-call loops — an agent that can call tools indefinitely with no step cap or budget.
- Shipping without ever having tried an adversarial or out-of-scope input against it.
