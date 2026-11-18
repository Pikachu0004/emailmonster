# Code Review Checklist

Run this pass deliberately before declaring a feature or project "done" — this is the "harden" phase, not something to skip under time pressure.

## Security

- [ ] No secrets, API keys, tokens, or credentials hardcoded or committed — all come from environment variables or a secrets manager.
- [ ] All user input is validated and sanitized at the boundary (API routes, form submissions, tool calls) before use.
- [ ] Database queries use parameterized queries / an ORM — never raw string-concatenated SQL.
- [ ] Authentication is checked on every route that needs it, including "obvious" internal-only ones.
- [ ] Authorization is checked, not just authentication — a logged-in user can still access another user's data if object-level checks are missing (IDOR).
- [ ] File uploads are validated by content, not just filename/extension, and stored outside the web root or in object storage with restricted access.
- [ ] Dependencies are pinned to known versions; no wildcard version ranges for anything security-sensitive.
- [ ] Error messages returned to the client don't leak stack traces, internal paths, or database details.
- [ ] Rate limiting exists on anything that's expensive or abusable (auth endpoints, search, anything hitting a paid external API).
- [ ] CORS is explicitly configured, not wide open to `*` for anything handling authenticated requests.

## Correctness

- [ ] Edge cases are handled: empty input, null/undefined, very large input, concurrent requests to the same resource.
- [ ] Off-by-one and boundary conditions in loops, pagination, and date ranges are checked, not assumed.
- [ ] Async code handles rejected promises / exceptions — no unhandled rejections.
- [ ] State mutations are intentional — no accidental sharing of mutable state across requests (a classic source of "works locally, breaks under load" bugs).
- [ ] Timezones and date handling are explicit (store in UTC, convert at display time) — don't let this be implicit and hope it works out.

## Performance

- [ ] No N+1 queries — check anything that loops and queries inside the loop.
- [ ] Indexes exist on columns used in `WHERE`, `JOIN`, and `ORDER BY` clauses for anything beyond a tiny table.
- [ ] Large lists are paginated, not loaded in full and filtered client-side.
- [ ] Expensive operations (image processing, large exports, third-party API calls) happen off the request path (background job/queue) when they'd otherwise block a user-facing response.
- [ ] No obvious O(n²) behavior on data that can grow (nested loops over the same collection where a map/set lookup would do).

## Maintainability

- [ ] Functions and modules have a single clear responsibility — if a function needs "and" to describe what it does, consider splitting it.
- [ ] Naming is specific and accurate — no `data`, `temp`, `handler2`, `thing` left in the final version.
- [ ] No dead code, commented-out blocks left "just in case," or unreachable branches.
- [ ] Non-obvious decisions have a short comment explaining *why*, not a comment restating *what* the code already says.
- [ ] Tests exist for the core logic and will actually fail if the logic is broken (not a test that just asserts `true`).
- [ ] The README/setup instructions were actually followed from a clean state to confirm they work, not just written and assumed correct.

## Final sanity check

- [ ] You ran it. It worked. You didn't just read the code and conclude it should work.
