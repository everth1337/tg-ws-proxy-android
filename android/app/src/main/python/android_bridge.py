"""Android lifecycle adapter. The upstream proxy sources are copied at build time."""
import asyncio
import logging
import sys
import threading
import android_aes

sys.modules['proxy._aes'] = android_aes

from proxy import tg_ws_proxy as core
from proxy.config import proxy_config
from proxy.stats import stats
from proxy.utils import human_bytes, DomainCensorFilter

_lock = threading.Lock()
_loop = None
_stop_event = None
_stop_requested = False

class _LogHandler(logging.Handler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.addFilter(DomainCensorFilter())
        self.setFormatter(logging.Formatter('%(asctime)s  %(levelname)s  %(message)s', '%H:%M:%S'))

    def emit(self, record):
        text = self.format(record)
        if 'Secret:' in text or 'tg://proxy?' in text:
            return
        self.callback.onLog(text)

def stop():
    global _stop_requested
    with _lock:
        _stop_requested = True
        if _loop is not None and _stop_event is not None:
            try:
                _loop.call_soon_threadsafe(_stop_event.set)
            except RuntimeError:
                pass

def run(secret, port, domains, callback):
    global _stop_requested
    # Java serializes starts. A stop arriving during Python initialization is
    # supplied by the callback before the loop starts.
    with _lock:
        _stop_requested = bool(callback.isStopping())
    if len(secret) != 32 or len(bytes.fromhex(secret)) != 16:
        raise ValueError('Invalid proxy secret')
    proxy_config.host = '127.0.0.1'
    proxy_config.port = int(port)
    proxy_config.secret = secret
    proxy_config.pool_size = 4
    proxy_config.dc_redirects = {2: '149.154.167.220', 4: '149.154.167.220'}
    proxy_config.cfproxy_user_domains = domains.split() if domains.strip() else []
    handler = _LogHandler(callback)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    try:
        asyncio.run(_run(callback))
    finally:
        root.removeHandler(handler)
        from proxy import config
        config._refresh_stop.set()

async def _run(callback):
    global _loop, _stop_event
    with _lock:
        _loop = asyncio.get_running_loop()
        _stop_event = asyncio.Event()
        if _stop_requested:
            _stop_event.set()
    task = asyncio.create_task(core._run(_stop_event))
    notified = False
    try:
        while not task.done():
            if _stop_event.is_set():
                try:
                    await asyncio.wait_for(asyncio.shield(task), 5)
                except asyncio.TimeoutError:
                    task.cancel()
                break
            server = core._server_instance
            if server is not None and server.is_serving() and not notified:
                callback.onProxyReady()
                notified = True
            callback.onStats(stats.connections_active, human_bytes(stats.bytes_up), human_bytes(stats.bytes_down))
            await asyncio.sleep(.5)
        try:
            await task
        except asyncio.CancelledError:
            pass
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        with _lock:
            _loop = _stop_event = None

def crypto_selftest():
    # NIST SP 800-38A, F.5.1; irregular chunks exercise partial-block state.
    key = bytes.fromhex('2b7e151628aed2a6abf7158809cf4f3c')
    iv = bytes.fromhex('f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff')
    plain = bytes.fromhex('6bc1bee22e409f96e93d7e117393172aae2d8a571e03ac9c9eb76fac45af8e51')
    expected = bytes.fromhex('874d6191b620e3261bef6864990db6ce9806f66b7970fdff8617187bb9fffdff')
    stream = android_aes.Cipher(android_aes.algorithms.AES(key), android_aes.modes.CTR(iv)).encryptor()
    actual = b''.join(stream.update(plain[a:b]) for a,b in [(0,1),(1,7),(7,19),(19,32)])
    assert actual == expected, (actual.hex(), expected.hex())
    assert stream.update(b'') == b''
    return 'NIST AES-CTR streaming: OK'
