# Public documentation policy

[English](PUBLICATION_POLICY.md) · [Bahasa Indonesia](id/PUBLICATION_POLICY.md)

The `docs/` directory is the public-documentation boundary inside the
InterrupThink source repository. The root README, `cases/`, `examples/`, and
the library docstrings are also user-facing material. They are curated for
readers who need to understand and reproduce the library, not for publishing
the complete internal research notebook.

## Allowed content

Add content when it is:

- written in English;
- useful to a library user, evaluator, or contributor;
- supported by source code, a committed test, or a sanitized run result;
- reproducible without private credentials;
- explicit about scope, uncertainty, and limitations;
- free of private prompts, raw model traces, and personal data.

Public evaluation pages may describe the scenario, method, observed outcome,
source test, and limitation. They must not turn a single fixture into a
general safety or quality claim.

## Excluded content

Do not copy any of the following into `docs/`:

- internal plans, gates, task identifiers, experiment-card identifiers, or
  shorthand labels that only make sense inside the research notebook;
- local lab files that are not published (`plan/`, including `plan/STATUS.md` and `plan/AGENTS.md`);
- raw prompts, private memos, hidden reasoning, or model transcripts;
- `.env` files, API keys, tokens, certificates, or credential paths;
- generated `runs/`, `tmp/`, log, cache, or local environment artifacts;
- personal names, private infrastructure details, or customer information;
- unpublished architectural decisions or internal project status;
- claims that have no test, run record, or reproducible procedure.

The research notebook remains internal. Public documentation should summarize
evidence without exposing the notebook's private coordination or planning
details.

## Review checklist

Before publishing a change:

- [ ] The page is English and has a clear audience.
- [ ] Every numeric or behavioral claim has a source test or run record.
- [ ] The page distinguishes deterministic tests from live-model checks.
- [ ] The page states relevant limitations and untested conditions.
- [ ] No internal identifiers or private research content appear.
- [ ] User-facing Markdown and docstrings use plain descriptions instead of
      lab labels or task numbers.
- [ ] No secret-like value or generated artifact is included.
- [ ] Links and code blocks were checked from the repository root.
- [ ] The full diff contains only the intended documentation change.

## Correction policy

If a public result is wrong, correct the page and preserve a short explanation
in the commit message. Do not rewrite a failed result into a success. If the
source test or protocol changed, update the method and limitation together.
