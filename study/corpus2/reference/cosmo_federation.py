"""Cosmo Federation (internal identifier Epsilon): the same supergraph through the Cosmo router, by `graphql_query` on the second graph
MCP server (port 8194). The access layer is graph_access.FederationAccess, the same queries as Apollo Federation."""
from graph_access import FederationAccess


class CosmoAccess(FederationAccess):
    arm = 'epsilon'


ARM = 'epsilon'
NAME = 'Cosmo Federation'
ACCESS = CosmoAccess
MCP_URL = 'http://127.0.0.1:8194/mcp'
TOOLS = ('graphql_query',)
