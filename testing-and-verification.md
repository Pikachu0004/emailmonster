# Testing & Verification

"I believe this works" is not a finishing condition. This file defines what counts as actually verified.

## The testing pyramid (default allocation)

- **Unit tests** (most of them) — pure functions, business logic, validation rules. Fast, no network/database, test one thing.
- **Integration tests** (some) — does the API route correctly talk to the database? Does the service correctly call the external API (mocked)?
- **End-to-end tests** (few, but real) — does the critical user path actually work through the real UI/API, start to finish? Reserve these for the paths that matter most (signup, checkout, the core workflow) — e2e suites that try to cover everything become slow and flaky.

Don't invert this pyramid: a project with only end-to-end tests (or only unit tests on trivial getters while the real logic is untested) is not well-tested, regardless of the test count.

## What to test, concretely

For any non-trivial function or endpoint:
- The expected/happy path.
- At least one edge case (empty input, boundary value, maximum size).
- At least one failure case (invalid input, a dependency that's down/errors) — confirm it fails the way you intend, not with an unhandled exception.

For anything involving money, auth, or irreversible actions (deletes, sends, payments): test these paths explicitly and don't skip them because they're "obviously fine."

## Verifying agents specifically

Standard unit/integration tests don't fully cover an LLM-driven agent, because its output isn't fully deterministic. Add:

- **A golden test set** — a fixed list of representative inputs with the expected tool calls or expected properties of the output (not necessarily an exact string match, but checkable: "did it call `issue_refund` with the right order ID", "did it refuse the out-of-scope request").
- **Regression checks** — before changing a system prompt or swapping a tool, run the golden set again and confirm nothing that used to work broke.
- **Adversarial cases** — at least one input that tries to get the agent to violate a stated constraint. If it doesn't hold the line, the constraint isn't actually enforced, it's just suggested.

## What "verified" means before calling something done

1. You ran the code (or the test suite) yourself, in this environment, and saw it pass — not just wrote it and reasoned that it should.
2. If you can't execute it in the current environment, say so explicitly and give the user the exact command to run and what success looks like — don't silently skip this step.
3. A fix for a bug includes a test that would have caught that bug, where practical — otherwise there's nothing stopping it from coming back.
4. Linting and type-checking run clean, not just "the obvious errors are gone."

## Red flags that mean "not actually verified"

- A test that was weakened (assertion loosened, case deleted) to make a failing suite pass, rather than fixing the underlying code.
- "It should work" as the final statement on a non-trivial change, with no run shown.
- A try/catch that swallows an exception just to make an error go away during testing.
