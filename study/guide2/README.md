# Study 2 guide

The written guide of Guided Direct Access in study 2 of the [Abstraction ladder study](../README.md), written blind and checked independently under decision J of the [study 2 design](../../docs/STUDY-2-DESIGN.md): a new integration guide, written by a fresh worker without exposure to the scored corpus, the answer key or study 1's task-level findings; given only the study-2 service contracts, the tool capabilities and general business context; independently checked for accuracy and coverage; frozen with its version and hash before scored execution; no revisions driven by outcomes. Study 1's guide in [study/guide/](../guide/README.md) is unchanged.

The guide is [GUIDE.md](GUIDE.md): 10,990 bytes, 103 lines, LF line ends, SHA-256 `e9a4c12620fea0b924683666f20f44a60a4d8888088b583038e1e47cd0b3fade`, here byte for byte as its author wrote it. It is not frozen yet: the freeze records its hash before the first scored run. The harness appends one file to the system prompt of the beta scenario, the scenario's `guide_file` (`make_config.py --guide-file`).

## How it was made

All of it on 2026-11-01, in the Job `study2_guide` (decisions G1 to G7).

- **The author's inputs.** The guide package that `study/blind/blind.py` builds from lab commit `6c18afa638ce583dcd79125177ba9a210f5a3686`, package hash `17d027e0d7f8bf129e4345d9cb87fa6ee41b195353c355259ab02e9269b7684b`, `MANIFEST.json` SHA-256 `054a01e5c422630b6d8313540de2a1a3b2553eb896578fd76264ff2762bb310d`: the three services' contracts, designs and READMEs, the mapping releases 1.0 to 1.3 and the tool texts, and nothing of `study/`. No file it is built from changed between that commit and lab commit `3b523c5`, on which this folder was added.
- **The author.** GPT-6 Astra at reasoning High (it reports itself as Codex, based on GPT-6), in a Codex cloud task with network access None, on a private repository made from the package (its package commit `6283a9e`, its final commit `d97c634`). It reached the live services only through the request relay ([study/blind/](../blind/README.md)): 2 rounds, 60 requests, run against the beta stack with the real Missions service, each on the lead developer's go.
- **The checker.** Claude Opus 5.5 at reasoning High, in a Claude cloud session with network access None, on a second private repository. Its inputs were the same package, the author's first draft, the author's relay folder and the real service's step 4 records of the preflight (`study/evidence/study-2-preflight/04-service-real-20261030T232712Z.json` and `04-compare-real-vs-simulated-20261030T233054Z.json`), listed with their hashes in a manifest of SHA-256 `c9df4779c0c7b58298e47e3af5e59ed9a25de54918189b47921ab3371df66be6`. It asked 1 relay round of 29 requests. It never saw the corpus, the keys or study 1's findings.
- **The check and the revisions.** The checker's [findings](check/FINDINGS.md) were 6 on accuracy and 11 on coverage. The author received them word for word and revised; the checker confirmed every one fixed and named three wording points the revision had made unclear; a second, smaller cycle on the lead developer's word fixed those three, and the checker confirmed it ([confirmation](check/CONFIRMATION.md)). No finding was disputed.
- **The versions.** First draft 11,909 bytes, SHA-256 `4d66ec5888f3c8b561ce882d931100ef1f36b0d1ad68bdf95d04225ab6dd6e06`; first revision 10,889 bytes, `0cf9368b2ef9df980bdc5cf4dc4c53f735b4b06875afaff3d7d389c61c859fe3`; final 10,990 bytes, `e9a4c126...`, three lines changed from the first revision. The earlier versions are kept in the checker's repository. Decision G5 aimed near study 1's 8,872 bytes and set 20 KB as the ceiling.

## The folder

| Path | What it is |
| --- | --- |
| `GUIDE.md` | The final guide. |
| `relay/` | The author's relay folder: each round's request file and answers file and `LEDGER.json`, SHA-256 `0d173f6e53fdfb33a4e143cd29210751cc365c6a6e7560f8611fb281d423a961`, whose chain hash after round 2 is `3008d4d8351db9258d7b8fd0b05522f98aeafef60bf222670f5b0e4102c9786c`. |
| `check/FINDINGS.md` | The checker's findings, SHA-256 `f80a2ed813aabd66fa104a402d1924cdeb0af8226271fcbd1ee13df369b2b235`. |
| `check/CONFIRMATION.md` | The checker's confirmation of both revision cycles, SHA-256 `ccd9700cc0c7345b23879d9b12e9c5352da0172f977a531cbe13aa4a2e91e3a5`. |
| `check/relay/` | The checker's relay folder: its round and `LEDGER.json`, SHA-256 `2e908c5afb218846808b0fd5cfac0048bbde8121bb6f170a1405576d4ff1dbc5`, chain hash `153610b6cc2016164b4041fd011167f1eb6e9031efea7aaa239e093ce57b2bc8`. |

Every file here is the byte copy of the file the author or the checker wrote or the relay recorded. The author's round 1 request file has CRLF line ends, as it was saved before that round ran, so `.gitattributes` keeps both relay folders out of line-ending conversion. Each relay folder checks against its own ledger with `study/blind/relay.py verify`, which refuses a folder inside the lab checkout: copy the folder to a new folder outside any Git work tree and run, from the root of the lab checkout:

```sh
python -B study/blind/relay.py verify --dir '<the copy>'
```

The transcripts of the author and the checker stay with the lead developer. The area accepts Markdown and JSON files.
