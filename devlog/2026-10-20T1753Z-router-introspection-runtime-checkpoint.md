# Both routers answer introspection through their own configuration

Date: 2026-10-20T17:53Z
Subject: Committed the introspection setting of the Apollo and Cosmo router configurations for the agent study, with an introspection test part in each stack gate
Status: Historical / non-normative
Lab checkpoint: lab commit `c20dfbfd76585e5287bc3df4f576e1f7a68c2af7`
Provenance: Git committer timestamp `2026-10-20T13:53:30-04:00` (2026-10-20 17:53:30 UTC), converted to the prescribed UTC minute. The lead developer's ruling of 2026-10-20 (enable router introspection with the existing mechanisms, Apollo enabled, Cosmo verified and enabled if needed, as its own governed scope) came through the study MCP worker; in this session the lead developer answered the Cosmo question (set it explicitly), stopped the lab stack for the gates and selected "go" at the preview; the go approved the exact candidate under the early conditional approval, every check having passed.
Migrated from lab log SD-2026.293-1753Z; originally written in the lab on 2026-10-20 (lab commit `fc3389c22b8b0a99a25d752659b9db2ee5aec311`); the study it names is now the Abstraction ladder study.

## Meaningful transition

The Apollo router answered every schema query with `INTROSPECTION_DISABLED`, so the study's Delta scenario could not discover the schema through it. `router.yaml` now sets `supergraph.introspection: true`. The pinned Cosmo router already answered by default; `config.yaml` now says `introspection.enabled: true` explicitly. Each stack gate has a new part that asks the router for `__schema` and `__type` and asks each of the four adapters for `__schema`. The commit is on the owned branch `tx/20261020-router-introspection`, parent lab commit `506eeb1db9fb81d59378529f55df69798c2c4feb`, tree `a30124d`.

## Choices recorded

- **Cosmo explicit.** The worker found the Cosmo default on and offered to leave it with a comment only; the lead developer chose the explicit setting, so the study manifest can name a setting and a version change cannot flip it.
- **Production note.** Both configurations say in a comment that production deployments usually keep introspection off.
- **Fairness.** The adapters answer introspection unchanged; their `_service` and `_entities` plumbing is not touched here.
- **Environment.** The first prepare failed four adapter offline gates because the worker had exported `MSYS_NO_PATHCONV`; the attempt was abandoned and the unchanged candidate passed.

## Retained evidence and limits

Measured before the change: the Apollo router on the running lab stack refused introspection, the four adapters answered it, and a throwaway Cosmo container with the then-committed configuration answered it with introspection true in its start log. Not claimed: Hive, benchmarking, or any change to the subgraphs, the supergraph or the execution config.

## Follow-up

The verified runtime commit entered the continuity-follow-up-pending state until this separately approved Progress and index change advanced `implementation_checkpoint`. [Progress](../docs/PROGRESS.md) owns current state. Integration of the exact tip and removal of the owned worktree follow after continuity passes. No push.
