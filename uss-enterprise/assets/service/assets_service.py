"""The Assets read service: GET /assets/{assetId} and GET /assets, JSON over HTTP, from PostgreSQL.

The web layer is the standard library (http.server with one thread per connection), on purpose: the service is
deliberately plain, the only third-party package is the PostgreSQL driver, and the standard handler lets one
method table answer every method with 405 and Allow: GET, which the contract requires (a framework adds HEAD
and OPTIONS handling that would have to be switched off). Every response is JSON in UTF-8; there is no ETag and
no caching metadata. Binds to loopback by default.

    ASSETS_HOST   address to bind (default 127.0.0.1)
    ASSETS_PORT   port to bind (default 8084; 0 picks a free port)
    PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD   the database login, from the environment only

Run: python assets_service.py [--host H] [--port P]. It prints one line, LISTENING <host>:<port>, once it serves.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
import json
import os
import sys

import assets_logic as logic

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8084
CONTENT_TYPE = 'application/json; charset=utf-8'


class AssetsHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'AssetsService/1.0'
    sys_version = ''
    timeout = 30

    def version_string(self):
        return self.server_version

    def __getattr__(self, name):
        # Every method, known or not, goes to one place, so that every method but GET is a 405 and not the
        # standard library's 501 page.
        if name.startswith('do_'):
            return self.respond
        raise AttributeError(name)

    def respond(self):
        try:
            # The target exactly as sent: the standard library rewrites a leading '//' in self.path.
            words = self.requestline.split()
            result = logic.handle(self.command, words[1] if len(words) > 1 else self.path, self.server.store, self.server.reference)
        except logic.ApiError as error:
            result = logic.Response(error.status, error.body(), error.headers)
        except Exception as error:  # an unclassified failure is a 500; the cause goes to the log, never to the caller
            self.log_error('unexpected failure: %s: %s', type(error).__name__, error)
            failure = logic.internal_error()
            result = logic.Response(failure.status, failure.body(), failure.headers)
        self.send_json(result)

    def send_error(self, code, message=None, explain=None):
        # The standard library calls this for a request it cannot parse; the answer is still the contract's JSON.
        self.log_error('rejected request: %s', code)
        self.close_connection = True
        error = logic.http_error(code)
        self.send_json(logic.Response(error.status, error.body(), error.headers))

    def send_json(self, result):
        body = json.dumps(result.body, ensure_ascii=False).encode('utf-8')
        self.send_response(result.status)
        self.send_header('Content-Type', CONTENT_TYPE)
        self.send_header('Content-Length', str(len(body)))
        for name, value in result.headers.items():
            self.send_header(name, value)
        # A request that carries a body is never read: close the connection so that it cannot be mistaken for the next request.
        headers = self.headers if hasattr(self, 'headers') else {}
        if headers and (headers.get('Content-Length', '0').strip() not in ('', '0') or headers.get('Transfer-Encoding')):
            self.close_connection = True
        if self.close_connection:
            self.send_header('Connection', 'close')
        self.end_headers()
        if getattr(self, 'command', None) != 'HEAD':
            self.wfile.write(body)


class AssetsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, reference):
        super().__init__(address, AssetsHandler)
        self.store = store
        self.reference = reference


def make_server(store, reference, host=DEFAULT_HOST, port=DEFAULT_PORT):
    return AssetsServer((host, port), store, reference)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--host', default=os.environ.get('ASSETS_HOST', DEFAULT_HOST))
    parser.add_argument('--port', type=int, default=int(os.environ.get('ASSETS_PORT', DEFAULT_PORT)))
    args = parser.parse_args(argv)
    from assets_store import PostgresStore
    store = PostgresStore()
    reference = store.reference()
    server = make_server(store, reference, args.host, args.port)
    host, port = server.server_address[:2]
    print(f'LISTENING {host}:{port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
