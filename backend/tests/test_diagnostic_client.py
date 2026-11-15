"""Real loopback HTTP timing with a simulated broker, not live Docker evidence."""

import asyncio
import json

import httpx
import pytest

from app.core.config import Settings
from app.tools.diagnostics import DiagnosticClient, DiagnosticError


def test_client_accepts_a_broker_result_after_the_old_six_second_read_timeout():
    async def exercise():
        observation = {"measurement": "actual", "data": {"fixture": "simulated delayed broker response"}}
        body = json.dumps(observation).encode()

        async def respond(reader, writer):
            try:
                await reader.readuntil(b"\r\n\r\n")
                # A valid broker result may arrive after 6 seconds but before its 7-second deadline.
                await asyncio.sleep(6.25)
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                             + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        async with await asyncio.start_server(respond, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            settings = Settings(_env_file=None, diagnostics_base_url=f"http://127.0.0.1:{port}")
            result = await DiagnosticClient(settings).execute("container_stats", {})
            assert result == observation
    asyncio.run(exercise())


@pytest.mark.parametrize("failure,message", [
    ("timeout", "request timed out"), ("connection", "is unavailable"), ("json", "invalid JSON"),
])
def test_diagnostic_errors_are_distinct_and_do_not_echo_raw_details(settings, failure, message):
    def respond(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private transport detail")
        if failure == "connection":
            raise httpx.ConnectError("private transport detail")
        return httpx.Response(200, content="private transport detail")
    client = DiagnosticClient(settings, transport=httpx.MockTransport(respond))
    with pytest.raises(DiagnosticError, match=message) as error:
        asyncio.run(client.execute("container_stats", {}))
    assert "private transport detail" not in str(error.value)
