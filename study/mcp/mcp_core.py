"""Shared parts of the three local MCP servers of the Abstraction ladder study.

Only this module touches the network on behalf of an agent, and only through `fetch`, which refuses every address outside the allow-list
it is given. Nothing here reads a file on an agent's behalf except `MappingFiles`, which serves the mapping release files of one
configured folder. There is no file or shell tool anywhere in these servers.

Python standard library plus the pinned `mcp` package (requirements.txt).
"""
import argparse
import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_CHARS = 200_000
ALLOWED_REQUEST_HEADERS = ('accept', 'accept-language', 'content-type', 'soapaction')
RUN_ID_HEADER = 'x-study-run-id'


# ---------------------------------------------------------------------------------------------------------------- the call log

def results_root():
    """The machine-local folder of raw run results: the setting LAB_RESULTS_DIR."""
    return Path(os.environ.get('LAB_RESULTS_DIR') or Path.home() / 'lab-results')


class CallLog:
    """One JSON object per line, appended for every tool call, the call that was refused or failed included.

    Fields: ts (UTC, ISO 8601), server, tool, run_id (the value of the HTTP header X-Study-Run-Id when the client sent one, else null),
    args (what the agent sent), outcome (ok, refused or error), http_status (or null), response_chars, truncated, duration_ms, error.
    The log never holds a credential: the servers hold none and take none.
    """

    def __init__(self, server, path=None):
        self.server = server
        if path is None:
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            path = results_root() / 'mcp-calls' / f'{server}-{stamp}.jsonl'
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, tool, args, run_id, outcome, started, http_status=None, response_chars=0, truncated=False, error=None):
        record = {
            'ts': datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            'server': self.server, 'tool': tool, 'run_id': run_id, 'args': args, 'outcome': outcome,
            'http_status': http_status, 'response_chars': response_chars, 'truncated': truncated,
            'duration_ms': round((time.monotonic() - started) * 1000, 1), 'error': error,
        }
        with open(self.path, 'a', encoding='utf-8', newline='\n') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')


class Refused(ToolError):
    """The call was refused by the sandbox (an address outside the allow-list, a blocked name, a bad argument)."""


# ----------------------------------------------------------------------------------------------------------------- the allow-list

def url_allowed(url, bases):
    """True when `url` is inside one of the base URLs: same scheme, host and port, and a path under the base path.

    Refused outright: a user name or password, a fragment, a backslash, an encoded dot or slash, a dot segment, an empty segment.
    """
    try:
        parts = urllib.parse.urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != 'http' or not parts.hostname or parts.username is not None or parts.password is not None or parts.fragment:
        return False
    if '\\' in parts.path or re.search(r'%(2e|2f|5c)', parts.path, re.IGNORECASE):
        return False
    segments = parts.path.split('/')[1:]
    if any(segment in ('.', '..') for segment in segments) or '//' in parts.path:
        return False
    for base in bases:
        b = urllib.parse.urlsplit(base)
        if (b.scheme, b.hostname, b.port or 80) != (parts.scheme, parts.hostname, port or 80):
            continue
        base_path = b.path.rstrip('/')
        if parts.path == base_path or parts.path.startswith(base_path + '/') or (base_path == '' and parts.path == ''):
            return True
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def clean_headers(headers):
    out = {}
    for name, value in (headers or {}).items():
        if name.lower() not in ALLOWED_REQUEST_HEADERS:
            raise Refused(f'The header {name!r} is not allowed. Allowed: {", ".join(ALLOWED_REQUEST_HEADERS)}.')
        out[name] = str(value)
    return out


def fetch(method, url, headers, body, bases, timeout, max_chars):
    """One request to an allowed address. Returns (status, content_type, text, truncated). Never follows a redirect.

    An HTTP error status is a result, not a failure: the agent sees what the service said. Only a refusal by the allow-list or an
    unreachable service raises (a stopped service is reported as such, never hidden).
    """
    if not url_allowed(url, bases):
        raise Refused('Address refused: only these base addresses are reachable: ' + ', '.join(bases))
    data = body.encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with _OPENER.open(request, timeout=timeout) as response:
            status, content_type, raw = response.status, response.headers.get('Content-Type'), response.read()
    except urllib.error.HTTPError as error:
        with error:
            status, content_type, raw = error.code, error.headers.get('Content-Type'), error.read()
    except (urllib.error.URLError, OSError, TimeoutError) as error:
        reason = getattr(error, 'reason', error)
        raise ToolError(f'The service did not answer: {type(reason).__name__}: {reason}') from error
    text = raw.decode('utf-8', errors='replace')
    truncated = len(text) > max_chars
    return status, content_type, text[:max_chars], truncated


# ------------------------------------------------------------------------------------------------ the federation plumbing (Gamma)

_BLOCKED_NAME = re.compile(r'(?<![_0-9A-Za-z])(_entities|_service|_Entity|_Service|_Any|federation__[_0-9A-Za-z]*|link__[_0-9A-Za-z]*)(?![_0-9A-Za-z])')
_UNICODE_ESCAPE = re.compile(r'\\u([0-9a-fA-F]{4})')
BLOCKED_FIELDS = {'_entities', '_service'}
BLOCKED_TYPES = {'_Entity', '_Service', '_Any', 'federation__FieldSet', 'link__Import', 'link__Purpose'}
BLOCKED_DIRECTIVES = {'federation__extends', 'federation__override', 'federation__provides', 'federation__shareable',
                      'external', 'inaccessible', 'key', 'link', 'requires', 'tag'}


def mentions_plumbing(query, variables):
    """True when the query text (comments and strings included, unicode escapes decoded) or a variable value names the plumbing."""
    texts = [_UNICODE_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), query or '')]

    def walk(value):
        if isinstance(value, str):
            texts.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                texts.append(str(key))
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(variables)
    return any(_BLOCKED_NAME.search(text) for text in texts)


def scrub_plumbing(value):
    """Remove the federation plumbing from an introspection answer: the two Query fields, the internal types and the directives."""
    if isinstance(value, list):
        return [scrub_plumbing(item) for item in value
                if not (isinstance(item, dict) and isinstance(item.get('name'), str)
                        and (item['name'] in BLOCKED_FIELDS or item['name'] in BLOCKED_TYPES or item['name'] in BLOCKED_DIRECTIVES
                             or item['name'].startswith(('federation__', 'link__'))))]
    if isinstance(value, dict):
        return {key: scrub_plumbing(item) for key, item in value.items()}
    return value


def graphql_post(url, query, variables, operation_name, bases, timeout, max_chars, plumbing_blocked):
    """One GraphQL POST to an allowed address. Returns (status, text, truncated)."""
    if plumbing_blocked and mentions_plumbing(query, variables):
        raise Refused('Refused: the federation plumbing (_entities, _service and the types and directives that belong to it) '
                      'is not part of this API.')
    payload = {'query': query}
    if variables is not None:
        payload['variables'] = variables
    if operation_name:
        payload['operationName'] = operation_name
    status, _, text, truncated = fetch('POST', url, {'Content-Type': 'application/json', 'Accept': 'application/json'},
                                       json.dumps(payload), bases, timeout, 10 ** 12)
    if plumbing_blocked and re.search(r'__schema|__type', query):
        try:
            text = json.dumps(scrub_plumbing(json.loads(text)), ensure_ascii=False)
        except ValueError:
            pass
    truncated = len(text) > max_chars
    return status, text[:max_chars], truncated


# --------------------------------------------------------------------------------------------------------- the mapping release files

class MappingFiles:
    """Read access to the mapping release files, as raw data, from one configured folder (releases/<release>/<file>)."""

    RELEASE = re.compile(r'[0-9]+\.[0-9]+')
    FILE = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]*\.json')

    def __init__(self, folder):
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise SystemExit(f'The mapping release folder does not exist: {folder}')

    def releases(self):
        return sorted(p.name for p in self.folder.iterdir() if p.is_dir() and self.RELEASE.fullmatch(p.name))

    def read(self, release, name, max_chars):
        if not self.RELEASE.fullmatch(release or '') or release not in self.releases():
            raise ToolError(f'There is no mapping release {release!r}. Releases present: {", ".join(self.releases()) or "none"}.')
        files = sorted(p.name for p in (self.folder / release).iterdir() if p.is_file() and self.FILE.fullmatch(p.name))
        if name is None:
            return json.dumps({'release': release, 'files': files}), False
        if name not in files:
            raise ToolError(f'Release {release} has no file {name!r}. Files present: {", ".join(files)}.')
        text = (self.folder / release / name).read_text(encoding='utf-8')
        return text[:max_chars], len(text) > max_chars


# ------------------------------------------------------------------------------------------------------------------ the tool wrapper

def run_id_of(ctx):
    try:
        headers = ctx.headers
        return headers.get(RUN_ID_HEADER) if headers else None
    except Exception:
        return None


async def logged(log, ctx, tool, args, work):
    """Run `work()` (blocking) in a thread, log the call with its timing, return its text. `work` returns (text, status, truncated)."""
    started = time.monotonic()
    run_id = run_id_of(ctx)
    try:
        text, status, truncated = await asyncio.to_thread(work)
    except Refused as error:
        log.write(tool, args, run_id, 'refused', started, error=str(error))
        raise
    except ToolError as error:
        log.write(tool, args, run_id, 'error', started, error=str(error))
        raise
    log.write(tool, args, run_id, 'ok', started, http_status=status, response_chars=len(text), truncated=truncated)
    return text


def result_text(status, content_type, body, truncated):
    return json.dumps({'status': status, 'contentType': content_type, 'truncated': truncated, 'body': body}, ensure_ascii=False)


def base_parser(description, port):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=port)
    parser.add_argument('--log', default=None, help='the call log file (default: LAB_RESULTS_DIR/mcp-calls/<server>-<time>.jsonl)')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT_SECONDS, help='seconds to wait for one request')
    parser.add_argument('--max-chars', type=int, default=DEFAULT_MAX_CHARS, help='longest response text returned to the agent')
    return parser


def serve(server, args):
    server.run('streamable-http', host=args.host, port=args.port, stateless_http=True, json_response=True)
