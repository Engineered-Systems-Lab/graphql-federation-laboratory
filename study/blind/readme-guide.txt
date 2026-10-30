# Your inputs

This folder is everything you get for writing the guide. It holds no task, no answer and no finding of an earlier study.

It was built from the laboratory's commit {commit}. Every file keeps its path in the laboratory. `MANIFEST.json` lists each file with its SHA-256. A link in a document to a file that is not here leads nowhere: that file is not part of your inputs.

You are given only what the study's design names: "the actual study-2 service contracts, the real Missions service included, the tool capabilities, the calculation tool and `ask_requester` included, and general business context. No task-specific hints."

## What is here

- The services' contracts: Personnel v2 (`uss-enterprise/personnel-v2/contracts/`, SOAP), Missions (`uss-enterprise/missions/contracts/`, REST with XML) and Assets (`uss-enterprise/assets/contracts/`, REST with JSON).
- The services' designs (`docs/`) and READMEs (`uss-enterprise/*/README.md`).
- The mapping release files 1.0 to 1.3 (`federation/mapping-releases/`).
- `TOOLS.md`: the tools an agent is given, with their texts as the agent reads them.

## Asking the live services

You cannot reach the services from here. To see how they answer, write the requests you want in a request file, and the lead developer runs them, in rounds, through the agents' own tool code with its limits: the same addresses, headers and size limit, and the same refusals. Nothing is edited, neither your requests nor the answers.

1. Write `relay/round-001.requests.json` (the next round is `round-002`, and so on):

   ```json
   {
     "round": 1,
     "requests": [
       {"id": "first-mission", "tool": "http_request", "arguments": {"method": "GET", "url": "http://127.0.0.1:8083/missions?pageSize=1"}},
       {"tool": "soap_request", "arguments": {"url": "http://127.0.0.1:8082/soap/personnel-v2", "envelope": "<soapenv:Envelope ...>...</soapenv:Envelope>"}},
       {"tool": "read_mapping_release", "arguments": {"release": "1.3"}}
     ]
   }
   ```

   Each request names one of the three tools `http_request`, `soap_request` and `read_mapping_release`, with the arguments that tool takes in `TOOLS.md`. `id` is optional and comes back with the answer.

2. Commit it and tell the lead developer that the round is ready.

3. The answers come back beside it as `relay/round-001.answers.json`: for each request, the tool, the arguments, the text the agent would see and whether the tool reported an error, in your order. A refused or failed request is answered as an agent would see it. The file also gives the round, the time and the dataset's fingerprint. `relay/LEDGER.json` lists every round with the hashes of both files.

A round is run once. A request file that names another tool, or that is not of this shape, is sent back unrun with the reason.
