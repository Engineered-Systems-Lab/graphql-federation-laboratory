"""Apollo Federation (internal identifier Delta): the supergraph through the Apollo router, by `graphql_query` on the graph MCP server
(port 8193). The access layer is graph_access.FederationAccess."""
from graph_access import FederationAccess


class ApolloAccess(FederationAccess):
    arm = 'delta'


ARM = 'delta'
NAME = 'Apollo Federation'
ACCESS = ApolloAccess
MCP_URL = 'http://127.0.0.1:8193/mcp'
TOOLS = ('graphql_query',)
