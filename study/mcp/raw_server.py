"""The RAW MCP server: the legacy systems as they are (scenarios Alpha and Beta). Port 8191 by default.

Tools: http_request (GET and HEAD), soap_request (POST of a SOAP envelope) and read_mapping_release. The first two reach only the
legacy services' base addresses given as --allow; the third reads the mapping release files as raw data. No file or shell tool.
"""
import json
from typing import Annotated, Literal

from mcp.server.mcpserver import Context, MCPServer
from pydantic import Field

import mcp_core as core

DEFAULT_ALLOW = ('http://127.0.0.1:8082', 'http://127.0.0.1:8083', 'http://127.0.0.1:8084')


def build(allow, mapping_dir, log, timeout=core.DEFAULT_TIMEOUT_SECONDS, max_chars=core.DEFAULT_MAX_CHARS):
    mapping = core.MappingFiles(mapping_dir)
    server = MCPServer('study-raw', instructions='Raw access to the legacy systems of the USS Enterprise.')
    bases = list(allow)

    @server.tool(description='Send one HTTP request (GET or HEAD) to a legacy service and return its status, content type and body. '
                             'Only the legacy services\' own addresses are reachable.')
    async def http_request(
            method: Annotated[Literal['GET', 'HEAD'], Field(description='The HTTP method.')],
            url: Annotated[str, Field(description='The full URL, including the query string.')],
            headers: Annotated[dict[str, str] | None, Field(description='Optional request headers (Accept, Accept-Language, Content-Type, SOAPAction).')] = None,
            ctx: Context = None) -> str:
        args = {'method': method, 'url': url, 'headers': headers}

        def work():
            status, ctype, text, truncated = core.fetch(method, url, core.clean_headers(headers), None, bases, timeout, max_chars)
            return core.result_text(status, ctype, text, truncated), status, truncated
        return await core.logged(log, ctx, 'http_request', args, work)

    @server.tool(description='POST a SOAP 1.1 envelope (text/xml) to a legacy SOAP endpoint and return its status, content type and body. '
                             'Only the legacy services\' own addresses are reachable.')
    async def soap_request(
            url: Annotated[str, Field(description='The full URL of the SOAP endpoint.')],
            envelope: Annotated[str, Field(description='The complete SOAP envelope as XML text.')],
            soap_action: Annotated[str | None, Field(description='The SOAPAction header value, if the operation needs one.')] = None,
            ctx: Context = None) -> str:
        args = {'url': url, 'envelope': envelope, 'soap_action': soap_action}

        def work():
            headers = {'Content-Type': 'text/xml; charset=utf-8', 'Accept': 'text/xml'}
            if soap_action is not None:
                headers['SOAPAction'] = soap_action
            status, ctype, text, truncated = core.fetch('POST', url, headers, envelope, bases, timeout, max_chars)
            return core.result_text(status, ctype, text, truncated), status, truncated
        return await core.logged(log, ctx, 'soap_request', args, work)

    @server.tool(description='Read a mapping release file as raw JSON text. Give only the release to list its files; give the file to read it. '
                            'An unknown release or file is an error.')
    async def read_mapping_release(
            release: Annotated[str, Field(description='The release number, for example 1.2.')],
            file: Annotated[str | None, Field(description='The file name inside the release, for example manifest.json.')] = None,
            ctx: Context = None) -> str:
        args = {'release': release, 'file': file}

        def work():
            text, truncated = mapping.read(release, file, max_chars)
            return json.dumps({'truncated': truncated, 'content': text}, ensure_ascii=False), None, truncated
        return await core.logged(log, ctx, 'read_mapping_release', args, work)

    return server


def main():
    parser = core.base_parser(__doc__.splitlines()[0], 8191)
    parser.add_argument('--allow', action='append', help='a legacy service base URL (repeatable; default: the Personnel, Missions and '
                                                          'Assets services on 127.0.0.1:8082, 8083 and 8084)')
    parser.add_argument('--mapping-dir', required=True, help='the folder that holds the mapping release folders (1.0, 1.1, ...)')
    args = parser.parse_args()
    log = core.CallLog('raw', args.log)
    core.serve(build(args.allow or DEFAULT_ALLOW, args.mapping_dir, log, args.timeout, args.max_chars), args)


if __name__ == '__main__':
    main()
