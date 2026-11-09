# Issue tracker: Forgejo

Issues and specs for this repo live as issues on the self-hosted Forgejo at https://git.serrebiradio.com. Use the `tea` CLI (login `serrebiradio`) for all operations. Run it inside the clone, or pass `--repo serrebi/<repo>`. GitHub is not the issue tracker, even if a GitHub mirror exists.

## Conventions

- **Create an issue**: `tea issues create --title "..." --description "..."`. Use `--description-file -` with a heredoc for multi-line bodies.
- **Read an issue**: `tea issues <number>` (add `--comments` to include comments).
- **List issues**: `tea issues list --state open` with `--labels` and `--state` filters. Add `--output json` for machine-readable output.
- **Comment on an issue**: `tea comment <number> "..."`
- **Apply / remove labels**: `tea issues edit <number> --add-labels "..."` / `--remove-labels "..."`
- **Close**: `tea comment <number> "..."`, then `tea issues close <number>`.
- **Anything tea lacks**: `tea api /repos/{owner}/{repo}/...` calls the Forgejo REST API with the stored login.

## Pull requests as a triage surface

**PRs as a request surface: no.** _(Set to `yes` if this repo treats external PRs as feature requests; `/triage` reads this flag.)_

When set to `yes`, PRs run through the same labels and states as issues: `tea pulls list`, `tea pulls <number>`, `tea comment <number> "..."`, `tea pulls close <number>`.

Forgejo shares one number space across issues and PRs, so a bare `#42` may be either: try `tea pulls 42`, then `tea issues 42`.

## When a skill says "publish to the issue tracker"

Create a Forgejo issue.

## When a skill says "fetch the relevant ticket"

Read it as in **Read an issue** above.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `tea issues create --labels wayfinder:map`.
- **Child ticket**: Forgejo has no sub-issues. Add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: put a `Blocked by: #<n>, #<n>` line at the top of the child body. Forgejo issue dependencies (`tea api -X POST /repos/{owner}/{repo}/issues/<child>/dependencies -d '{"owner":"...","repo":"...","index":<blocker>}'`) may be added too, but the body line is canonical. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`tea issues list --state open`, scoped to the map's task list), drop any with an open blocker or an assignee; first in map order wins.
- **Claim**: `tea issues edit <n> --add-assignees serrebi`, the session's first write.
- **Resolve**: `tea comment <n> "<answer>"`, then `tea issues close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
