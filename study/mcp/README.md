# Study MCP servers

The local MCP servers of the [Abstraction ladder study](../README.md), one per arrangement. Every tool runs on this machine, over MCP streamable HTTP on loopback, and the agents receive no file or shell tools: each agent gets exactly the tools of its server and nothing else. The harness is the MCP client and presents these tools to each model through that vendor's own function calling, so the tool names, descriptions and schemas are the same for every model. The method is in the [agent scenario design](../../docs/PLAN.md#agent-scenario-design).

## Servers and ports

The study reserves the federation-only block 8191 to 8199 for them.

| Port | Server | Scenarios | Tools |
| --- | --- | --- | --- |
| 8191 | `raw_server.py` | Alpha, Beta (Beta adds the written guide in the agent's context, not a tool) | `http_request`, `soap_request`, `read_mapping_release` |
| 8192 | `adapters_server.py` | Gamma | `graphql_query` (the adapter is a parameter) |
| 8193 | `graph_server.py --router-url <Apollo>` | Delta | `graphql_query` |
| 8194 | `graph_server.py --router-url <Cosmo> --port 8194 --name graph-cosmo` | Epsilon | `graphql_query` |

The MCP endpoint of a server is `http://127.0.0.1:<port>/mcp`. `submit_answer` is not a tool of these servers: its schema is per task and belongs to the harness.

## What each tool does

- `http_request(method, url, headers?)`: GET or HEAD to an allowed address. An HTTP error status (404, 500) is returned as a result, as the service said it. A redirect is returned, never followed. Allowed request headers: Accept, Accept-Language, Content-Type, SOAPAction.
- `soap_request(url, envelope, soap_action?)`: POST of a SOAP 1.1 envelope as `text/xml` to an allowed address.
- `read_mapping_release(release, file?)`: the mapping release files (`<release>/<file>.json` under `--mapping-dir`) as raw JSON text. With only the release it lists the files; an unknown release or file is an error that names what exists (release 2.0 does not exist, and release 1.0 has no crew section).
- `graphql_query(service?, query, variables?, operation_name?)`: one POST to the adapter or router (`service` exists on the adapters server only). Introspection is forwarded to the real adapter or router as it is; the server keeps no schema of its own. On the adapters server the federation plumbing is hidden from discovery (the Query fields `_entities` and `_service`, the types `_Entity`, `_Service`, `_Any`, `federation__*` and `link__*`, and the federation directives are removed from introspection answers) and blocked from execution (a query or variable that names them is refused). The guard is lexical and conservative: it looks at the whole query text, comments and strings included.

Every response is JSON text: `{"status", "contentType", "truncated", "body"}`. The text is cut at `--max-chars` (200,000 by default, the same for every scenario) and `truncated` says so. A refused call, an unreachable service (a stopped service is reported as not answering, never hidden) and an unknown release are tool errors (`isError`) with a message the model can read.

## The sandbox

- The HTTP tools reach only the base addresses given with `--allow` (the raw server defaults to the Personnel, Missions and Assets services on 127.0.0.1:8082, 8083 and 8084) and the GraphQL tools only the adapter or router addresses they were started with. A URL is checked for scheme, host, port and a path under the base path; a user name, a fragment, a backslash, an encoded dot or slash, a dot segment and a double slash are refused.
- The raw server cannot reach the adapters or the routers, and the other servers cannot reach the legacy services.
- Nothing reads or writes a file for an agent except `read_mapping_release`, which serves `.json` files directly under the release folders of one configured folder.
- Nothing in the code or the configuration derives a location from the lab checkout's path or name: `--mapping-dir` has no default, and the addresses are configuration.

## Reaching the legacy services

The compose file of the stack publishes the three legacy backends nowhere. [legacy-ports.json](legacy-ports.json) is a compose override (compose reads JSON as YAML) that publishes them on loopback only, at the ports their own scripts default to. After `federation/stack/start.sh start`, apply it to the three services (from Git Bash, with the variables `start.sh` uses set in the same shell: `SUPERGRAPH_FILE`, `EXECUTION_CONFIG_FILE` and the two `STACK_ASSETS_DB_*_PASSWORD` values of the run):

```sh
docker compose -f federation/stack/compose.yaml -f study/mcp/legacy-ports.json up -d --no-deps personnel-service missions-stub assets-service
```

The override recreates those three containers; the assets database is not touched. Nothing else of the stack changes, and the benchmark stack keeps its backends unpublished when the override is not applied.

## Routers and introspection

The Apollo router answers every introspection query with `INTROSPECTION_DISABLED` as configured on 2026-10-20 (`federation/routers/apollo/router.yaml` has no setting that enables it), so Delta cannot discover the graph until `supergraph.introspection: true` is set in that file. The Cosmo router answers introspection by default, on the path `/graphql`, while the Apollo router answers on `/`. Both facts were checked on 2026-10-20 against a scratch Apollo router with introspection enabled and the stack's Cosmo router. The lead developer ruled that enabling it in the router configuration is a governed change of its own; these servers forward introspection and never answer it themselves. The router URL of a graph server is `--router-url`.

## Running

The servers use the pinned `mcp` package ([requirements.txt](requirements.txt); [requirements-lock.txt](requirements-lock.txt) is the full set the tests ran with on Python 3.14). Install it into a virtual environment outside the repository, then from this folder:

```sh
python -B raw_server.py --mapping-dir <folder that holds the release folders 1.0 to 1.3>
python -B adapters_server.py
python -B graph_server.py --router-url http://127.0.0.1:8170/
python -B graph_server.py --router-url http://127.0.0.1:8171/graphql --port 8194 --name graph-cosmo
```

Every server also takes `--host`, `--port`, `--timeout` (seconds for one request, 20 by default), `--max-chars` and `--log`.

## The call log

Every tool call, the refused and the failed ones included, appends one JSON line to the log file of the server process: `--log`, else `LAB_RESULTS_DIR/mcp-calls/<name>-<UTC time>.jsonl` (`LAB_RESULTS_DIR` defaults to the folder `lab-results` in the user's home). The harness owns how a run uses it: start a server with its own `--log` per run, or send the HTTP header `X-Study-Run-Id` on every MCP request of a run and the server copies it into `run_id`.

| Field | Meaning |
| --- | --- |
| `ts` | UTC time the call finished, ISO 8601 with milliseconds |
| `server` | `raw`, `adapters`, or the `--name` of a graph server |
| `tool` | the tool name |
| `run_id` | the `X-Study-Run-Id` header, else null |
| `args` | the arguments the agent sent |
| `outcome` | `ok`, `refused` (the sandbox said no) or `error` (the service did not answer, unknown release or file) |
| `http_status` | the service's HTTP status, else null |
| `response_chars` | length of the text returned to the agent |
| `truncated` | whether it was cut at `--max-chars` |
| `duration_ms` | time the server spent on the call |
| `error` | the message of a refusal or error, else null |

The log holds no credential: the servers hold and take none.

## Tests

- `test_mcp_offline.py` needs no stack: a loopback HTTP server stands in for a service. It covers the allow-list (inside, outside and every evasion), the plumbing guard and scrub, the mapping files, the tool lists, truncation, the honest error for an unreachable service and the log.
- `test_mcp_stack.py` needs the running large-data stack and is skipped unless `STUDY_MCP_STACK=1`; it also needs `STUDY_MCP_MAPPING_DIR` and the override above. It covers the three legacy services (REST/JSON, REST/XML, SOAP), the mapping release files and the unknown release, the allow-list refusing the adapters and the routers, each adapter's ordinary queries and discovery without the plumbing, and the graph through each router (`STUDY_MCP_COSMO_URL` adds Cosmo, `STUDY_MCP_ROUTER_URL` overrides the Apollo URL). It reports, and does not assume, whether a router answers introspection.

```sh
python -B -m unittest test_mcp_offline test_mcp_stack
```

The files here are Python, JSON, Markdown and text only.
