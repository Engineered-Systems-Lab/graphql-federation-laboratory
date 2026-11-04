# Study evidence

The compact evidence files of the [Abstraction ladder study](../README.md) kept in the repository: the score table and the run manifest of each scored run, and the bundle and archive checksums that tie them to the raw run bundles. The raw transcripts and bundles stay outside the repository and are cited by checksum.

## Files

| File | Holds |
| --- | --- |
| `study-1/scores.csv` | The score table of study-1: 320 runs, five scenarios, two models, two trials, as the harness wrote it. |
| `study-1/manifest.json` | The run manifest of study-1: harness and corpus hashes, models and settings, limits, prices, machine and stack facts. |
| `gamma-prime-1/scores.csv` | The score table of gamma-prime-1: 64 runs of Gamma after the mapping lookups landed. Its scenario column says `gamma`; the analysis names it Gamma-prime. |
| `gamma-prime-1/manifest.json` | The run manifest of gamma-prime-1. |
| `study-2-preflight/` | The backend preflight of study 2 (steps 1 to 6 and 8 of `study/preflight/`, run on 2026-10-30 and 2026-10-31 UTC): each step's record, copied from the machine-local results folder with LF line ends and the local Python path in the outage commands written `<python>`, and `preflight-record-20261101T013718Z.json`, the report with the decision-L classification, the lead developer's judgement and go or no-go, and `gates-index.json`, the command, main commit, exit code, result line and log checksum of each router and adapter gate run outside the kit. The machine-local originals and the gate logs stay outside the repository. |
| `study-2-preflight/07-answerability-<arm>-<set>-real.json` | Step 7 of study 2's preflight (2026-11-02 UTC): the 20 reports of `study/corpus2/reference/run_reference.py` on the real Oracle-backed stack, five arms, each with every set and the Missions, Assets and Personnel outages, byte for byte as the runs wrote them. The draw of the 48 scored tasks (seed 313) was made from them. |
| `study-2-preflight/09-study2-dev-notool-1/`, `09-study2-dev-tool-1/` | The score table and run manifest of study 2's two paid development runs (2026-11-03 UTC), byte copies of the run folders' files: run 1, 64 runs of the 8 development tasks in four arms without the calculation tool, and run 2, 80 runs on study 2's block schedule in all five arms with it. |
| `study-2-preflight/09-dev-runs-checksums.json` | Per development run: the bundle checksum, the SHA-256 of `bundle.json`, of the run folder's per-file sums file and of each evidence file. It is kept apart from `checksums.json`, which holds study 1's runs only. |
| `study-2-preflight/preflight-record-steps-7-9-20261104T022919Z.json` | The step 7 and step 9 record: the answerability result and its finding, both development runs' outcomes and spend, the calculation tool's declared check with every failure classified by cause and the lead developer's verdict (it fails), the comparison with study 1 and gamma-prime-1, the measurements for the freeze, and the updated go or no-go. |
| `checksums.json` | Per run: the bundle checksum, the SHA-256 of `bundle.json`, of the archive zip and of the archive's per-file sums file, and of each evidence file. |

Each score table and manifest is a byte copy of the file in the run folder, taken from a copy verified against the archive's per-file sums on 2026-10-21. A Windows checkout may hold them with CRLF line ends; their checksums are of the LF bytes the run wrote. The [analysis](../analysis/README.md) refuses to run when its copies of the run folders differ from these files or from these checksums, and its tests check these files against `checksums.json`. The `commit` field of each run manifest is a lab commit: the commit of the original lab repository, where the harness ran, not a commit of this repository.

## Where the raw data are

| Run | Bundle checksum | Archive | Archive SHA-256 |
| --- | --- | --- | --- |
| study-1 | `b914cafa2528a3b62feaabdab3af32727c2e2dcb14238cf489e421fd2b70a6b2` | `lab-results-2026-10-21.zip` | `1b74534e0a3238fef1ca46bdd8d8a1c9c262ef8c3f5a10f6926187e4e39885ab` |
| gamma-prime-1 | `ff31d2bb752ef1df5b3fb28f7be767c2862b53b197b9ae441a6b9f078329390c` | `gamma-prime-1-2026-10-21.zip` | `1c394bd06edfc98bb7556c7a6af02f08b1f28de86d8ec9042131aa59e2aa8ff6` |

The bundle checksum is the runner's checksum over the bundle's file list (`study/harness/runner.py`, `write_bundle`). The originals in the machine-local results folder are read-only, and the archives are kept with their per-file sums files beside them, outside the repository.
