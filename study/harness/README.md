# Study harness

The agent loop for the two vendors, the scoring and the run manifests of the [Abstraction ladder study](../README.md). Raw transcripts go to the machine-local `LAB_RESULTS_DIR`, never into this folder. The method is in the [agent scenario design](../../docs/PLAN.md#agent-scenario-design).

The tests use fake vendor clients and fake stacks. The first real calls were the smoke and pilot runs of 2026-10-20 (see [the pilot](#pilot-2026-10-20)), on the lead developer's keys, started by the lead developer from their own terminal: the first paid request is the live check of the vendor request shapes, and `--dry-run` exercises everything else first.

## Files

| File | Holds |
| --- | --- |
| `runner.py` | The run protocol, the plan, the per-block checks and the vendor-error requeue of the schedule, the manifest, the results, the bundle and the command line. |
| `schedule.py` | Study 2's block schedule: the Williams square, the seeded letters, round order, halves and model split, the order inside a block, and the reference block. |
| `harness_tools.py` | The two harness tools, `calculate` and `ask_requester`, the result ids and the per-run store of tool results. |
| `scoring_contract.py` | The declared contract through which the harness calls a corpus's scorer. |
| `agent.py` | One agent run: the shared system prompt, the loop, `submit_answer`, the limits, the retries. |
| `vendors.py` | The two vendor clients (Claude Sonnet 5.5 through the Messages API, GPT-6.1 Sol through the Responses API) behind one neutral interface. |
| `mcp_client.py` | The harness as the MCP client of a scenario's server, one session per run. |
| `budget.py` | The token budget with a reservation before each request. |
| `provenance.py` | The run provenance: the declared backends, the read-only observation of the running stack, the comparison and the redaction. |
| `credentials.py`, `launcher.py` | The two API keys in Windows Credential Manager and the launcher that supplies them to the child process. |
| `study_gate.py` | The study test gate. |
| `models.json`, `prices.json` | The pinned models with their fixed request settings, and the dated price table. |
| `study-config.example.json` | The shape of the machine-local config. |
| `requirements.txt` | The pinned SDKs. Install them into a virtual environment outside the repository. |
| `test_*.py`, `fakes.py` | The tests and their fakes (vendor clients, stacks and the Docker command line). |

## Models and settings

Two models, each through its own vendor API with the model id pinned. Each has one fixed request setting, recorded in every manifest and never tuned per scenario or task (`models.json`):

- `claude-sonnet-5-5`: adaptive thinking and effort `medium`, the starting point Anthropic's prompting guide gives for agentic tool use.
- `gpt-6.1-sol`: reasoning effort `medium` (its default). Tool calling works through the Responses API only, which is the one the client uses.

The SDK pins are in `requirements.txt` (`anthropic` 1.16.0, `openai` 3.35.1, `mcp` 2.3.0). SDK retries are switched off, so every retry is the harness's own, recorded and costed. Prompt caching differs by vendor and is not a setting: the OpenAI API caches repeated prefixes by itself, while the Anthropic client marks the end of the last message of every request with a cache breakpoint, so each turn of a run reads the earlier turns from the cache. Both are costed from the cached-read column of `prices.json`.

## The loop and the scoring

One shared system prompt for every scenario and model (answer with the tools you have, then call `submit_answer`; say so if something cannot be determined). Beta adds the guide document to that prompt. The tools are the scenario's MCP tools plus `submit_answer` with the task's fixed schema, and, when the config names them, the [harness tools](#the-harness-tools). The answer is scored by the corpus scorer (`study/corpus/scoring.py`, loaded from the corpus folder; no judge) through the [scoring contract](#the-scoring-contract). A format error is tagged apart from a wrong answer. The task text is read from the corpus at run time and is copied nowhere.

Limits, the same for every scenario and model and configurable: tool calls, wall-clock seconds and tokens per task. Hitting one is scored `did_not_finish` with its reason, and everything spent is counted. A text-only reply is nudged to submit up to `max_nudges` times, then `did_not_finish` (`no_submission`). The numbers are set from the pilot, at about twice Alpha's worst pilot run.

## Token budget

The budget is in tokens per vendor, with input, cached read, cache write and output counted apart and never twice. The dollar estimate beside it comes from `prices.json`, which is dated; dollars are derived and never stored as raw data. Rules, from the lead developer and the Coordinator:

- Before each request the harness reserves its possible cost (the estimated current input plus the maximum output). A request that does not fit is a clean **budget stop**.
- Every reservation, settlement and retry is appended to the ledger (`budget-<vendor>.jsonl`) at once, and every vendor request is timed on its own (`requestStart`, `requestEnd` and `requestSeconds`, with no tool, ledger or scoring time in it) on the assistant turn of the transcript, on each retry event and on its settlement entry. A reservation that was never settled (the process died during a request) is charged in full on resume.
- A completed run is saved the moment it finishes. A budget stop ends the study cleanly with everything kept and the incomplete run archived under `attempts/`, never overwritten.
- `--resume` runs only the missing or incomplete runs and refuses a study whose plan, models, limits, prompt, guides, corpus or prices differ from the stored manifest, and one whose [provenance](#run-provenance) differs from what was declared or observed before.
- The pilot budget was 20 dollars per vendor. Study 2's ceiling (decision D of the [design](../../docs/STUDY-2-DESIGN.md#cost)) is 125 dollars for all of study 2, development included, split as 85 dollars for Anthropic and 40 for OpenAI; the example config sets `dollar_ceiling` to these. Put the matching token figure in the config (`budgets.<vendor>.tokens`, no default). The harness's budget is per study run: spend of earlier runs (development, preflight) is not counted in a later run's budget, so the ceiling of a later run is what remains of the study's. Verify that each vendor console enforces its own cap; the harness enforces its own stop regardless.

## The run protocol

One stack run per scenario (the whole plot), with the models nested inside it (the sub-plot), sequentially. Per scenario: start the stack through the config's commands, wait until the MCP server answers, record the cold start and the cold first request, run the declared warm-up (`warmup_passes` passes over `warmup_calls`), then run every task and trial of the set with every model, and tear down. The order of the tasks and trials is shuffled from the recorded seed. The model order is interleaved per task and counterbalanced by cycling the model permutations from a seeded start. A category D task stops its service before its runs and restores it after. Every sample carries its phase (`cold`, `warm-up`, `measurement`) in `samples.jsonl`. A budget stop ends the whole study, so the order stays balanced for the resume. Subprocesses of the stack get an environment without the API keys.

Records, in `LAB_RESULTS_DIR/<study run id>/`: `manifest.json` (the commit, SDK versions, harness file hashes, models with their settings and price entries, prices date, limits, budgets, telemetry and router settings, dataset hashes, machine facts, stack facts, the declared provenance, the scoring contract, the plan and its hash, and with the schedule or the harness tools the fields listed below), `samples.jsonl`, `budget-<vendor>.jsonl`, `runs/<key>/transcript.jsonl` and `result.json` (with the harness tools also `results.jsonl`), `provenance/<scenario>.json` and `provenance/checks.jsonl` (with the schedule also `provenance/<block>.json` and `blocks.jsonl`), `scores.jsonl`, `scores.csv` and `bundle.json` with the checksum. Nothing written holds an absolute path or a key; the exact key values are also redacted from everything the harness writes. The MCP servers' call logs are matched to a run by the `X-Study-Run-Id` header, which carries the run key.

## The block schedule (study 2)

With a `schedule` block in the config the harness runs [study 2's design](../../docs/STUDY-2-DESIGN.md#the-schedule-a-williams-square-in-four-rounds) instead of one stack run per scenario. A config without it runs exactly as before, with the same plan, plan hash, outcomes and score columns.

| Config key | Holds |
| --- | --- |
| `schedule` | `{"design": "williams-4-half", "arms": [four scenarios], "reference": <scenario>}`: the four full arms of the square and the Direct Access reference block. `scenario_order` and `trials` are then not used. |
| `seed` | The one seed; the schedule's draws use sub-seeds of it by label (letters, rounds, halves, models per half, the order of each block). |
| `dataset_fingerprint` | A command, run at every block start, that prints one JSON object with two texts: `fingerprint` (the dataset) and `session` (one continuous run of the database, for example its instance start time). Required with `schedule`. |
| `harness_tools` | Optional: `["calculate", "ask_requester"]`, see [the harness tools](#the-harness-tools). It also works without a schedule. |

A corpus task may carry `set` (`core` or `ambiguity`), `size` and `systems`; `load_tasks` passes them on and the halves are stratified on them with the category.

**The schedule,** computed from the config and the seed in `schedule.py`, so the same seed always gives the same schedule:

- The square is the design page's: rows `a b d c`, `b c a d`, `c d b a`, `d a c b`. Every arm stands once in every position and directly follows every other arm once.
- A seeded draw assigns the four arms to the letters, and a seeded draw orders the four rows in time. Rows 1 and 3 run half H1 and rows 2 and 4 run half H2, whatever order the rows run in.
- The halves: the tasks are grouped by stratum (set, category, size, systems), shuffled within each group and dealt alternately, so every stratum splits evenly within one task.
- The model split: within each half, dealt the same way by category, each task runs with one model in one of its two rows and with the other model in the other row, the same model for all four arms of a row. Every arm thus runs every task once per model.
- Inside a block the tasks are shuffled from the block's own seed, which also places the outage tasks, and the models alternate. The reference block comes last: every task with both models, the models interleaved per task.
- Run keys are `<arm>__<task>__<model>__r<row>`, and `__ref` in the reference block.

**A block** is one start of its arm's stack. The harness starts the stack, waits until it is ready, then, before the warm-up and before any paid request:

1. observes the provenance again, compares it with the declaration and with the arm's first stored observation, and keeps it as `provenance/<block>.json` with a line in `provenance/checks.jsonl`. A mismatch or drift refuses the block.
2. runs the fingerprint command. The block is refused unless the fingerprint equals the study's first fingerprint and its session's first one. The session is recorded on the block's line in `blocks.jsonl` and on every run of the block.

A refusal tears the stack down, writes the bundle with status `provenance_refused` or `fingerprint_refused` and exits with 3. Then the block runs its runs in order, stopping the outage service around each of its runs. A run that ended on a vendor error is queued again once, at the end of its block, and a second vendor error is recorded as the outcome `vendor_error`, which is missing from the main analysis (its score is empty). The count of vendor errors comes from the run's result and its archived attempts, so the requeue survives a stop. `blocks.jsonl` has a line for every block start (with the session, the fingerprint, the provenance fingerprint and the start number), refusal, budget stop and end (with the outcomes).

**Resume.** `--resume` goes through the blocks in order, skips every block whose runs are all finished without starting its stack, starts a partly finished block again and runs only its missing runs, the requeued ones last. The refusals on a changed plan (the schedule included) or a changed provenance are unchanged.

**The manifest** adds `schedule` (design, seed, square, letters, round order, the half of each row, the halves, the model of each task per row, and every block with its sequence, row, position, letter, arm, half and runs in order), `stackRunsPerBlock`, `vendorErrorRequeues` and `datasetFingerprint` (the command, redacted, and the rule). The schedule and the redacted fingerprint command are in the plan identity. Each run's record adds `block`, `blockSequence`, `row`, `roundSequence`, `position`, `half`, `orderInBlock`, `session`, `requeued` and `vendorErrors`, and the scores files carry them as columns.

## The harness tools

`harness_tools` in the config offers two tools beside every scenario's MCP tools ([the design's tools](../../docs/STUDY-2-DESIGN.md#the-tools)), the same name, description, schema and limits in every arm and run. A scenario whose MCP server already has a tool of either name is refused before any paid request.

- **Result ids.** With `calculate` offered, every result of a scenario tool and every successful `calculate` result gets an id `<tag>-<n>`, where the tag is four hex digits of the run key and attempt and `n` counts from 1. The id is shown to the agent as the result's first line, `result_id: <id>`, and the result is stored unchanged in the run's `results.jsonl`, which the bundle checksum covers.
- **`calculate`** names one or more results by id, each with an optional path, and one generic operation: `count`, `distinct`, `group_by` (count or sum), `sort`, `filter` (literal `eq`, `ne`, `lt`, `le`, `gt`, `ge`, every condition must hold), `union`, `intersection`, `difference` and `arithmetic` (add, subtract, multiply, divide over numbers or results). `fields`, `limit` and `round` shorten the output, which is cut at 50,000 characters and marked `truncated`. A path is dot-separated keys or positions, with `*` for every element of a list. A text on the way is read as JSON, or as XML when it starts with `<`: XML is read generically, with local tag names, attributes as `@name` and a repeated element as a list, so the SOAP arms can use the tool like the others. It has no network, file, database, backend or answer-key access and sees only the run's own results. An id of another run, an unknown id, an operation or comparison not on the list and a bad path are refused as tool errors.
- **`ask_requester`** takes a question, logs it with the run key and always returns "No requester response is available during this evaluation."
- **Logging and counting.** Both tools count in the tool-call limit like any other tool. Each call's transcript event carries `harness`: for `calculate` the result ids used, the operation, the new result id or the failure, the seconds of the calculation, the bytes read and returned and an estimate of the tokens it added; for `ask_requester` the question and the run key. The run's record adds `harnessToolCalls` (`calculate`, `calculateErrors`, `askRequester`) and `askRequester` (the questions), and the scores files the columns `calculateCalls`, `calculateErrors` and `askRequesterCalls`.

The manifest and the plan identity record the tools as `harnessTools` (names, descriptions and schemas, the fixed text, the id format, the operations and the limits).

## The scoring contract

`scoring_contract.py` declares how the harness calls the corpus's `scoring.py` and what it accepts back.

| Version | Declared by | Called as | Outcomes the scorer may return |
| --- | --- | --- | --- |
| 1 | nothing (study 1's corpus, unchanged) | `score(submission, schema, expected)` | `correct`, `wrong_answer`, `format_error`, `silent_guess`, `definition_not_accepted` |
| 2 | `SCORING_CONTRACT = 2` in the module (corpus 2) | `score(submission, schema, expected, context)` | `correct`, `wrong_answer`, `format_error`, `definition_not_accepted`, `abstained` |

- `context` holds `taskId`, `set`, `category` and `askRequester`, the run's log of `ask_requester` questions, which is the only source of a clarification. A version-2 scorer may also return the booleans `clarified` and `interpretationAccepted` for the ambiguity set; the scores files carry them as columns.
- Every result must carry an outcome of its version and a `score` that is 1 exactly when the outcome is `correct`. A result that breaks the contract stops the study (bundle status `scoring_error`, exit 3); it is never recorded as a score.
- The harness decides two outcomes itself: `did_not_finish` (no submission, or a limit) and `vendor_error`. `budget_stop` is not a score.
- `abstained` is incorrect for primary accuracy and reported as its own outcome beside wrong answers. Which submissions count as abstention is decided by corpus 2's scorer and frozen with it.

The manifest records the contract as `scoringContract` (version, outcomes, the correct outcome, the harness outcomes and the scorer's SHA-256). A version other than 1 is part of the plan identity.

## Run provenance

Study-1 ran against a Missions simulator instead of the Oracle-backed service, and nothing in its manifest said so. Every run now declares the backends it means to use, observes the ones it actually uses, and refuses to spend anything when the two differ.

**Declare.** Every scenario of the config has a `provenance` block, and a scenario without one is refused when the config loads. `study-config.example.json` shows the shape:

| Key | Holds |
| --- | --- |
| `compose_projects` | The compose projects the harness observes. |
| `backends.<logical service>` | `mode` (`real` or `simulated`); `service`, the compose service that serves it, as `name` or, when two projects have that name, `project/name`; `image_id` (`sha256:...` from `docker inspect`) and/or `image_ref` (the image name the container was started from); optionally `dataset`: `id`, `path` (a file or a folder the harness hashes), `sha256` (expected) and `mount` (the container path of a bind mount that must exist on that service and whose source the harness must be able to read and hash; leave `mount` out where it cannot, as with some Docker Desktop paths). |
| `routing.endpoints` | Each upstream URL the MCP server calls, with the compose service that must publish its port on the host. The host must be `127.0.0.1`, `localhost` or `[::1]`, and the port must be published on an address that serves it. |
| `routing.env` | Per compose service, the backend URL variables and their expected values (for example `MISSIONS_SERVICE_URL`). |
| `launch_files` | Label and path of the launch scripts and config files to hash. Only the hash is stored, never the contents. |

**Observe.** After the stack is ready and before the warm-up, so before the first paid request (dry runs included), the harness runs two read-only commands and nothing else: `docker compose -p <project> ps --all --format json` and `docker inspect` of the containers it lists. Per service it records the state, the image ref and id, the published ports, the routing environment (names that end in `_URL`, `_HOST` or `_PORT`, and every name in `routing.env`) and the bind mounts (the container path and the SHA-256 of the source when the harness can read it; the source path is never stored). It also hashes the datasets and the launch files and records the scenario's stack commands as the launch configuration.

**Compare.** Any difference refuses the scenario before any paid request, with one line per difference: a backend service that is missing or not running, another image, a dataset hash, a missing mount, a mount that cannot be read or whose hash differs, a routing variable, an endpoint port that the named service does not publish, a launch file that cannot be read, or a stack that cannot be observed. `mode` is recorded as declared and checked through the service, image and routing it implies. The stack is torn down, the bundle is written with status `provenance_refused` and the command exits with 3.

**Keep.** The manifest holds `provenance.schema`, `provenance.intended` (each scenario's declaration, host paths reduced) and `provenance.observationCommands`. The first matching observation of a scenario is `provenance/<scenario>.json`, with a `fingerprint` of its stable part (images, routing environment, ports, mounts and hashes, datasets, launch files, launch configuration and the MCP URL; container ids and times are left out). Every later check, and every refusal, is a line of `provenance/checks.jsonl` (`match`, `mismatch`, `drift` or `unobserved`). The bundle checksum covers both.

**Resume.** A resume refuses when the declaration differs from `provenance.intended` and when a scenario's new observation differs from its stored one, naming each change. There is no override. A bundle written before provenance existed cannot be resumed.

**Redact.** Environment values whose names contain `PASSWORD`, `SECRET`, `TOKEN` or `KEY` (in any case, which covers both API key names) are stored as `[MASKED]` with the name kept, and so is the value of a command option with such a name (`--db-password x`). The `user:password@` part of a URL is masked, in the observation and in the declaration the manifest keeps. Host absolute paths are reduced to `<path>/<last component>`; container paths, such as mount destinations, stay. The exact values of the API keys are redacted from everything as before.

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

The provenance tests use a fake Docker (`fakes.py`) and never start, stop or inspect a container.

`python -B study/harness/study_gate.py` runs the offline tests of the study: this folder, the corpus derivation check and the MCP offline tests. It needs no stack and no key. The MCP suite needs the `mcp` package, which the governance interpreter does not have, so it runs under the interpreter named by the machine-local variable `STUDY_MCP_PYTHON` and is reported as NOT RUN when there is none (`--require-mcp` makes that a failure). The convention for the other study areas: put `test_*.py` files directly in the area's folder and list the folder in `SUITES` of `study_gate.py`. The live MCP stack tests (`study/mcp/test_mcp_stack.py`) are not part of the gate.

The area accepts Python, JSON, JSON Lines, TOML, Markdown and text files.
