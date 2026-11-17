# Blind workers' inputs

Study 2 has two workers who must not see part of the lab: the author of the Guided Direct Access guide must not see the scored corpus, the answer key or study 1's task-level findings (decision J of the [study 2 design](../../docs/STUDY-2-DESIGN.md)), and the worker of the second corpus 2 derivation (keys B) must not read the first derivation until its own keys are recorded (the [corpus 2 README](../corpus2/README.md), the handoff to the second deriver). Instead of instructions alone, each gets a prepared folder that holds only its inputs, with no Git history, no remote and no network. Someone who may see everything builds it; this folder holds the builder, the package definitions, the request relay and their tests (decisions I1 to I7 of the Job `study2_blind_inputs`).

Study 3 adds a third package, `keys-b3`, for the blind derivation of the keys of corpus 3's 31 new tasks (the second derivation of the new keys in the [corpus 3 README](../corpus3/README.md); decisions B1 to B5 of the Job `study3_blind_inputs`). Its rule: the new tasks are all it gets. It holds `study/corpus3/tasks.json` and `study/corpus3/schemas.json` rewritten to the tasks named by `newTaskIds` of `study/corpus3/corpus-manifest.json` (each record and schema the lab's own JSON value), with the `directions` map and every task's `designNote` dropped; no development task; the keys B worker's own study 2 derivation, `study/corpus2/derive_b.py` and `test_derive_b.py`, byte for byte, to reuse; and the released data that study 2's keys B package held. It holds nothing of either first derivation, of corpus 2 or of corpus 3 (`derive_a.py`, `derive_a3.py`, `keys-a.json`, `expected.json`, `reference/`).

| File | What it is |
| --- | --- |
| `blind.py` | The builder: `build`, `verify` and `list`. |
| `packages.json` | The three package definitions: each package's allow-list with the reason for every entry, its derived and rewritten files, its excluded paths, and every file that was read and left out, with the reason. |
| `readme-guide.txt`, `readme-keys-b.txt`, `readme-keys-b3.txt` | The README of each package, written into it as `README.md` with the commit filled in. |
| `relay.py` | The request relay of the guide author (decision I3). |
| `test_blind.py` | The leak checks (decision I5, and those of `keys-b3`) and the builder's tests. |
| `test_relay.py` | The relay's tests, on the harness's scripted session and on the raw MCP server's own code against the loopback service of the MCP offline tests. |

## Building a package

From the root of a checkout of the commit to build from (its `study/blind/blind.py` must be the one that runs), with any Python 3.13 or later, in Git Bash or PowerShell:

```sh
python -B study/blind/blind.py build guide --commit <full commit id> --output <new folder outside any Git work tree>
python -B study/blind/blind.py build keys-b --commit <full commit id> --output <another new folder>
python -B study/blind/blind.py build keys-b3 --commit <full commit id> --output <another new folder>
```

The builder reads everything from the commit, never from the working tree: the definitions, the README templates and every file. It refuses an output folder inside any Git work tree or one that is not empty, and a commit whose `blind.py` is not the running one, so the output is a function of the commit and the same commit always gives the same bytes. The folder holds the allowed files, each at its lab path, `README.md`, the derived files (the guide's `TOOLS.md`, the tool texts copied from their sources) and `MANIFEST.json`: the commit, every file's SHA-256 and size, how each was made (`lab`, `rewritten`, `derived` or `readme`, with the hash of each source), the builder's version and hash, and `packageSha256`, the SHA-256 of the manifest's canonical JSON without that field. `build` then runs `verify` on the result and prints the package hash, the hash of the `MANIFEST.json` file and any leak finding; it exits 1 on a finding.

A definition's `rewrite` list changes an included JSON file, in order, and refuses a file that does not round-trip through JSON unchanged: `drop` removes one key from every object of a list (`from`), or without `from` from the file's top-level object; `select` keeps only the entries of a list of objects (by `id`) or of a map (by key) whose id is in a named list of a lab file, and refuses an id that is missing or doubled. The manifest records each rewrite with the hash of the original, and a `select` with the hash of its list's file and the ids it kept; a file rewritten more than once has the list of its rewrites.

`list guide` (or `keys-b`, `keys-b3`) prints what a package would hold, from the working tree or with `--commit` from a commit.

## Verifying and handing it over

```sh
python -B study/blind/blind.py verify <package folder>
```

checks the folder against its manifest (every file present and unchanged, nothing more, no `.git`) and runs the leak checks against this checkout's corpus files: for the guide package no file under an excluded path or under `study/`, no corpus 2 or study 1 question (exact, whitespace-normalized or a 10-word fragment) and no corpus 2 task id; for the keys B package no `expected` entry in a corpus 2 file and no file of, or with the bytes of, `keys-a.json`, `derive_a.py`, `expected.json` or `reference/`; for `keys-b3` (a) no file of, or with the bytes of, either first derivation (corpus 2's or corpus 3's `derive_a.py`, `derive_a3.py`, `keys-a.json`, `expected.json`, `reference/`) or of a development set, (b) exactly the ids of `newTaskIds` in the tasks and in the schemas and no other corpus 2 or 3 question (exact, whitespace-normalized or a 10-word fragment) in any file, and (c) no `expected`, `directions` or `designNote` entry in a corpus 2 or 3 file. Every scan for question text or task ids reads `MANIFEST.json` too, reads `\n`, `\r` and `\t` escapes as whitespace and, in a JSON file, also its decoded strings, joined by spaces; a 10-word fragment is any window of ten words, of at least 50 characters, starting at any word of the question.

The lead developer creates the private repository from the folder and pushes it; the builder never creates a repository, a remote or a push. Record the package hash with the repository: the freeze of the guide or of the B keys names it.

## The request relay

The guide author works with no network, so the live services reach it only through the relay. The author writes `relay/round-<nnn>.requests.json` in its repository: `{"round": n, "requests": [...]}`, each request `{"tool", "arguments"}` with an optional `"id"`, the tool one of `http_request`, `soap_request` and `read_mapping_release`, the arguments those of the agents' tool. In a clone of that repository, from the root of the lab checkout:

```sh
python -B study/blind/relay.py run --dir <clone>/relay --round <n> --missions real --dry-run
python -B study/blind/relay.py run --dir <clone>/relay --round <n> --missions real
python -B study/blind/relay.py verify --dir <clone>/relay
```

The dry run checks the file and prints the requests; the lead developer reads them and gives the go for the round. The run builds the raw MCP server in its own process with the launch kit's arguments (the three legacy services' addresses, the lab's mapping release folder, the default timeout and size limit) and sends each request through the MCP client: the same tool code, sandbox and refusals as the agents, no other tool and nothing edited. It writes `round-<nnn>.answers.json` (each answer's text and error flag as the agent's session reads them, the round, the start and end times, the dataset fingerprint from `study/launch/launch.py fingerprint` before and after the round, the Missions backend serving the Missions port before and after the round, the relay's version and hash, the lab commit and the code's hashes) and appends the round to `LEDGER.json`, which holds both files' SHA-256 and a chain hash over the rounds, so the freeze can record exactly what the author saw. A round runs once; a file of another shape, a round out of order or a folder that does not match its ledger is refused and nothing runs. The relay runs committed code only: it refuses when `study/blind/`, `study/mcp/`, `study/launch/` or the mapping releases differ from the commit.

`--missions` is checked, not trusted. Before the first request the relay reads `docker ps` (read only): exactly one container must publish the launch kit's Missions host port (8083, which the server's allow-list reaches), and it must be the real service's container for `real` or the federation stack's `missions-stub` for `simulated`. The fingerprint must also name that mode. Otherwise nothing runs.

A run holds `relay.lock`, created exclusively in the relay folder, from the check that the round is the next one until the ledger is written. A second run of the same folder meanwhile is refused and runs nothing. The answers file is also created exclusively, and the ledger is replaced whole. A lock left by a run that died stays: once no relay runs, the lead developer runs `verify` and deletes the lock.

A live round needs the scenario's stack and the real Missions service up (the [launch kit](../launch/README.md)), the interpreter named by `STUDY_MCP_PYTHON` and the lead developer's go for that round. The relay starts nothing. The lead developer commits the answers and the ledger in the author's repository and pushes them, and the author reads them there.

## Tests

`test_blind.py` and `test_relay.py` run in the study gate (`study/harness/study_gate.py`, suite `blind`), offline: no stack and no API key. The relay's tests through the raw MCP server need the `mcp` package and are skipped without it.
