"""Network handover regression tests for the Android session supervisor."""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'android/app/src/main/python'))
from android_runtime import supervise


class HandoverTest(unittest.IsolatedAsyncioTestCase):
    async def test_handover_closes_old_clients_rebinds_and_preserves_port(self):
        stop = asyncio.Event()
        state = {'revision': 0, 'server': None, 'starts': 0, 'ready': 0, 'port': 0}
        writers = set()

        def client(reader, writer):
            writers.add(writer)

        async def core(session_stop):
            server = await asyncio.start_server(client, '127.0.0.1', state['port'])
            state['server'] = server
            state['port'] = server.sockets[0].getsockname()[1]
            state['starts'] += 1
            try:
                await session_stop.wait()
            finally:
                server.close()
                for writer in list(writers):
                    writer.close()
                    await writer.wait_closed()
                writers.clear()
                await server.wait_closed()
                state['server'] = None

        def ready():
            state['ready'] += 1

        task = asyncio.create_task(supervise(
            core, stop, lambda: state['revision'],
            lambda: state['server'] is not None, ready, lambda: None,
            lambda: None, interval=.005))

        async def wait_for(predicate):
            async def wait():
                while not predicate():
                    await asyncio.sleep(.005)
            await asyncio.wait_for(wait(), 2)

        try:
            await wait_for(lambda: state['ready'] == 1)
            reader, writer = await asyncio.open_connection('127.0.0.1', state['port'])
            port = state['port']
            # Simulate Wi-Fi -> cellular, including an event burst.
            state['revision'] += 3
            await wait_for(lambda: state['ready'] == 2)
            self.assertEqual(port, state['port'])
            self.assertEqual(b'', await asyncio.wait_for(reader.read(), 1))
            writer.close()
            await writer.wait_closed()
            fresh_reader, fresh_writer = await asyncio.open_connection('127.0.0.1', port)
            stop.set()
            await asyncio.wait_for(task, 2)
            self.assertEqual(b'', await asyncio.wait_for(fresh_reader.read(), 1))
            fresh_writer.close()
            await fresh_writer.wait_closed()
            self.assertEqual(2, state['starts'])
        finally:
            stop.set()
            await asyncio.gather(task, return_exceptions=True)

    async def test_stop_during_network_recovery_does_not_start_again(self):
        stop = asyncio.Event()
        revision = [0]
        entered = asyncio.Event()
        cleanup = asyncio.Event()
        starts = []

        async def core(session_stop):
            starts.append(True)
            entered.set()
            try:
                await session_stop.wait()
                await cleanup.wait()
            finally:
                cleanup.set()

        task = asyncio.create_task(supervise(
            core, stop, lambda: revision[0], lambda: True,
            lambda: None, lambda: None, lambda: None, interval=.005))
        await entered.wait()
        revision[0] += 1
        await asyncio.sleep(.02)
        stop.set()
        cleanup.set()
        await asyncio.wait_for(task, 1)
        self.assertEqual(1, len(starts))

    async def test_stuck_old_session_is_cancelled_before_new_session(self):
        stop = asyncio.Event()
        revision = [0]
        old_cancelled = asyncio.Event()
        starts = []

        async def core(session_stop):
            starts.append(True)
            if len(starts) == 1:
                try:
                    await asyncio.Future()
                finally:
                    old_cancelled.set()
            else:
                self.assertTrue(old_cancelled.is_set())
                stop.set()
                await session_stop.wait()

        def first_ready():
            revision[0] += 1

        await asyncio.wait_for(supervise(
            core, stop, lambda: revision[0], lambda: True,
            first_ready, lambda: None, lambda: None,
            interval=.005, shutdown_timeout=.03), 1)
        self.assertEqual(2, len(starts))

    async def test_core_failure_is_reported(self):
        async def broken(session_stop):
            raise OSError('listener failed')

        with self.assertRaisesRegex(OSError, 'listener failed'):
            await supervise(broken, asyncio.Event(), lambda: 0, lambda: False,
                            lambda: None, lambda: None, lambda: None, interval=.005)
