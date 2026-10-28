"""Guided Direct Access (internal identifier Beta): the same raw tools as Direct Access (the raw MCP server on port 8191). The written guide
is context for an agent and adds no tool, so the scripted solution of every task is Direct Access's, over the same raw access layer."""
from direct_access import RawAccess


class GuidedRawAccess(RawAccess):
    arm = 'beta'


ARM = 'beta'
NAME = 'Guided Direct Access'
ACCESS = GuidedRawAccess
MCP_URL = 'http://127.0.0.1:8191/mcp'
TOOLS = ('http_request', 'soap_request', 'read_mapping_release')
