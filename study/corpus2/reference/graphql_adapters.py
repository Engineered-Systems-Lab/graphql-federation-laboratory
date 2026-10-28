"""GraphQL Adapters (internal identifier Gamma): the four adapters as separate GraphQL APIs through `graphql_query` on the adapters MCP server
(port 8192), with no router and no `_entities`. The access layer is graph_access.AdaptersAccess."""
from graph_access import AdaptersAccess

ARM = 'gamma'
NAME = 'GraphQL Adapters'
ACCESS = AdaptersAccess
MCP_URL = 'http://127.0.0.1:8192/mcp'
TOOLS = ('graphql_query',)
