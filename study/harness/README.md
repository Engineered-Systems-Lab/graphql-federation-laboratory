# Study harness

The agent loop for the two vendors, the scoring and the run manifests of the [Abstraction ladder study](../README.md). Raw transcripts go to the machine-local `LAB_RESULTS_DIR`, never into this folder. The method is in the [agent scenario design](../../docs/PLAN.md#agent-scenario-design).

The tests use fake vendor clients and fake stacks. The first real calls were the smoke and pilot runs of 2026-10-20 (see [the pilot](#pilot-2026-10-20)), on the lead developer's keys, started by the lead developer from their own terminal: the first paid request is the live check of the vendor request shapes, and `--dry-run` exercises everything else first.

## Files

| File | Holds |
| --- | --- |
| `runner.py` | The run protocol, the plan, the manifest, the results, the bundle and the command line. |
| `agent.py` | One agent run: the shared system prompt, the loop, `submit_answer`, the limits, the retries. |
| `vendors.py` | The two vendor clients (Claude Sonnet 5.5 through the Messages API, GPT-6.1 Sol through the Responses API) behind one neutral interface. |
| `mcp_client.py` | The harness as the MCP client of a scenario's server, one session per run. |
| `budget.py` | The token budget with a reservation before each request. |
| `credentials.py`, `launcher.py` | The two API keys in Windows Credential Manager and the launcher that supplies them to the child process. |
| `study_gate.py` | The study test gate. |
| `models.json`, `prices.json` | The pinned models with their fixed request settings, and the dated price table. |
| `study-config.example.json` | The shape of the machine-local config. |
| `requirements.txt` | The pinned SDKs. Install them into a virtual environment outside the repository. |
| `test_*.py`, `fakes.py` | The tests and their fakes. |

## Models and settings

Two models, each through its own vendor API with the model id pinned. Each has one fixed request setting, recorded in every manifest and never tuned per scenario or task (`models.json`):

- `claude-sonnet-5-5`: adaptive thinking and effort `medium`, the starting point Anthropic's prompting guide gives for agentic tool use.
- `gpt-6.1-sol`: reasoning effort `medium` (its default). Tool calling works through the Responses API only, which is the one the client uses.

The SDK pins are in `requirements.txt` (`anthropic` 1.16.0, `openai` 3.35.1, `mcp` 2.3.0). SDK retries are switched off, so every retry is the harness's own, recorded and costed. Prompt caching differs by vendor and is not a setting: the OpenAI API caches repeated prefixes by itself, while the Anthropic client marks the end of the last message of every request with a cache breakpoint, so each turn of a run reads the earlier turns from the cache. Both are costed from the cached-read column of `prices.json`.

## The loop and the scoring

One shared system prompt for every scenario and model (answer with the tools you have, then call `submit_answer`; say so if something cannot be determined). Beta adds the guide document to that prompt. The tools are the scenario's MCP tools plus `submit_answer` with the task's fixed schema. The answer is scored by the corpus scorer (`study/corpus/scoring.py`, loaded from the corpus folder; no judge). A format error is tagged apart from a wrong answer. The task text is read from the corpus at run time and is copied nowhere.

Limits, the same for every scenario and model and configurable: tool calls, wall-clock seconds and tokens per task. Hitting one is scored `did_not_finish` with its reason, and everything spent is counted. A text-only reply is nudged to submit up to `max_nudges` times, then `did_not_finish` (`no_submission`). The numbers are set from the pilot, at about twice Alpha's worst pilot run.

## Token budget

The budget is in tokens per vendor, with input, cached read, cache write and output counted apart and never twice. The dollar estimate beside it comes from `prices.json`, which is dated; dollars are derived and never stored as raw data. Rules, from the lead developer and the Coordinator:

- Before each request the harness reserves its possible cost (the estimated current input plus the maximum output). A request that does not fit is a clean **budget stop**.
- Every reservation, settlement and retry is appended to the ledger (`budget-<vendor>.jsonl`) at once, and every vendor request is timed on its own (`requestStart`, `requestEnd` and `requestSeconds`, with no tool, ledger or scoring time in it) on the assistant turn of the transcript, on each retry event and on its settlement entry. A reservation that was never settled (the process died during a request) is charged in full on resume.
- A completed run is saved the moment it finishes. A budget stop ends the study cleanly with everything kept and the incomplete run archived under `attempts/`, never overwritten.
- `--resume` runs only the missing or incomplete runs and refuses a study whose plan, models, limits, prompt, guides, corpus or prices differ from the stored manifest.
- The pilot budget is 20 dollars per vendor; put the matching token figure in the config (`budgets.<vendor>.tokens`, no default) and the dollar figure in `dollar_ceiling`. Verify that each vendor console enforces its own cap; the harness enforces its own stop regardless.

## The run protocol

One stack run per scenario (the whole plot), with the models nested inside it (the sub-plot), sequentially. Per scenario: start the stack through the config's commands, wait until the MCP server answers, record the cold start and the cold first request, run the declared warm-up (`warmup_passes` passes over `warmup_calls`), then run every task and trial of the set with every model, and tear down. The order of the tasks and trials is shuffled from the recorded seed. The model order is interleaved per task and counterbalanced by cycling the model permutations from a seeded start. A category D task stops its service before its runs and restores it after. Every sample carries its phase (`cold`, `warm-up`, `measurement`) in `samples.jsonl`. A budget stop ends the whole study, so the order stays balanced for the resume. Subprocesses of the stack get an environment without the API keys.

Records, in `LAB_RESULTS_DIR/<study run id>/`: `manifest.json` (the commit, SDK versions, harness file hashes, models with their settings and price entries, prices date, limits, budgets, telemetry and router settings, dataset hashes, machine facts, stack facts, the plan and its hash), `samples.jsonl`, `budget-<vendor>.jsonl`, `runs/<key>/transcript.jsonl` and `result.json`, `scores.jsonl`, `scores.csv` and `bundle.json` with the checksum. Nothing written holds an absolute path or a key; the exact key values are also redacted from everything the harness writes. The MCP servers' call logs are matched to a run by the `X-Study-Run-Id` header, which carries the run key.

## Credentials

The two keys are generic credentials in Windows Credential Manager under names that do not depend on any repository:

| Vendor | Name | Variable the child receives |
| --- | --- | --- |
| Anthropic | `agent-study/anthropic-api-key` | `ANTHROPIC_API_KEY` |
| OpenAI | `agent-study/openai-api-key` | `OPENAI_API_KEY` |

Setup, once, by the lead developer in a PowerShell terminal (the keys are typed hidden, twice, and never appear in an argument, a file, a log or the shell history):

```powershell
py -3 study/harness/launcher.py --set-credentials
py -3 study/harness/launcher.py --check
```

`--check` prints present or missing for each credential and never a value. One command then runs a whole pilot or study run, the launcher starting the harness with the keys in the child process only:

```powershell
py -3 study/harness/launcher.py run -- --config <machine-local config> --run-id <new run id>
```

`--dry-run` after the `--` runs the whole protocol with a fake vendor client that spends nothing. If a key is missing the launcher looks first, then asks (hidden, twice, sanity check of the prefix and shape only, no API call) only in an interactive terminal; anywhere else it stops with a clear message, so a worker session never receives a key. `--set-credentials` replaces a key after a rotation. The launcher changes no global or user environment variable, no shell profile and no coding-assistant authentication. The harness itself reads the keys from the environment only, so explicit process-level injection works everywhere. Limitation: Credential Manager protects storage; it does not restrict retrieval to this application. Windows is implemented; the stores of other operating systems are deferred until they can be tested.

## Pilot (2026-10-20)

The pilot ran the development set (4 tasks) in Alpha and in Delta (Apollo) with both models, one trial: 16 runs in the run `pilot-1`, status complete, no retry, no budget stop, code at the commit that times every request. Bundle checksum (from `bundle.json`): `88629e9e8eb2560948d8ce84993fe170589a3ab018cafbbeb29cc80c3048c217`. The bundle stays machine-local in `LAB_RESULTS_DIR`. The scored corpus is frozen with the manifest checksum `e0e019c2987a9c3b81fa1602953df9cc6269f6af34dc1f3247136c886321651f` (see the [corpus freeze](../corpus/README.md#the-freeze)). Spend at the dated prices: about 0.83 dollars for Claude Sonnet 5.5 and 0.26 for GPT-6.1 Sol. Correct answers: 3 of 4 in Alpha and 4 of 4 in Delta, for each model. The two Alpha misses are one run that hit the tool call limit (Claude) and one name answered with a rank in front (GPT).

Settled for the study, by the lead developer:

- **Limits per task:** 80 tool calls, 1,000,000 tokens with cached reads counted (the cap is checked before each request) and 900 seconds of wall clock. The retries and nudges are unchanged.
- **Trials:** two, which is 320 runs (5 scenarios, 16 scored tasks, 2 models). A third trial may be added later from the same frozen corpus.
- **Scoring rule for names:** names are scored exactly and the scorer strips no rank. Every name field of the answer schemas says, in one text for both models, that the name is as the system records it, without rank or title.
- **Projection:** a scored task is taken to cost and take 3 times a development task (range 2 to 4). One trial is then about 21 dollars and 2.7 hours for Claude and about 6.7 dollars for GPT; two trials about 42 and 13 dollars, with 25 to 50 percent headroom proposed on top. Beta, Gamma and Epsilon are assumed from Alpha and Delta, not measured, and the dev set underrepresents the harder scored tasks.
- **Caching:** OpenAI caches repeated prefixes by itself; the Anthropic client marks the last block of each request, with a five-minute lifetime. Runs of one scenario share the system prompt and tool list, so a run can start on a cache warmed by the run before it. Cache-hit share is reported beside latency, and the timing baseline counts only runs made after the caching and request timing changes.

## Tests and the study gate

`python -B study/harness/study_gate.py` runs the offline tests of the study: this folder, the corpus derivation check and the MCP offline tests. It needs no stack and no key. The MCP suite needs the `mcp` package, which the governance interpreter does not have, so it runs under the interpreter named by the machine-local variable `STUDY_MCP_PYTHON` and is reported as NOT RUN when there is none (`--require-mcp` makes that a failure). The convention for the other study areas: put `test_*.py` files directly in the area's folder and list the folder in `SUITES` of `study_gate.py`. The live MCP stack tests (`study/mcp/test_mcp_stack.py`) are not part of the gate.

The area accepts Python, JSON, JSON Lines, TOML, Markdown and text files.
