# Maintaining this skill (for DPYC maintainers, not end users)

This file is **not** part of the skill's runtime context — it's a note for whoever keeps the
skill accurate. End users never read it.

## How the skill stays current
The skill deliberately holds almost no hardcoded specifics. At run time it clones the live
`tollbooth-sample` repo and copies whatever is actually there — the wheel pin, the CI matrix,
the bootstrap anatomy. So **keeping the skill accurate mostly means keeping `tollbooth-sample`
accurate.** The template is the single source of truth that travels with the skill.

## The catch: the template lags the fleet
`tollbooth-sample` is the *definitive* template by intent, but the working edge of DPYC lives
in the production operators (excalibur, schwab, optionality, cypher, thebrain, ...). New,
better patterns land there first. The sample can fall behind — for example, long-runner
operators pin the `[nostr,prefect]` extra and the sample may still show `[nostr]`.

So the maintenance loop is:
1. Periodically survey the fleet for patterns that have advanced beyond the sample
   (bootstrap changes, new SDK conveniences, pin/extra changes, CI changes).
2. Fold the genuinely-better, generalizable ones back into `tollbooth-sample`.
3. The skill then picks them up automatically on its next run.

Handy surveys:
```bash
# every consumer's wheel pin and extras
grep -rhoE "tollbooth-dpyc(\[[a-z,]+\])?==[0-9.]+" --include=pyproject.toml --include=requirements.txt .
# who ships a per-call session module, and is it still live?
grep -rln "restore_oauth_session\|SessionCache" --include="*.py" .
```

## The reference docs DO carry a few specifics
`references/` names real SDK modules, two example operators (schwab, thebrain), and the
`read/write/heavy` categories. If the SDK renames a module or the exemplars change materially,
update the references. Keep them descriptive (patterns and boundaries), not prescriptive
copy-paste — the code specifics belong in the live template.

## Don't let the monorepo copy drift
The DPYC monorepo previously carried `.claude/commands/new-server.md`. That has been reduced to
a thin pointer to this skill so the two can't diverge. If you add operator-scaffolding guidance,
put it here (shipped, versioned) — not back in a monorepo-only command.
