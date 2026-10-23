"""The ADAPTERS MCP server: the four adapters as separate GraphQL APIs, no router (scenario Gamma). Port 8192 by default.

One tool, graphql_query, with the adapter named in the call. The federation plumbing (_entities, _service and the internal types and
directives) is refused when a query names it and removed from every answer, so the agent discovers each adapter's ordinary API only.
"""
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

import mcp_core as core

DEFAULT_ADAPTERS = {
    'personnel': 'http://127.0.0.1:8182/graphql',
    'missions': 'http://127.0.0.1:8183/graphql',
    'assets': 'http://127.0.0.1:8184/graphql',
    'mapping': 'http://127.0.0.1:8190/graphql',
}


def build(adapters, log, timeout=core.DEFAULT_TIMEOUT_SECONDS, max_chars=core.DEFAULT_MAX_CHARS):
    server = MCPServer('study-adapters', instructions='Four GraphQL adapters over the legacy systems of the USS Enterprise.')
    bases = list(adapters.values())

    @server.tool(description='Run one GraphQL query (introspection included) against one adapter and return its status and JSON body. '
                             'The adapters are personnel, missions, assets and mapping.')
    async def graphql_query(
            service: Annotated[Literal['personnel', 'missions', 'assets', 'mapping'], Field(description='Which adapter to ask.')],
            query: Annotated[str, Field(description='The GraphQL query text.')],
            variables: Annotated[dict | None, Field(description='Optional GraphQL variables.')] = None,
            operation_name: Annotated[str | None, Field(description='Optional operation name when the query holds several.')] = None,
            ctx: Context = None) -> str:
        args = {'service': service, 'query': query, 'variables': variables, 'operation_name': operation_name}

        def work():
            status, text, truncated = core.graphql_post(adapters[service], query, variables, operation_name, bases, timeout,
                                                        max_chars, plumbing_blocked=True)
            return core.result_text(status, 'application/json', text, truncated), status, truncated
        return await core.logged(log, ctx, 'graphql_query', args, work)

    return server


def main():
    parser = core.base_parser(__doc__.splitlines()[0], 8192)
    for name, url in DEFAULT_ADAPTERS.items():
        parser.add_argument(f'--{name}-url', default=url, help=f'the {name} adapter\'s GraphQL URL (default {url})')
    args = parser.parse_args()
    adapters = {name: getattr(args, f'{name}_url') for name in DEFAULT_ADAPTERS}
    log = core.CallLog('adapters', args.log)
    core.serve(build(adapters, log, args.timeout, args.max_chars), args)


if __name__ == '__main__':
    main()
