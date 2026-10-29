# Study launch kit

How an operator starts, stops and interrupts the stack of each scenario of the [Abstraction ladder study](../README.md), and writes the machine-local study config that the [harness](../harness/README.md) runs. It replaces the machine-local scripts of study 1, which lived outside the repository and ran only the Missions simulator. The design it serves is [Abstraction ladder study 2: design](../../docs/STUDY-2-DESIGN.md).

The kit was written and tested with fakes only: nothing in it has been run against Docker, Oracle or the Missions service yet.

## Files

| File | Holds |
| --- | --- |
| `launch.py` | `up`, `down` and `service stop|start` for one scenario, in one of the two Missions modes, and the two read-only commands of the harness, `fingerprint` and `health`. |
| `missions-real.compose.yaml` | The overlay of `federation/stack/compose.yaml` for the real mode: the Missions adapter on the real service's network, and no `missions-stub`. |
| `make_config.py` | The generator of the machine-local study config, with each scenario's `provenance` block. |
| `test_launch.py` | The offline tests, with a fake machine in place of Docker. |

## The two Missions modes

| Mode | Missions backend | How the stack starts |
| --- | --- | --- |
| `simulated` | `missions-stub`, the simulator of study 1, serving Missions release 1.2 | `federation/stack/start.sh start`, unchanged, as in study 1 |
| `real` | the real Missions service on Oracle, started by the operator beforehand | the same steps as `start.sh`, with `missions-real.compose.yaml` added to every compose call |

Every scenario starts the whole federation stack, as in study 1: the backends, the four adapters and one router (Cosmo for epsilon, Apollo otherwise). Alpha and beta (Direct Access and Guided Direct Access) also publish the legacy services on their loopback ports (`study/mcp/legacy-ports.json`): Personnel on 8082 and Assets on 8084, and in the simulated mode the simulator on 8083. In the real mode the real service publishes `127.0.0.1:8083` itself.

**The real-mode wiring.** The real service runs in its own compose project, `starfleet-missions` (`uss-enterprise/missions/compose.yaml`), on two networks: Oracle's internal network `starfleet-missions-data-20261009` and its own bridge, `starfleet-missions_default`, which carries its publication. The overlay attaches the Missions adapter to that bridge only and sets its `MISSIONS_SERVICE_URL` to `http://starfleet-missions-service:8083`, the service's container name there. The adapter therefore cannot reach Oracle, Oracle's network stays internal, and no port is published beyond what the two compose files already publish on `127.0.0.1`. The overlay resets the adapter's `depends_on`, so neither the adapter nor a router ever starts `missions-stub`; that needs Docker Compose 2.24.4 or later.

**The adapters' backends.** The stack compose file lets the environment set `MISSIONS_SERVICE_URL`, `PERSONNEL_SERVICE_URL` and `ASSETS_SERVICE_URL`. `launch.py` sets all three in every command it runs, to the stack's own services (and, for Missions, to the mode's backend), so a value inherited from the shell cannot point an adapter elsewhere.

**What the kit never does.** It never starts, provisions, resets or removes Oracle, and never starts or creates the Missions service: those stay the operator's explicit steps, with `uss-enterprise/missions/datasets/missions_operator.py` and the Missions compose file ([the Missions README](../../uss-enterprise/missions/README.md#packaging-and-deployment)). Before a real-mode start, `launch.py up` checks, and refuses without, the service's container running, its network present, `GET http://127.0.0.1:8083/missions?pageSize=1` answering 200, a Compose new enough for the overlay, the stack's loopback ports free and, for an Apollo router, `APOLLO_ELV2_LICENSE=accept`. `down` stops the federation stack only. Nothing removes a container, an image, a volume or a network.

**The Missions outage.** In the simulated mode, `service stop|start missions` stops and starts `missions-stub`. In the real mode it runs `docker stop` and `docker start` on the existing container `starfleet-missions-service` that the operator made, by its name, and then waits until the service answers again; it never runs the Missions compose file and refuses when the container does not exist. The Assets and Personnel outages stop and start their compose services in both modes; the start uses `--no-recreate`, so the stopped container comes back with the credentials it had.

## Machine-local settings

Nothing here names a path of the machine. The repository is found from the scripts' own location, and every machine-local value comes from the environment or an argument:

| Setting | Used by | What it is |
| --- | --- | --- |
| `--state-dir` or `STUDY_LAUNCH_STATE_DIR` | `launch.py` | A folder outside the repository. The composed supergraph and the Cosmo execution config are written there, so the committed ones are never rewritten. |
| `STUDY_MCP_PYTHON` or `--mcp-python` | `make_config.py` | The Python of the MCP virtual environment (`study/mcp/requirements.txt`), which runs the MCP servers. |
| `STUDY_BASH` | `launch.py` | The bash of Git Bash, for the simulated mode (default: `bash` on the PATH; the WSL launcher is refused). |
| `PYTHON` | `launch.py` | The Python that `start.sh` and the composition scripts run under (default: the one running `launch.py`). |
| `APOLLO_ELV2_LICENSE=accept` | `launch.py` | Your acceptance of the Elastic License 2.0 of Rover's composition plugin, for an Apollo start. `make_config.py --accept-apollo-elv2` writes it into the start commands of the config. |
| `LAB_RESULTS_DIR` | the harness | The folder of the run results, as before. |

## Credentials

No credential is in a committed file or in the generated config. `launch.py up` makes the two Assets database passwords at random for each start, as `start.sh` does, unless `STACK_ASSETS_DB_ADMIN_PASSWORD` and `STACK_ASSETS_DB_SERVICE_PASSWORD` are set in the environment, and passes them to its child commands only; it never prints or writes them. `down` and the outages give compose a placeholder, which it needs to read the file and never uses. The kit handles no Missions login: the operator gives the service its login from the environment when starting it ([the Missions README](../../uss-enterprise/missions/README.md#packaging-and-deployment)). The API keys stay with the [harness launcher](../harness/README.md#credentials).

## Starting a scenario by hand

From the repository root, in Git Bash. Replace `<folder>` with a machine-local folder outside the repository.

Simulated mode, any scenario:

```sh
export APOLLO_ELV2_LICENSE=accept
python -B study/launch/launch.py up gamma --missions simulated --state-dir '<folder>'
python -B study/launch/launch.py service stop assets gamma --missions simulated --state-dir '<folder>'
python -B study/launch/launch.py service start assets gamma --missions simulated --state-dir '<folder>'
python -B study/launch/launch.py down gamma --missions simulated --state-dir '<folder>'
```

Real mode: first the operator steps of the Missions README (Oracle up through `missions_operator.py`, the release loaded, then the service with `docker compose -f uss-enterprise/missions/compose.yaml up --detach --build` and its login in the environment), then:

```sh
python -B study/launch/launch.py up delta --missions real --state-dir '<folder>'
python -B study/launch/launch.py down delta --missions real --state-dir '<folder>'
```

`--dry-run` prints the checks and the commands and runs nothing. Each scenario works the same way: `alpha`, `beta`, `gamma`, `delta` or `epsilon`.

## The study config

The harness starts and stops the stacks itself, from the config. Write the config once per mode:

```sh
python -B study/launch/make_config.py --output '<config folder>/study-config.json' --plan '<config folder>/plan.json' \
  --missions real --state-dir '<folder>' --guide-file '<the guide of beta>' --accept-apollo-elv2
```

Both the config and the plan are outside the repository. The plan is a JSON object holding exactly the run plan, which this kit does not decide, in the shape of [`study-config.example.json`](../harness/study-config.example.json) (an `about` text is allowed), of one of two shapes. For study 2: `schedule`, `task_set`, `models`, `seed`, `warmup_passes`, `limits` and `budgets`, and optionally `harness_tools`, `health_every_runs` and `earlier_study_runs`; `scenario_order` and `trials` are refused, because the schedule decides them. For study 1: `task_set`, `scenario_order`, `models`, `trials`, `seed`, `warmup_passes`, `limits` and `budgets`, and optionally `harness_tools`. The generator copies it and writes the rest: each scenario (the schedule's arms and its reference, or those of `scenario_order`) with its MCP URL and warm-up calls, the guide file for beta, its stack commands (`launch.py up`, `down` and `service`, with the mode and the state folder) and its MCP server, and the `provenance` block of [run provenance](../harness/README.md#run-provenance):

- `compose_projects`: `starfleet-federation-stack`, and `starfleet-missions` in the real mode;
- `backends`: `missions` with mode `simulated` (service `missions-stub`, its pinned image and the hash of Missions release 1.2) or `real` (service `starfleet-missions/missions`, image `starfleet-missions-service:1.0.0`); `assets` and `personnel` with mode `real`, their images, and the hash of Assets release 1.1;
- `routing`: the upstream URLs the scenario's MCP server calls, with the service that publishes each, and the backend URL of each of the three backend adapters: `MISSIONS_SERVICE_URL` for the mode, `PERSONNEL_SERVICE_URL` and `ASSETS_SERVICE_URL`. The harness compares each one with the running adapter's environment;
- `launch_files`: `launch.py`, the stack compose file and, by mode, `start.sh` or the overlay, and for alpha and beta `legacy-ports.json`, hashed by the harness.

The generator also writes, for the harness:

- `dataset_fingerprint`: `launch.py fingerprint` with the mode and the state folder, which the harness runs at every block start of a schedule;
- every scenario's `health`: `launch.py health <scenario>`, which the harness's [void-block rule](../harness/README.md#the-void-block-rule) runs;
- `corpus_dir`: the corpus the harness reads, `study/corpus2` for a plan with a schedule and `study/corpus` without (`--corpus-dir` names another folder, which must hold a `scoring.py`). The harness takes it from the config, so it is not given to the harness by hand; a `--corpus-dir` given to the harness that names another folder is refused.

The generator checks each block with the harness's own validator before it writes, and refuses an output inside the repository or an existing file without `--replace`. Then run the study through the [harness launcher](../harness/README.md#credentials) with `--config` naming the written file.

## The read-only commands of the harness

Both only read: no state folder is made, nothing is started or stopped, and Oracle sees SELECTs only.

- `launch.py fingerprint --missions <mode> --state-dir <folder>` prints one JSON object with `fingerprint` and `session`. On the real service the fingerprint is `missions-db:` and the SHA-256 of the [preflight](../preflight/README.md)'s data step reading (the row counts of the six Missions tables, the clock row, and the largest change id and lastUpdated, read through the preflight's guarded SQLPlus session), and the session is `oracle-instance:` and the instance's start time (`v$instance`). On the simulator (decision F5 of the Job `study2_build_followups`) the fingerprint is `missions-release-1.2:` and the SHA-256 of the simulator's dataset release, as the harness hashes it for the provenance, and the session is `missions-stub:` and its container's start time from `docker inspect`, so a restarted simulator is a new session. It exits 1 when either cannot be read.
- `launch.py health <scenario> --missions <mode> --state-dir <folder>` prints `{"backends": {"missions": ..., "assets": ..., "personnel": ...}}`, each with `up` and a `detail`. A backend is up when its container (found by its compose labels, or the real service's container by name) is running and, as all three have a healthcheck in the stack's compose file, healthy; the real Missions service must also answer `GET http://127.0.0.1:8083/missions?pageSize=1` with 200. It exits 0 whatever it finds. Known limit: Docker updates a healthcheck's status only at its interval, so a backend that has just gone down can still read healthy for a few seconds.

## Study 2, end to end

From the repository root, in Git Bash; every folder in angle brackets is outside the repository. A run against Oracle, the stacks or a vendor needs the lead developer's go.

1. The study environment, once: `python -B study/mcp/setup_env.py '<new folder>'`, then set `STUDY_MCP_PYTHON` with the line it prints ([the MCP README](../mcp/README.md#the-study-environment)).
2. In the real mode, the operator steps of the Missions README: Oracle up through `missions_operator.py`, the release loaded, the service started.
3. The plan: a JSON file with `schedule`, `task_set`, `models`, `seed`, `warmup_passes`, `limits`, `budgets` (each vendor with `tokens`, `dollar_ceiling` and `ceiling_basis`) and, as needed, `harness_tools`, `health_every_runs` and `earlier_study_runs` ([the harness README](../harness/README.md#the-block-schedule-study-2)).
4. The config:

   ```sh
   python -B study/launch/make_config.py --output '<config folder>/study-config.json' --plan '<config folder>/plan.json'      --missions real --state-dir '<folder>' --guide-file '<the guide of beta>' --accept-apollo-elv2
   ```

5. Optionally, the two read-only commands by hand, with the stack of a scenario up:

   ```sh
   python -B study/launch/launch.py fingerprint --missions real --state-dir '<folder>'
   python -B study/launch/launch.py health delta --missions real --state-dir '<folder>'
   ```

6. A dry run of the whole protocol with no key and no cost, then the run, from PowerShell or Git Bash:

   ```sh
   py -3 study/harness/runner.py --config '<config folder>/study-config.json' --run-id '<new run id>' --dry-run
   py -3 study/harness/launcher.py run -- --config '<config folder>/study-config.json' --run-id '<new run id>'
   ```

   The harness reads the corpus from the config. A stop (`budget_stop`, `block_void`) is resumed with the same command and `--resume`.

## Tests

`test_launch.py` uses a fake machine: it checks the arguments, the commands each scenario and mode would run, the real-mode refusals, the passwords, the generated config for both modes and both plan shapes, and what `fingerprint` and `health` read and print (with the preflight's own SQL guard on every query, and the harness's own parsers on the output), and pins the kit's copies of facts owned elsewhere (the backends of `start.sh`, the Missions compose defaults, the stack's image names) against those files. It never starts, stops or inspects a container and makes no network call.

The area accepts Python, YAML and Markdown files.
