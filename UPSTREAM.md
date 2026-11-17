# Upstream and license

This is an unofficial Android port of [Flowseal/tg-ws-proxy](https://github.com/Flowseal/tg-ws-proxy).

The `proxy/` package and the upstream Python tests were copied from upstream commit `6690b788432fd0f59b0f38e228494bcd6bede1ca` (version 1.11.4). The upstream MIT license is preserved in `LICENSE`.

Android-specific code is in `android/`. At build time the Gradle project copies the `proxy/` package, then supplies an Android lifecycle bridge and a streaming AES-CTR adapter backed by Android JCA. Desktop UI files and desktop packaging are intentionally omitted from this Android distribution.

Version `1.11.4-android.3` adds an optional bearer key to Worker connections in `proxy/config.py`, `proxy/raw_websocket.py`, `proxy/pool.py`, and `proxy/bridge.py`. This extends the upstream Worker path without putting the key in URLs. `cloudflare/worker.js` adapts the MIT-licensed example in upstream `docs/RU/CfWorker.md`, with key verification, a Telegram-only destination list, and ordered stream writes.

Runtime dependencies include Chaquopy (Python runtime), certifi (CA certificates), and httpx/httpcore/h2 and their dependencies. Those projects retain their respective licenses. No credentials or signing keys are included in this repository.
