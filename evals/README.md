# Scout honesty evals

This harness scores agent-facing answers against `CLAIMS.md` and the checked-in
portfolio and price-history fixtures. Deterministic checks are the primary gate and
need no network, API key, or model dependency.

## Run offline

From the repository root:

```bash
python3 scripts/scout_eval.py --offline
```

The bundled examples in `evals/cases.json` pass their own candidate `output`.
To evaluate captured agent answers, pass a JSON object keyed by case ID:

```bash
python3 scripts/scout_eval.py --offline --responses path/to/responses.json
```

An answer can be a string or JSON value. The fixture equality check compares
structured holdings directly with `fixtures/portfolio.json`; text checks enforce
mode, safety, claims, and install markers.

## Optional AI Gateway judge

Live judging is opt-in. Use a Vercel AI Gateway key through the
`AI_GATEWAY_API_KEY` environment variable, then run:

```bash
python3 scripts/scout_eval.py --judge
```

The default model is `google/gemini-2.5-flash-lite`; override it with
`--model openai/gpt-5-nano`. Requests use short prompts, at most 100 output tokens,
and the reporting tag `feature:scout-eval`.

Use `--dry-run` to inspect every request body without sending or spending:

```bash
python3 scripts/scout_eval.py --dry-run
```

If the key is absent, `--judge` skips cleanly. On HTTP 402, the runner stops the
suite and does not retry. Use a project-scoped key with a budget set by the
operator. This repository supplies no key and grants no spending authority.

CI runs the offline suite by default. The live job can run only through a manual
workflow dispatch with `live_judge` enabled and the `AI_GATEWAY_API_KEY` repository
secret present.
