# Service scripts

Three read-only wrappers in `uss-enterprise/scripts/` let the lead developer look at a running service without hand-writing a SOAP envelope or a URL. They are for reading only, in Git Bash, with `curl` on the path; each script's own `--help` is the usage and this page only says what they are for. They are not a frontend: the reading interface of the integrated system will be the federation layer's GraphQL explorer.

| Script | Service | Default address | Commands |
| --- | --- | --- | --- |
| `uss-enterprise/scripts/personnel.sh` | Personnel v2 (SOAP) | `PERSONNEL_URL`, default `http://127.0.0.1:8082/soap/personnel-v2` | `get <personnelId>`, `list [department= dutyStatus= offset= limit=]` |
| `uss-enterprise/scripts/missions.sh` | Missions (REST) | `MISSIONS_URL`, default `http://127.0.0.1:8083` | `get <missionId>`, `changes <missionId>`, `list [filter=value ...]` |
| `uss-enterprise/scripts/assets.sh` | Assets (REST, JSON) | `ASSETS_URL`, default `http://127.0.0.1:8084` | `get <assetId>`, `list [kind= category= status= parentAssetId= offset= limit=]` |

They pretty-print the answer on standard output (XML, or JSON for Assets) and put the HTTP status on standard error, with the ETag when the service sends one (Missions does, Assets does not). `--dry-run` prints the exact request, method, URL, headers and body, and sends nothing. When the service is not running they print one line naming the command that starts it (a compose file, or `bash uss-enterprise/assets/start.sh start` for Assets) and exit 3; a bad command line prints the usage and exits 2; an HTTP error status exits 1 after printing the answer.

The scripts never start, stop or modify a service and never send credentials. The Missions write methods need the audit headers and are not wrapped. The Assets service is read-only, and its two commands are the two reads of contract 1.1 (`uss-enterprise/assets/contracts/assets-v1.1.openapi.json`); a repeated or unknown filter is sent as given and the service answers it 400. The Personnel dataset is chosen when the service starts, so there is no per-request flag. The Personnel request is the one the acceptance test `SoapHttpTest` sends, and `uss-enterprise/scripts/tests/test_service_scripts.py` compares the two. Crew & Personnel v1 is not wrapped.
