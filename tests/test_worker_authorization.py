import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from proxy.config import proxy_config
from proxy.raw_websocket import RawWebSocket
from proxy.pool import _CfWorkerPool
from proxy import bridge

KEY = 'example-test-key-not-a-real-secret'


class WorkerAuthorizationTest(unittest.IsolatedAsyncioTestCase):
    async def test_header_is_sent_without_putting_key_in_url(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'HTTP/1.1 101 Switching Protocols\r\n\r\n')
        writer = Mock(drain=AsyncMock())
        with patch('proxy.raw_websocket.asyncio.open_connection', AsyncMock(return_value=(reader, writer))), patch('proxy.raw_websocket.set_sock_opts'):
            await RawWebSocket.connect('bridge.example', 'bridge.example', path='/apiws?dc=2', bearer_token=KEY)
        request = writer.write.call_args.args[0]
        self.assertIn(('Authorization: Bearer ' + KEY + '\r\n').encode(), request)
        self.assertNotIn(KEY.encode(), request.split(b'\r\n', 1)[0])

    async def test_invalid_keys_are_rejected_before_dialing(self):
        for key in ('a\r\nInjected: value', 'short', 'a' * 129, 'ключ' * 8):
            with self.subTest(key=repr(key)), patch('proxy.raw_websocket.asyncio.open_connection', AsyncMock()) as connect:
                with self.assertRaises(ValueError):
                    await RawWebSocket.connect('bridge.example', 'bridge.example', bearer_token=key)
                connect.assert_not_called()

    async def test_key_is_not_sent_over_plaintext_http(self):
        with patch('proxy.raw_websocket.asyncio.open_connection', AsyncMock()) as connect:
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                await RawWebSocket.connect('bridge.example', 'bridge.example', secure=False, bearer_token=KEY)
            connect.assert_not_called()

    async def test_warm_worker_connections_carry_the_key(self):
        with patch.object(proxy_config, 'cfproxy_worker_token', KEY), patch('proxy.pool.RawWebSocket.connect', AsyncMock()) as connect:
            await _CfWorkerPool()._connect_one(['bridge.example'], '149.154.167.51', 2)
        self.assertEqual(KEY, connect.call_args.kwargs['bearer_token'])

    async def test_cold_worker_connections_carry_the_key(self):
        ws = Mock(send=AsyncMock())
        with patch.object(proxy_config, 'cfproxy_worker_token', KEY), patch.object(proxy_config, 'cfproxy_worker_domains', ['bridge.example']), patch.object(bridge.cf_worker_pool, 'get', AsyncMock(return_value=None)), patch.object(bridge.RawWebSocket, 'connect', AsyncMock(return_value=ws)) as connect, patch.object(bridge, 'bridge_ws_reencrypt', AsyncMock()):
            ok = await bridge._cfproxy_worker_fallback(None, None, b'init', 'test', None, 2, False, False, '149.154.167.51')
        self.assertTrue(ok)
        self.assertEqual(KEY, connect.call_args.kwargs['bearer_token'])
