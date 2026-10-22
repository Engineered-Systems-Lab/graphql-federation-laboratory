# Personnel v2 SOAP service

Standalone Java 17 / Apache CXF 4.2.3, Maven WSDL-first, no Spring. See the [specification](../../docs/PERSONNEL-V2.md) and [validation evidence](../../docs/PERSONNEL-V2-VALIDATION.md). V1 remains under ../crew-personnel with its frozen contracts and deployment unchanged.

From the repository root with JAVA_HOME pointing to JDK 17:

```sh
mvn -B -ntp -f uss-enterprise/personnel-v2/pom.xml clean verify
java -jar uss-enterprise/personnel-v2/target/personnel-v2-2.0.0.jar
docker compose -f uss-enterprise/personnel-v2/compose.yaml up --build
```

Default URL: `http://127.0.0.1:8082/soap/personnel-v2?wsdl`. Environment: PERSONNEL_DATASET_VERSION (personnel-v2-small-002 default, or personnel-v2-small-001, personnel-v2-small-003 or the large personnel-v2-large-004), PERSONNEL_FAILURE_PROFILE (normal/slow/unavailable), PERSONNEL_PORT (8082), PERSONNEL_BIND_HOST (127.0.0.1, or container 0.0.0.0). Compose publishes host loopback only. The Dockerfile retains v1's pinned Java 17 build/runtime images. Dataset selection is startup-only and accepts registered hashes only.

GetPersonnelMember accepts personnelId; ListPersonnelMembers accepts optional department/dutyStatus/offset/limit. The common result contains exactly one crewDetails/civilianDetails branch. Civilian department filters do not match; omitted department includes both branches. Clients restart pagination on datasetVersion change. Faults, enums and exact ordering are in contracts/personnel-v2.xsd and the specification.

All three snapshots are exact immutable bytes pinned in Dataset.java and preserved by .gitattributes. The same Wesley PRS-0714 is civilian in 001 and crew in 002. Snapshot 003 keeps the seven records of 002 and adds seven people migrated from the v1 release by federation/personnel-mapping (see the specification). Snapshot 004 (1,000 people: the 14 of 003, the other 787 people of the v1 release and 199 civilians) is a package of ten pages of the same contract plus a manifest under datasets/personnel-v2-large-004/, with every page pinned in Dataset.java. Generated Java, jars, logs and target/ are not source artifacts. HTTP tests start and stop their own loopback servers, validate responses/faults against XSD and exercise self-contained malformed/DTD/entity/SOAP-version probes.
