# The stack's Assets database lives in memory so every start succeeds, and the READMEs and citations are brought current

Date: 2026-10-26T17:06Z
Subject: Committed a tmpfs for the Assets database of the federation stack, so that a second and every later start of the same compose project succeeds, together with the rewritten root and stack READMEs, the gate counts and the labeled lab ids
Status: Historical / non-normative
Provenance: Written on 2026-10-26 after the commit by a fresh records worker, from the commit itself, the checks the checkpoint tool ran on the commit's exact tree before the commit, and the run reports that the worker who made the change kept in its Job notes, attributed below as theirs. Dated by the committer time of the checkpoint commit (`2026-10-26T13:06:05-04:00`, 2026-10-26 17:06:05 UTC), converted to the prescribed UTC minute.
Repository checkpoint: `b079a207dcab79914e17b6ab2f1ba16549bcb7cf`

## The transition

Before this commit only the first `start.sh start` of a compose project worked. `start.sh` makes new random credentials for the Assets database on every run, while `assets-db` kept its data in the anonymous volume that the `postgres:17-bookworm` image declares; Compose keeps that volume when it recreates the container, so a data directory initialized by an earlier run refused the new password and `assets-bootstrap` exited 1 ("password authentication failed for user postgres") until the volumes were removed by hand.

The commit mounts a `tmpfs` of 128m at the image's data directory (`/var/lib/postgresql/data`, its PGDATA and declared volume, read with `docker image inspect`) in `federation/stack/compose.yaml`. The data now lives only while `assets-db` runs: every start initializes it with that run's credentials, and the bootstrap loads Assets dataset release 1.1 again. The container's memory limit stays 512m with no swap (`mem_limit` and `memswap_limit` unchanged), and the `tmpfs` pages count against it. `start.sh` still removes nothing; its usage text, the compose file's header and `federation/stack/README.md` now say that the data lives only while the database container runs, that the scripts create no credentials file, and how to remove the stack with the variables, project and profile Compose needs.

The same commit rewrote `README.md` and `federation/stack/README.md` for an outside reader, gave the gate counts of the runs in `federation/acceptance/README.md` and said there that mapping releases 1.2 and 1.3 give the same question 6 answer, said in `study/evidence/README.md` that the `commit` field of each run manifest is a lab commit, and labeled the bare lab ids in `study/guide/README.md` and in the [entry of 2026-10-02 on the shared baseline branch](2026-10-02T0756Z-shared-baseline-branch-lessons.md). Its parent is `b52f9affb1709e550ed2a8a9bdfb70d022b9f559` (Comitas release 0.6.2) and its tree `6441b48`; it changed 8 files, 188 lines added and 49 removed. It follows the implementation checkpoint of [the recovery-chain entry](2026-10-22T2342Z-recovery-chain-adopted.md).

## What was verified

Each check is listed with its recorded result and, where it can be repeated, the command that repeats it; a command is how to run the check again, not evidence that it passed.

**On the commit's exact tree, before the commit** (the checks the checkpoint tool selected for the profile `federation-integration` and ran fresh, on 2026-10-26; all exited 0):

- Staged whitespace (`git diff --cached --check`): clean, 0.05 s.
- Continuity (`python -B governance/tools/validate_continuity.py`): PASS, 14.0 s.
- Apollo router offline (`python -B federation/routers/apollo/validation/run_router_gate.py offline`): 39 tests, PASS, 26.5 s.
- Apollo router on a disposable stack (`APOLLO_ELV2_LICENSE=accept python -B federation/routers/apollo/validation/run_router_gate.py stack`): 35 tests, PASS, 301.0 s.
- Cosmo router offline (`python -B federation/routers/cosmo/validation/run_router_gate.py offline`): 40 tests, PASS, 37.2 s.
- Cosmo router on a disposable stack (`python -B federation/routers/cosmo/validation/run_router_gate.py stack`): 36 tests, PASS, 334.2 s.

After the commit the tool ran continuity again, which failed with exactly "Stale implementation checkpoint: runtime history has advanced": the expected continuity-follow-up-pending phase that this entry and the Progress row close.

**Before the commit, on the mission's working copy with the `tmpfs` applied** (reported by the worker who made the change; not repeated by the records worker):

- The double start, on fresh compose projects removed afterwards with `docker compose -p <project> down --volumes`: with Apollo, `start` (50 s), one cross-system query, `stop`, `start` again (41 s), the same query, `stop`; with Cosmo the same (45 s and 43 s). Every round's bootstrap loaded the 32 assets of release 1.1, the two routers returned the same answer (SHA-256 `2555a9e0...` of the response) and `assets-db` had no volume. Repeat with the quickstart and the verification query of [the stack README](../federation/stack/README.md).
- The stack gates, unsealed: Apollo 35 tests in 296.4 s (parts 17, 7, 9 and 2) and Cosmo 36 tests in 319.0 s (parts 17, 7, 9, 1 and 2), both PASS; each removed its own project.
- The offline gates: Apollo 39 tests in 26.2 s and Cosmo 40 tests in 36.6 s, PASS; after the later README and usage-text changes Apollo 39 tests in 25.8 s and Cosmo 40 tests in 36.1 s, PASS, with `bash -n` and `git diff --check` clean.
- The README commands, as written, on throwaway projects: the Apollo and Cosmo start, the verification query, status and stop each exited 0 and both routers returned the JSON the stack README quotes; the removal command exited 0 and left no container, volume or network of the project; the composed supergraph and execution config were byte-identical to the committed files.
- Question 6, derived for mapping releases 1.2 and 1.3: both 182 / 65 / 26, 73.7 percent, 27 cancelled missions not counted, 12 references not resolved (12 occurrences of 9 distinct crew references, all UNMAPPED).

**Checked by the records worker at the commit** (reading its files, after the commit): in `study/guide/README.md` and the entry of 2026-10-02 every occurrence of the scoped ids lab commit `506eeb1`, lab commit `03abf8c`, lab commit `cf114eb` and lab commit `f8b31eb` carries the `lab commit` label. The fifth place of the scope, the lab main id in `project-governance/RATIONALE.md`, is not in this commit and stays unlabeled there; the entry of 2026-10-02 also still holds one bare reference to lab commit `b77b23a`, which the scope did not name.

**Observed memory usage of `assets-db`** against its 512 MiB limit, read with `docker stats` while the containers ran and before any cleanup (reported by the same worker; UTC times of 2026-10-26):

- Double start, Apollo: 69.5 MiB at 15:01:22 after the first start and 70.06 MiB at 15:03:11 after the second; the `tmpfs` held 46M of its 128M.
- Double start, Cosmo: 69.41 MiB at 15:05:23 and 70.14 MiB at 15:07:14.
- The cgroup's `memory.peak` since each container started: 85.5 MB and 87.2 MB (Apollo), 86.7 MB and 87.1 MB (Cosmo).
- During the unsealed stack gates, sampled about every 15 s: Apollo 16 readings from 15:08:53 to 15:13:16, 68.52 to 74.27 MiB; Cosmo 18 readings from 15:13:49 to 15:18:48, 70.11 to 77.16 MiB; the highest `memory.peak` read 87.0 MB and 87.8 MB.

## Not run or not covered

- The memory usage was not read during the sealed stack gates; the readings above come from the runs before the commit.
- The full governance suite (`python -B governance/tools/run_tests.py -s governance/tests -s governance/config -p 'test_*.py'`) was not run on the commit's exact tree. Run on an earlier working copy of the mission, which still held an edit of `project-governance/RATIONALE.md`, it reported 1384 tests in 775.9 s with 1 failure and 1 skip: `conformance/test_extension_removal.py` judges the uncommitted runtime edits of its copy as a stale implementation checkpoint, and on clean main the same test passed. The worker reported this as a matter of the framework; the lead developer then took the rationale edit out of this commit for a later record transaction.
- The real-service mode of the stack (Missions on Oracle) was not run; the stack ran with its default Missions stub.
- No manual acceptance is recorded.

## How it landed

The commit was approved through the early conditional approval: the lead developer's go at the preview, with every check passing at the seal. The first prepare had been withdrawn without changing content because the Apollo stack gate ran without `APOLLO_ELV2_LICENSE=accept` and stopped before its tests. After the commit, the checkpoint tool of Comitas 0.6.1 could not verify it: it read the `implementation_checkpoint` fact from the framework's reconstruction contract only, while this project declares that fact in its own part of the contract. Comitas release 0.6.2 fixed the lookup and landed on main as `b52f9affb1709e550ed2a8a9bdfb70d022b9f559`; the upgraded tool then verified this unchanged commit and moved it into the follow-up-pending phase, and this entry with its index line and the Progress row is the follow-up.

Before it reached main, the commit was replayed onto the upgraded main with the same changes, and every check ran again.
