# The Abstraction Ladder: Evaluating AI-Agent Access to Legacy Systems

The lab compares how well language-model agents answer questions about the USS Enterprise legacy systems when the same questions are asked through five different arrangements: the raw legacy systems, the raw systems with a written guide, the four adapters alone, the adapters behind the Apollo router and the adapters behind the Cosmo router. The method, the scenarios and the open points are in the [agent scenario design](../docs/PLAN.md#agent-scenario-design) of the plan; nothing of that design is repeated here. In the study stack of study-1 and gamma-prime-1, Missions was a simulator, not the Oracle-backed Missions service, while Personnel and Assets were the real services: see [the report's correction](../docs/AGENT-STUDY-REPORT.md#correction-2026-10-21-the-study-testbed).

## Layout

- [corpus](corpus/README.md): the task corpus and its expected answers.
- [mcp](mcp/README.md): the local MCP servers, one per scenario.
- [harness](harness/README.md): the agent loop for the two vendors, the scoring and the run manifests.
- [launch](launch/README.md): the launch kit: each scenario's stack start, stop and outages, with the Missions simulator or the real Missions service, and the generator of the machine-local study config.
- [guide](guide/README.md): the written guide of the second scenario.
- [analysis](analysis/README.md): the analysis scripts that write every table and figure of the study's report.
- [evidence](evidence/README.md): the score tables, the run manifests and the bundle and archive checksums of the scored runs.

The results of the scored runs are in the [Abstraction ladder study report](../docs/AGENT-STUDY-REPORT.md). The design of the next study, decided before any of its runs, is in [Abstraction ladder study 2: design](../docs/STUDY-2-DESIGN.md).

## Rules of the folder

- Nothing here derives a location from the path or the name of the lab checkout. The folder of raw run results is the machine-local setting `LAB_RESULTS_DIR`, outside the repository; manifests name a result bundle by run id and checksum.
- API keys come from the environment only and are never written to a file, a log or a manifest.
- Each area accepts only the file types its rows in the [artifact classification table](../project-governance/ARTIFACT-CLASSIFICATION.md) name.
