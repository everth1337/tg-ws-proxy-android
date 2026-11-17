"""Restart the proxy on a new Android default network, preserving settings."""
import asyncio


async def _finish(task, session_stop, timeout):
    session_stop.set()
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout)
    except asyncio.TimeoutError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def supervise(run_core, stop, revision, is_ready, on_ready,
                    on_reconnecting, on_tick, *, interval=.25, shutdown_timeout=5):
    while not stop.is_set():
        current_revision = revision()
        session_stop = asyncio.Event()
        task = asyncio.create_task(run_core(session_stop))
        notified = False
        try:
            while not task.done():
                changed = revision() != current_revision
                if stop.is_set() or changed:
                    if changed and not stop.is_set():
                        on_reconnecting()
                    await _finish(task, session_stop, shutdown_timeout)
                    break
                if is_ready() and not notified:
                    on_ready()
                    notified = True
                on_tick()
                try:
                    await asyncio.wait_for(stop.wait(), interval)
                except asyncio.TimeoutError:
                    pass
            # Propagate unexpected failures instead of leaving a false ready state.
            if not task.cancelled():
                await task
            if not stop.is_set() and revision() == current_revision:
                raise RuntimeError('Proxy listener stopped unexpectedly')
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
