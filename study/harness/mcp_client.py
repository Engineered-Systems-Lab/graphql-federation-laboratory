"""The harness as an MCP client of a scenario's local MCP server.

One session per agent run, so the server's call log can be matched to the run through the HTTP header `X-Study-Run-Id`. The session keeps one
event loop in a background thread and offers a synchronous interface, which keeps the agent loop plain. One long-lived task in that loop owns
the connection from its opening to its closing (the transport's cancel scopes must be entered and left by the same task) and serves the
requests the calling thread puts in a queue. The `mcp` package is imported only when a real session is opened (tests use `FakeToolSession`).
The session offers no file or shell tool: it presents exactly the tools its server lists, as neutral tool descriptions
(name, description, input_schema).
"""
import asyncio
import concurrent.futures
import threading

RUN_ID_HEADER = 'X-Study-Run-Id'


class ToolSession:
    """The interface the agent loop needs. `tools()` lists neutral tools; `call(name, arguments)` returns (text, is_error)."""

    def tools(self):
        raise NotImplementedError

    def call(self, name, arguments):
        raise NotImplementedError

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class McpSession(ToolSession):
    def __init__(self, url, run_id, call_timeout=120.0, open_timeout=30.0):
        self.url, self.run_id, self.call_timeout = url, run_id, call_timeout
        self._tools = None
        self._opened = concurrent.futures.Future()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._queue = None
        self._done = asyncio.run_coroutine_threadsafe(self._serve(), self._loop)
        try:
            self._opened.result(timeout=open_timeout)
        except BaseException:
            self._shutdown_loop()
            raise

    async def _serve(self):
        self._queue = asyncio.Queue()
        try:
            from mcp import Client
            from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
            http = create_mcp_http_client(headers={RUN_ID_HEADER: self.run_id})
            async with http:
                async with Client(streamable_http_client(self.url, http_client=http), read_timeout_seconds=self.call_timeout) as client:
                    self._opened.set_result(True)
                    while True:
                        item = await self._queue.get()
                        if item is None:
                            return
                        action, future = item
                        try:
                            future.set_result(await action(client))
                        except BaseException as error:  # handed to the calling thread
                            future.set_exception(error)
        except BaseException as error:
            if not self._opened.done():
                self._opened.set_exception(error)
            else:
                raise

    def _ask(self, action):
        future = concurrent.futures.Future()
        self._loop.call_soon_threadsafe(self._queue.put_nowait, (action, future))
        return future.result()

    def tools(self):
        if self._tools is None:
            async def list_tools(client):
                return (await client.list_tools()).tools
            self._tools = [{'name': t.name, 'description': t.description or '', 'input_schema': t.input_schema} for t in self._ask(list_tools)]
        return list(self._tools)

    def call(self, name, arguments):
        async def call_tool(client):
            return await client.call_tool(name, arguments)
        result = self._ask(call_tool)
        text = '\n'.join(part.text for part in result.content if getattr(part, 'text', None) is not None)
        return text, bool(result.is_error)

    def close(self):
        if self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, None)
            self._done.result(timeout=15)
        finally:
            self._shutdown_loop()

    def _shutdown_loop(self):
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)
        if not self._loop.is_running():
            self._loop.close()


class FakeToolSession(ToolSession):
    """A scripted session for tests: `handlers` maps a tool name to a function of the arguments returning text or (text, is_error)."""

    def __init__(self, tool_list, handlers):
        self._tools, self.handlers, self.calls = tool_list, handlers, []

    def tools(self):
        return list(self._tools)

    def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name not in self.handlers:
            return 'Unknown tool ' + name, True
        outcome = self.handlers[name](arguments)
        return outcome if isinstance(outcome, tuple) else (outcome, False)
