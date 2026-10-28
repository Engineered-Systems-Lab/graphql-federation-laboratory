# Study 2 preflight

The operator scripts of the preflight of [Abstraction ladder study 2](../../docs/STUDY-2-DESIGN.md#preflight-steps): they measure and record, one explicit step at a time, before the real Missions service on Oracle is used for any study run. The judgement of the go or no-go thresholds and of the decision-L gate stays the lead developer's; the scripts only fill the record that the lead developer reads.

The scripts were written and tested with fakes only: no step has been run against Docker, Oracle, the Missions service or a stack yet.

## Files

| File | Holds |
| --- | --- |
| `preflight.py` | One subcommand per step: `inventory`, `oracle`, `data`, `service`, `compare`, `stack`, `outage`, `provenance`, and `report`. |
| `record-template.json` | The preflight record: the go or no-go thresholds, the nine steps, the decision-L gate with its five questions and its procedure, and the options on a failure. `preflight.py` reads its thresholds from here, and `report` fills it. |
| `test_preflight.py` | The offline tests, with a fake machine in place of Docker, SQLPlus, HTTP and the launch kit. |

## How every step behaves

- **One explicit action.** `python -B study/preflight/preflight.py <step> ... --results '<folder>'` prints what the step will do and runs nothing. The same command with `--run` prints it again, runs the step and writes one record.
- **The record.** A JSON file in the results folder, which must be outside the repository: the step, the plan it printed, every command it ran, the measurements, the checks with `pass`, `fail` or `not-measured`, and notes. A record is never overwritten. The exit code is 0 when no check failed, 4 when one did and 1 when the step refused to start.
- **Read only.** Docker is called only in read-only forms (`image inspect`, `inspect`, `ps`, `stats --no-stream`, `system df`) and through one SQLPlus session in the Oracle container. Every SQL statement is a single SELECT in a read-only transaction that ends with a rollback. HTTP is GET to this machine only, plus GraphQL queries, never a mutation, to the router. The one exception is `outage`, which stops and starts services through `study/launch/launch.py service`.
- **No credential.** The one value read from a container's environment is the service's login name, `MISSIONS_DB_USER`, through a Docker template that reads nothing else. SQL runs as the Oracle container's operating-system user, with no password. Every record is redacted before it is written: a value under a secret-named key, a secret-named assignment, the `user:password@` part of a URL and an `IDENTIFIED BY` clause are masked.
- **What no step does.** No step provisions, resets, starts, stops or removes Oracle, starts or builds the Missions service, writes to Oracle, makes a paid request or changes a file of the stack. Those stay the operator's steps, with the lead developer's go: `uss-enterprise/missions/datasets/missions_operator.py` for Oracle and the reset, the Missions compose file for the service ([the Missions README](../../uss-enterprise/missions/README.md#packaging-and-deployment)), `study/launch/launch.py` for the stacks ([the launch kit](../launch/README.md)).

## The steps, in order

From the repository root, in Git Bash. `<results>` is a machine-local folder outside the repository; `<state>` is the state folder of the launch kit.

| Step | Before it, the operator | The step | Needs from the lead developer |
| --- | --- | --- | --- |
| 1 Inventory | nothing | `preflight.py inventory --results '<results>' --run`: the Oracle image by its pinned digest, the service image `starfleet-missions-service:1.0.0`, the memory limit of the Missions compose file and 20 GiB of free disk (`--disk-path` names the drive) | the go for the step; the service image is built afterwards by the operator, once the memory-limit Job has landed |
| 2 Oracle alone | provisions or starts Oracle with `missions_operator.py provision` | `preflight.py oracle --results '<results>' --run`, started right after Oracle: the readiness time (from the container's start to the first answer, at most the pinned 900 s), the `docker stats` peak, the `vmmem` size, the host's free memory and the SGA and PGA views | the environment go of [the operator workflow](../../uss-enterprise/missions/README.md#explicit-operator-workflow) |
| 3 Data | resets to release 1.2 (`missions_operator.py reset --dataset 1.2`) and creates the read-only login (below) | `preflight.py data --login '<login>' --results '<results>' --run`: the six row counts, the release hash in the clock row, the clock counter and a fingerprint, and that the login has `CREATE SESSION`, no role and `SELECT` on the six tables only | the go for the reset and for the login |
| 4 The Missions service | starts the service with the Missions compose file and the read-only login | `preflight.py service --target real --results '<results>' --run`; then, with the service stopped and a simulated stack of alpha or beta up (`launch.py up alpha --missions simulated`), `preflight.py service --target simulated --results '<results>' --run`; then `preflight.py compare '<real record>' '<simulated record>' --results '<results>' --run` | the go for the service start; the classification of each difference under decision L |
| 5 The whole stack, per arm | starts the scenario's stack with `launch.py up <scenario> --missions real --state-dir '<state>'`, and runs the acceptance list A and the adapter gates with their own commands | `preflight.py stack <scenario> --missions real --results '<results>' --run`: the full page of 100 missions with their assets, commanding officer and crew at offsets 0, 100 and 200, then a 30-minute soak (`--minutes`) with the Missions REST pages, sampling every container, the host and `vmmem`; the same with `--missions simulated` for the latency against the simulator | the go for each stack start |
| 6 Outage mechanics | has the scenario's stack up | `preflight.py outage <scenario> --missions real --state-dir '<state>' --results '<results>' --run`: stops and starts Assets, Personnel and the Missions service through `launch.py service`, timing the outage and the recovery through the router; the router is never restarted by the step | the go for the step, because it stops services |
| 7 Answerability | | not in this kit: it needs corpus 2 | a later Job |
| 8 Provenance | writes the study config with `study/launch/make_config.py --missions real` and has the scenario's stack up | `preflight.py provenance <scenario> --config '<config>' --results '<results>' --run`: the harness's own observation and comparison, with no vendor client; the intended Missions mode must be real and the observed one equal it | the go for the step |
| 9 Paid smoke test | | not in this kit: it needs corpus 2 and paid requests | a later Job |

Then `preflight.py report --results '<results>'` writes `preflight-record-<time>.json`: the template with each step's records, the status of each threshold (`pass`, `fail` or `not-measured`, answerability staying `not-measured` until step 7 exists), the decision-L differences to classify, and the empty slots of the judgement and of the go or no-go decision.

The Missions clock check of step 3 is `data` run again after a block with `--compare-to '<the earlier data record>'`: the fingerprint must be equal.

## The read-only service login

The login and its grants are an operator step, run as an Oracle administrator inside the Oracle container, in the pluggable database `XEPDB1`, with the lead developer's go. Choose the name and a password; the password goes only into the service's environment when the operator starts it ([the Missions README](../../uss-enterprise/missions/README.md#packaging-and-deployment)) and never into a file or a record:

```sql
CREATE USER <login> IDENTIFIED BY "<password>";
GRANT CREATE SESSION TO <login>;
GRANT SELECT ON MISSIONS_LAB.MISSIONS TO <login>;
GRANT SELECT ON MISSIONS_LAB.MISSION_ASSIGNED_CREW TO <login>;
GRANT SELECT ON MISSIONS_LAB.MISSION_PARTICIPANTS TO <login>;
GRANT SELECT ON MISSIONS_LAB.MISSION_ASSIGNED_ASSETS TO <login>;
GRANT SELECT ON MISSIONS_LAB.MISSION_CHANGES TO <login>;
GRANT SELECT ON MISSIONS_LAB.MISSION_CLOCK TO <login>;
```

These are the grants of the service's read operations; the write operations, which the study never uses, would need the grants of [the write slice](../../uss-enterprise/missions/README.md#write-service-slice). Step 3 checks that the login in use has nothing more.

## Limits

- The Missions compose file sets no memory limit yet: that change is its own Job, and step 1 records whether it has landed.
- Step 4 sends GET only. The raw MCP tool of Direct Access and Guided Direct Access also allows HEAD, which the step does not probe.
- Step 5 does not run the acceptance list A or the adapter gates; the operator runs them with their own commands, and their results go into the record by hand.
- The thresholds are judged mechanically against the template; the decision-L classification, the gate's judgement and the go or no-go decision are the lead developer's.

## Tests

`test_preflight.py` uses a fake machine: it checks the arguments, the refusals and the guards (the Docker, SQL, HTTP, GraphQL and launch allowlists), the record of each step, the report, the redaction of credentials, and pins the facts copied from elsewhere (the full page of the acceptance suite, the thresholds of the design page, the service, container and stack names). It never starts, stops or inspects a container, reads no database and makes no network call. The study gate runs it with the other study suites.

The area accepts Python, JSON and Markdown files.
