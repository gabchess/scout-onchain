# Independent DeFi evaluation protocol

An independent AI reviewer writes fresh scenarios and freezes a source-backed rubric before seeing Scout's answers. The builder cannot call its own grading an independent review. This protocol provides bounded evidence about the tested host; it does not provide human financial certification.

The retained first review is in [`evals/independent-defi`](../evals/independent-defi/README.md).

## Reproduce a run

Install the package's MCP dependencies and authenticate Codex CLI separately. Running this command uses that host's model allowance. The fixture MCP receives no live provider credentials.

```sh
python scripts/run_host_evaluation.py \
  --suite /absolute/path/to/frozen-suite.json \
  --repo /absolute/path/to/frozen-scout-checkout \
  --output /absolute/path/to/new-evaluation-directory
```

Before spending model calls, the runner starts the configured MCP interpreter, lists its tools and verifies one fixture response over stdio. A failed preflight stops the run. Virtual environment interpreter paths retain their symlink so installed dependencies remain available.

The runner forwards only each prompt. Reference answers and criteria stay outside the answering model's context. Each case starts a fresh ephemeral Codex session with Scout skill context and the fixture MCP. Shell, web and agent delegation tools are disabled. The runner records suite, context and runtime hashes, raw responses, tool events, duration and process status. It stops if the runtime changes. It refuses to overwrite an existing evaluation directory.

## Review and publication

The reviewer grades each criterion against the frozen rubric and quotes the exact supporting or failing answer. Critical errors are reported separately from omissions. The reviewer must inspect tool traces for false live-data or execution claims. A process exit code of zero is not an advice-quality pass.

After the first run, the cases are known regression cases. Corrections belong in general instructions or validated tools, rather than embedding the held-out answer. Use a newly authored holdout to check whether a correction generalizes. Preserve original failures with the corrected results.

Public results must name the evaluated source revision and host mode. Native plugin activation, live provider behavior and transaction execution need separate evidence. An AI review artifact does not satisfy a GitHub rule requiring an approving review from an eligible account.

## Host context limits

The context hash identifies the Scout text supplied by this runner. Codex may still discover global skill metadata despite `--ignore-user-config` and the experimental discovery flag. Retain startup warnings with the result and disclose this limitation. The default model is selected by the authenticated host unless separately pinned, so a repeated run may use a different model. A run with injected skills is distinct from a native plugin activation test.
