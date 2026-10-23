"""The GRAPH MCP server: one GraphQL endpoint, the router of the federation (scenarios Delta and Epsilon).

One tool, graphql_query, against the single router address given with --router-url. Port 8193 by default (Apollo router, 8170); start a
second copy on 8194 for the Cosmo router (8171). Introspection and queries are forwarded to the router unchanged.
"""
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

import mcp_core as core


def build(router_url, log, timeout=core.DEFAULT_TIMEOUT_SECONDS, max_chars=core.DEFAULT_MAX_CHARS):
    server = MCPServer('study-graph', instructions='One GraphQL graph over the legacy systems of the USS Enterprise.')
    bases = [router_url]

    @server.tool(description='Run one GraphQL query (introspection included) against the graph and return its status and JSON body.')
    async def graphql_query(
            query: Annotated[str, Field(description='The GraphQL query text.')],
            variables: Annotated[dict | None, Field(description='Optional GraphQL variables.')] = None,
            operation_name: Annotated[str | None, Field(description='Optional operation name when the query holds several.')] = None,
            ctx: Context = None) -> str:
        args = {'query': query, 'variables': variables, 'operation_name': operation_name}

        def work():
            status, text, truncated = core.graphql_post(router_url, query, variables, operation_name, bases, timeout, max_chars,
                                                        plumbing_blocked=False)
            return core.result_text(status, 'application/json', text, truncated), status, truncated
        return await core.logged(log, ctx, 'graphql_query', args, work)

    return server


def main():
    parser = core.base_parser(__doc__.splitlines()[0], 8193)
    parser.add_argument('--router-url', default='http://127.0.0.1:8170/', help='the router\'s GraphQL URL (default: the Apollo router)')
    parser.add_argument('--name', default='graph', help='the name in the call log (for example graph-apollo, graph-cosmo)')
    args = parser.parse_args()
    log = core.CallLog(args.name, args.log)
    core.serve(build(args.router_url, log, args.timeout, args.max_chars), args)


if __name__ == '__main__':
    main()
