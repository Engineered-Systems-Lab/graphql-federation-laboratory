# Study evidence

The compact evidence files of the [Abstraction ladder study](../README.md) kept in the repository: the score table and the run manifest of each scored run, and the bundle and archive checksums that tie them to the raw run bundles. The raw transcripts and bundles stay outside the repository and are cited by checksum.

## Files

| File | Holds |
| --- | --- |
| `study-1/scores.csv` | The score table of study-1: 320 runs, five scenarios, two models, two trials, as the harness wrote it. |
| `study-1/manifest.json` | The run manifest of study-1: harness and corpus hashes, models and settings, limits, prices, machine and stack facts. |
| `gamma-prime-1/scores.csv` | The score table of gamma-prime-1: 64 runs of Gamma after the mapping lookups landed. Its scenario column says `gamma`; the analysis names it Gamma-prime. |
| `gamma-prime-1/manifest.json` | The run manifest of gamma-prime-1. |
| `checksums.json` | Per run: the bundle checksum, the SHA-256 of `bundle.json`, of the archive zip and of the archive's per-file sums file, and of each evidence file. |

Each score table and manifest is a byte copy of the file in the run folder, taken from a copy verified against the archive's per-file sums on 2026-10-21. A Windows checkout may hold them with CRLF line ends; their checksums are of the LF bytes the run wrote. The [analysis](../analysis/README.md) refuses to run when its copies of the run folders differ from these files or from these checksums, and its tests check these files against `checksums.json`. The `commit` field of each run manifest is a lab commit: the commit of the original lab repository, where the harness ran, not a commit of this repository.

## Where the raw data are

| Run | Bundle checksum | Archive | Archive SHA-256 |
| --- | --- | --- | --- |
| study-1 | `b914cafa2528a3b62feaabdab3af32727c2e2dcb14238cf489e421fd2b70a6b2` | `lab-results-2026-10-21.zip` | `1b74534e0a3238fef1ca46bdd8d8a1c9c262ef8c3f5a10f6926187e4e39885ab` |
| gamma-prime-1 | `ff31d2bb752ef1df5b3fb28f7be767c2862b53b197b9ae441a6b9f078329390c` | `gamma-prime-1-2026-10-21.zip` | `1c394bd06edfc98bb7556c7a6af02f08b1f28de86d8ec9042131aa59e2aa8ff6` |

The bundle checksum is the runner's checksum over the bundle's file list (`study/harness/runner.py`, `write_bundle`). The originals in the machine-local results folder are read-only, and the archives are kept with their per-file sums files beside them, outside the repository.
