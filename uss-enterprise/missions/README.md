# Missions

Missions v1 is a native REST/XML service on Oracle 18c through plain JDBC. This
component supplies the executable contract, the six-table schema with its immutable
dataset release, the Java service with its read operations (`GET /missions`,
`GET /missions/{id}`, `GET /missions/{id}/changes`) and its write operations
(`POST /missions` and `PUT /missions/{id}`), and the real-Oracle acceptance gate of
each part. The [image and compose deployment](#packaging-and-deployment) are supplied and
have their own gate. Normative authority is
the [Missions design](../../docs/MISSIONS-V1-DESIGN.md), including its reviewed
schema/dataset amendment.

The sections before the [read service slice](#read-service-slice) record the
schema/dataset slice as it was accepted on 2026-10-09, when no Java REST service
existed, and stay as written, acceptance limitations included. The
[read](#read-service-slice) and [write](#write-service-slice) service sections
describe the service and its evidence.

- [Contract 1.0](contracts/missions-v1.0.xsd) remains immutable.
- [Compatible 1.1](contracts/missions-v1.1.xsd) adds only MAINTENANCE, same namespace.
- [Schema](schema/schema.sql) creates six tables, two sequences, local integrity
  guards, immutable audit and a transactional clock helper.
- [Recipe](datasets/recipe.json) and [curation inputs](datasets/curation.json)
  specify the deterministic candidate; [release 1.0 manifest](datasets/releases/1.0/manifest.json)
  binds exact content and archived authoring inputs. Published releases cannot be reused.
- [Release 1.1 manifest](datasets/releases/1.1/manifest.json) appends to release 1.0: 300 missions
  (the 31 of 1.0 unchanged with their ids, 57 new curated canon missions, 45 generated maintenance missions and
  167 generated routine missions, all generated ones labelled synthetic in the
  [provenance](datasets/releases/1.1/provenance.json)), with the deliberate edge cases listed in its edge ledger.
  Select it explicitly: `reset.sh --dataset 1.1`.
- [Operator](datasets/missions_operator.py) owns explicit provisioning/reset. The
  [shell wrapper](datasets/reset.sh) runs it directly with Python.
- [Data acceptance](validation/runtime/data/test_data.py) executes real Oracle
  DDL/load/reset in a unique disposable schema; missing dependencies fail.

The fixed SHA256 counter recipe uses independently keyed categories and
mission/event substreams, master 1701, canonical byte formats and fixed input order.
No startup/reset calls the generator. The 31-mission/101-change candidate keeps
the accepted lab status mix. Every cost/date/reference/assignment/history is lab
adaptation; provenance distinguishes episode inspiration and reported source
stardates from inventions. Two modest objective revisions use recorder-specific
styles. The audit is not a full objective snapshot or guaranteed drift history.

The physical external-reference capacity is 50 bytes under ASCII grammar. XML
reference patterns remain unbounded: this is a known lab storage limitation,
with no invented API error mapping or full service-conformance claim. Text has
20% headroom and CLOB storage; XML/application code-point limits stay authoritative.
Later context (2026-10-15): the service now answers a reference beyond the capacity
with 422, see the [findings of the write slice](#write-service-slice).

## Explicit operator workflow

Run from the repository root with Python 3.13 or later. Provisioning requires
the lead developer's concrete environment preview go; this README supplies no approval.
The reviewed [environment](datasets/oracle-environment.json) pins Oracle 18.4 XE
to its registry digest, Linux/amd64, 4 GiB memory, two CPUs, 1 GiB shared memory,
a dedicated ownership-labeled internal bridge with no external routing, no
published host ports or host mounts, and an ownership-labeled container.
Reserve 20 GiB for image/database storage. A random admin password is supplied
through the process environment, never committed or printed; Docker inspection
can expose that environment to operators with Docker access. No client install,
JDBC driver, Tomcat image or Java service provisioning is part of this slice.

```sh
python -B uss-enterprise/missions/datasets/missions_operator.py provision
sh uss-enterprise/missions/datasets/reset.sh --dataset 1.0
```

Provision refuses an existing same-name container rather than adopting it. Image
pull and database creation are explicit; tests/reset do not provision implicitly.
The database's only managed durable schema is MISSIONS_LAB, initially a schema-only
Oracle account. Later JDBC authentication/grants belong to the service slice.
Provisioning retains its owned container on failure for inspection; it never
removes unrelated images, containers, networks or volumes. The internal network
is created explicitly and inspected for internal/bridge/ownership settings;
unrelated or differently configured same-name networks are refused. Operator cleanup is separate
and limited to this exact owned container after required evidence is preserved.

Reset verifies the selected release before destructive DDL and requires the
documented service container starfleet-missions-service stopped or absent. This
guard covers the named deployment, not unknown remote service processes. It
refuses unexpected schema objects, restores all six tables/next sequences/clock,
compares every loaded scalar/collection/audit value, checks Oracle 18c and AL32UTF8,
then reports the explicit version. No command starts Missions. Oracle DDL commits
make the whole reset nontransactional: any failure requires inspection and a
successful explicit reset/validation while service remains stopped.

Acceptance selects missions-offline and missions-data, not Personnel, REST/JDBC
or full packaging gates. The tests do not claim API mutation acceptance. Runtime
commit completion requires the separately delegated fresh Progress/devlog entry worker
and its separate exact checkpoint approval before integration or worktree cleanup.

## Startup findings from this candidate

The pinned image downloaded successfully on 2026-10-09. Three network-none
startup attempts failed before database initialization: Docker's generated
hostname was unresolved; localhost triggered a native resolver SIGSEGV in
libclntsh.so.18.1/snlinGetAddrInfo; a named IPv4 loopback mapping was rejected
as having no valid IP address. Failed owned containers were diagnosed before
replacement. At that stage, no schema load, Oracle acceptance or service
publication had passed.
The lead developer approved the dedicated internal bridge, and listener setup passed.
Database creation then rejected the generated 39-character admin password with
OPW-00007; generation was corrected to 27 characters without recording its value.
Image/resources remained unchanged. The image defaults to OS root; the first
local SQLPlus call returned ORA-12547. Explicit Oracle OS-user execution
resolved it. Initialization and the later checks below then passed.

## Schema and dataset acceptance (2026-10-09)

Observed Oracle Database XE 18.4.0.0.0 (`version_full`; the legacy `version`
column reports 18.0.0.0.0) and AL32UTF8 in the pinned Linux/amd64 image. The
approved dedicated internal bridge was inspected as internal/bridge with the
mission ownership label; no host ports or host mounts were published. Missions
remained stopped throughout. The random database admin password is not evidence.

Executed from the repository root through the admitted governance launcher:

- `uss-enterprise/missions/datasets/missions_operator.py reset --dataset 1.0`
  passed the actual DDL/load and exact loaded-value comparison: 31 missions,
  101 changes, all six tables, child references, costs/NULLs, audit values,
  release identity, clock baseline and next sequence positions.
- `sh uss-enterprise/missions/datasets/reset.sh --dataset 1.0` passed through
  the documented wrapper in Git Bash, again comparing the complete release.
- `validation/missions_runtime.py data` passed all 12 tests (8 Oracle and 4
  release tests), zero skips, in 43.950 seconds on the pre-seal accepted run.
  The unique disposable acceptance schema was removed by suite cleanup.
- `uss-enterprise/missions/validation/validate.py` passed the 1.0 probes, all
  six old fixtures under 1.1, and the 1.1-only MAINTENANCE fixture; canonical
  schema comparison proved the sole wire addition and preserved 1.0 rejection.
- Focused artifact-classification tests passed all 48 tests; pre-commit
  continuity and the exact staged whitespace check passed.

Oracle acceptance established append-only audit/immutable mission identity,
local foreign-key and reference constraints, zero/absent/maximum decimal
behavior, shared transactional-clock rollback, atomic scalar/collection/audit
failure rollback, real two-session clock-lock serialization, sequence exhaustion,
explicit reset positions, stopped-service and unknown-release failure guards,
and exact 2,000 supplementary-character CLOB/120-character title round-trips.
Release acceptance established archived reproduction, independently keyed
category draws, tamper/history corruption rejection and code-point bounds.

The first full data run failed two probe assertions: RPAD used display width
for supplementary characters, and SQLPlus displayed a maximum sequence value
in scientific notation. Probes were corrected to construct exact characters
and request exact decimal text, then the complete suite passed. Earlier
operator import/name and Unicode-literal authoring defects, and classifier
golden ordering, were repaired after actual failures; these are not hidden PASS.

Limits: schema/dataset only; no Java REST/JDBC, HTTP mutation or packaging
acceptance, no Personnel mapping or gates. Physical ASCII references stop at
50 bytes despite unbounded wire grammar. Oracle DDL prevents whole-reset
rollback; the guard covers only the documented service container. Objective
history is not a full semantic snapshot. The owned database is retained for
follow-on work. Runtime commit verification/Progress/lab log continuity remain
separate obligations; this report alone does not authorize integration.

## Read service slice

The native read service is Java 17 / Maven: Jersey 2 (`javax.ws.rs`) on embedded Tomcat 9,
plain JDBC through Tomcat's pool to Oracle 18c, and JAXB types generated from the frozen
[1.1 contract](contracts/missions-v1.1.xsd), which also validates every response before it is sent.
The read operations of the [design](../../docs/MISSIONS-V1-DESIGN.md) are `GET /missions`
(nine filters, paging, order by stardate, priority, missionId), `GET /missions/{id}` with its strong
ETag and `GET /missions/{id}/changes` (numeric changeId order), with the Accept grammar and the 400, 404,
405, 406 and 500 mappings. An unknown path answers a bodyless 404 because the frozen contract defines no
body for it. The image, compose file and the `starfleet-missions-service` name are described under [Packaging and deployment](#packaging-and-deployment).

Configuration comes from the environment: `MISSIONS_JDBC_URL`, `MISSIONS_DB_USER`, `MISSIONS_DB_PASSWORD`,
`MISSIONS_DB_SCHEMA` (default `MISSIONS_LAB`), `MISSIONS_PORT` (8080) and `MISSIONS_BIND_HOST` (127.0.0.1 or
0.0.0.0). The read operations need a login with `CREATE SESSION` and `SELECT` on the six tables; the
[write operations](#write-service-slice) need the grants listed there. Creating the login for a deployment is
an explicit operator step, not part of reset.

[Read acceptance](validation/runtime/service/test_read_service.py) runs the real service through a login that can
only read: it builds a uniquely tagged image whose build runs `mvn verify` on JDK 17 (the Java unit tests), loads
release 1.0 into a disposable schema of the reviewed Oracle container, creates the disposable login, starts the
service on an ephemeral loopback port joined to the internal Oracle network, and compares every response with the
release. The image, schema, login and container handling is shared with the write gate in
[service_harness.py](validation/runtime/service/service_harness.py), which builds one image per run and removes
every container, image, login and schema it created. Run both gates with
`python -B uss-enterprise/missions/validation/missions_runtime.py service`.

## Write service slice

`POST /missions` and `PUT /missions/{id}` complete the operations of the design on the same Jersey/Tomcat/JDBC
service. Nothing is generated by the client except the content: the service owns `missionId`, `lastUpdated`,
the change id and the ETag.

- **POST** takes a mission without `missionId` and `lastUpdated` (either present is 422), generates the identifier
  from a base-36 Oracle sequence (`ST-` and nine characters; an exhausted sequence fails, it never wraps or reuses),
  and answers 201 with the relative `Location: /missions/{id}`, the strong `ETag` and the created mission.
  A generated identifier that already exists is 409 `RESOURCE_CONFLICT`.
- **PUT** is a full replacement. The body must carry the URI's `missionId` (absent is 422, different is 409) and no
  `lastUpdated`. `If-Match` is required: missing is 428; a wildcard, a weak tag, a malformed or non-canonical tag,
  several tags or a repeated header are 400; one well-formed strong tag that is not the current one is 412
  `ETAG_MISMATCH`. Success is 200 with the resulting mission and a new ETag, and the ETag always advances, also
  when no value changed.
- Both require `X-Starfleet-User` and `X-Starfleet-Ordered-By` (canonical `C-*` references) and
  `X-Starfleet-Audit-Summary` (UTF-8, 1 to 256 code points, at least one non-whitespace code point); each is
  400 `INVALID_REQUEST` when missing, repeated or invalid. The summary is stored byte for byte as received:
  no trimming, no normalization. The body media type is `application/xml` with an optional `charset=UTF-8`,
  anything else is 415, and the XML is read without DTDs or entities and validated against the 1.1 schema (400).
- Domain failures are 422 `DOMAIN_VALIDATION_FAILED`: the cost lifecycle table, the cancellation provenance
  (a cancelled mission may omit its estimate only when its immediate predecessor was PLANNED, or CANCELLED with
  that eligibility; the flag is stored in `cancelled_without_estimate_allowed`), a missing commander,
  an outcome before a terminal status, duplicates in a collection, whitespace-only text and a reference longer than the
  50-byte storage capacity. Processing is fail-fast: the first failure answers.
- `PATCH`, `DELETE`, `HEAD` and `OPTIONS` answer 405 with an `Allow` header naming only what the path supports
  (`GET, POST` on `/missions`, `GET, PUT` on `/missions/{id}`, `GET` on `/missions/{id}/changes`). The framework's
  own HEAD and OPTIONS handling never runs, because routing is decided ahead of it.

Each mutation is one database transaction. It first calls `missions_clock_tick`, which locks the singleton clock
row and advances Oracle's reference clock, then locks the mission row, rechecks the ETag under that lock,
allocates the change id from its sequence, writes the mission, replaces its collections and appends the audit
event (`CREATED` or `UPDATED`, with the cost values and signed changes of the design). The same instant is
`lastUpdated` and `changedAt`; no host clock is used. Any failure rolls all of it back, the clock advance included,
so refused and failed requests leave no trace; the sequences are not transactional and leave gaps.

The service login of the write operations needs `CREATE SESSION`; `SELECT`, `INSERT` and `UPDATE` on
`missions`; `SELECT`, `INSERT` and `DELETE` on `mission_assigned_crew`, `mission_participants` and
`mission_assigned_assets`; `SELECT` and `INSERT` on `mission_changes`; `SELECT` on `mission_id_seq` and
`change_id_seq`; and `EXECUTE` on `missions_clock_tick`. It needs nothing on `mission_clock` (the function runs
with its owner's rights) and no right to change or delete audit rows.

[Write acceptance](validation/runtime/service/test_write_service.py) runs against the same real service and Oracle
container with a login holding exactly those grants. It covers every row of the error table, the cost matrix
(creation and replacement), cancellation provenance, the service-owned elements, every If-Match form, the media type,
encoding and Accept rules, the header forms and the exact UTF-8 summary (compared with the stored bytes), the audit
trail and its cost population, ETag advance on an unchanged PUT, parallel writers (one winner on a shared tag, a
gapless clock and one global change order), atomic rollback on a forced audit failure, a clean 500 without a database,
sequence overflow for both sequences and the 405 `Allow` lists.

Findings of this slice:

- **Container-level rejections.** Tomcat refuses a control character in any header value (U+000B, U+000C,
  U+001C to U+001F, DEL) itself, before the application runs. It first answered its own HTML 400; since 2026-10-15 the
  [`XmlErrorReportValve`](src/main/java/lab/enterprise/missions/api/XmlErrorReportValve.java), installed on the host
  by `Main`, gives that 400 the contract's XML error body (`INVALID_REQUEST`). The unit tests run a real embedded Tomcat
  against it and the gate shows the XML 400 for POST and PUT. Any other status of the container keeps Tomcat's page.
- **Content-Type.** Jersey parses the request Content-Type before any filter and answers a bare 400 for a value it
  cannot parse or for a repeated header. `MissionsServlet` guards that: POST and PUT get the contract's 415 with the
  XML error body; any other request routes as if the header were absent.
- **Summary characters.** A summary carrying U+FFFE or U+FFFF (valid UTF-8, but not representable in XML 1.0, which
  would break the change log representation) is refused with 400; the design does not name them.
- **Body size.** A body above 8 MiB is refused with 400 before it is parsed; the design names no limit.
- **Reference capacity.** A valid reference longer than the 50-byte physical capacity (a crew, participant or asset
  member, the commander, or an actor header) is refused as 422 `DOMAIN_VALIDATION_FAILED` with the XML error body and a
  message that the reference exceeds the storage capacity; nothing is stored or truncated and the clock is untouched.
  The check counts UTF-8 bytes, never characters (the columns are `VARCHAR2(50 BYTE)`), and earlier versions of this
  slice answered 500 `INTERNAL_ERROR` (D027 oversized reference extension, 2026-10-15).
- **Test count.** The service gate discovers 33 tests, 8 read and 25 write, from files that define every test
  unconditionally, and the harness fails on any skip or incomplete run. The write slice's checkpoint log notes one run that counted 32 and
  two that counted 33; the cause was not recorded. A run on 2026-10-15 right after restarting the Oracle container,
  the same situation as that run, counted 33, so the count does not depend on a cold start. The most likely explanation is that
  the suite gained its last test between those runs; that is an inference, not an observation.
- **Open contract questions, left as decided.** An unknown path stays a bodyless 404, and the service sends
  `application/xml;charset=UTF-8` without the space the design shows.

## Packaging and deployment

The service ships as one image built from the committed [Dockerfile](Dockerfile) and started by the committed
[compose.yaml](compose.yaml). The build is two stages, both bases pinned by digest: Maven 3.9.11 on JDK 17 runs
`mvn verify` (the Java unit tests) and a JRE 17 stage carries only the jar and its libraries. The
[.dockerignore](.dockerignore) lets the build context hold nothing but `pom.xml`, the 1.1 schema, `fixtures/valid`
and `src`. The container runs as the non-root `10001:10001` and listens on 8083 (`MISSIONS_PORT`, with
`MISSIONS_BIND_HOST=0.0.0.0` inside the container). Compose limits the container to 768 MiB (`mem_limit: 768m`) and caps
the Java heap at 60 percent of it, about 460 MiB, with `JAVA_TOOL_OPTIONS=-XX:MaxRAMPercentage=60.0`.

Compose starts only the service. It never starts, removes or recreates Oracle, which the
[operator script](datasets/missions_operator.py) keeps owning: the service joins the existing internal network
`starfleet-missions-data-20261009` as an external network, and an ordinary bridge of its own carries the
publication, which is `127.0.0.1:8083` on the host only. The container is named `starfleet-missions-service`, the
name the reset guard looks for. The credentials come from the environment alone, with no default and no committed
value: compose fails before it starts anything when `MISSIONS_JDBC_URL`, `MISSIONS_DB_USER` or
`MISSIONS_DB_PASSWORD` is missing or empty, and `MISSIONS_DB_SCHEMA` defaults to `MISSIONS_LAB` as the service does.
The login and its [grants](#write-service-slice) are an explicit operator step. From the repository root, in Git Bash:

```sh
export MISSIONS_JDBC_URL='jdbc:oracle:thin:@//starfleet-missions-data-20261009:1521/XEPDB1'
export MISSIONS_DB_USER='<service login>'
export MISSIONS_DB_PASSWORD='<its password>'
docker compose -f uss-enterprise/missions/compose.yaml up --detach --build
docker compose -f uss-enterprise/missions/compose.yaml down
```

`MISSIONS_IMAGE`, `MISSIONS_CONTAINER_NAME` and `MISSIONS_HOST_PORT` rename the image and container and move the
host port; they exist so the gate can run beside a real deployment and are not needed otherwise. Reset requires the
service stopped, which `down` does.

[Packaging acceptance](validation/runtime/packaging/test_packaging.py) runs through compose against the reviewed Oracle
container, with a disposable schema, a read-only login, a unique image tag, project and container name and an
ephemeral loopback port, all removed at the end. It checks that both bases are pinned by digest and that the service
gates build from this same Dockerfile; that `docker compose config` is valid, joins the Oracle network as an external
network, publishes only on loopback and fails closed without each credential; that the image builds from the committed
files and runs as UID 10001; that compose starts the service on the Oracle network, `GET /missions` answers with the
31 missions of release 1.0, and taking the project down leaves Oracle and its network as they were; and that an invalid
`MISSIONS_PORT`, `MISSIONS_BIND_HOST` or `MISSIONS_DB_SCHEMA` makes the container exit non-zero with the message of
`Config`. The API matrix stays in the service gates. Run it with
`python -B uss-enterprise/missions/validation/missions_runtime.py packaging`.

Not supplied: a registry or image publication, orchestration beyond compose, Mission Control publication and a
deployment of the login itself.

## Release 1.2: the participants reclassified

`datasets/releases/1.2` appends to release 1.1 (the same 300 missions, every missionId and changeId kept) and applies the lead developer's definitions of the reference classes: P is on-board non-crew Personnel and names a civilian of `personnel-v2-large-004` by exact display name, O is an outsider and never maps, C is crew and never a participant. 108 missions get corrected `participantIds` and one appended UPDATED correction entry each (973 change entries in all, eighteen pages become twenty); `participants.json` lists each reference with its class and name and `civilians.json` archives the roster names the P references are checked against. The [Missions design](../../docs/MISSIONS-V1-DESIGN.md#release-12-the-participants-reclassified-2026-10-19) and [D045](../../project-governance/DECISIONS.md#d045---missions-dataset-release-12-participants-reclassified-as-p-and-o-2026-10-19-accepted-scope) hold the rules. The Missions service, the federation stack and the mapping release still use releases 1.0 and 1.1.
