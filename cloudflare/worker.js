// TG WS Proxy bridge. Based on Flowseal/tg-ws-proxy (MIT).
import { connect } from "cloudflare:sockets";

const DATACENTERS = Object.freeze({
  "1": "149.154.175.50", "2": "149.154.167.51",
  "3": "149.154.175.100", "4": "149.154.167.91",
  "5": "149.154.171.5", "203": "91.105.192.100",
});

async function toBytes(data) {
  if (data instanceof ArrayBuffer) return new Uint8Array(data);
  if (ArrayBuffer.isView(data)) return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
  if (data && typeof data.arrayBuffer === "function") return new Uint8Array(await data.arrayBuffer());
  throw new TypeError("Binary WebSocket frames required");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/") return new Response("TG WS Proxy Worker is online. Configure its domain and AUTH_TOKEN in the Android app.\n");
    if (url.pathname !== "/apiws") return new Response("Not found", { status: 404 });
    if (!env.AUTH_TOKEN || !/^[A-Za-z0-9_-]{16,128}$/.test(env.AUTH_TOKEN)) return new Response("Set the AUTH_TOKEN secret first", { status: 503 });
    if (request.headers.get("Authorization") !== `Bearer ${env.AUTH_TOKEN}`) return new Response("Unauthorized", { status: 401 });
    if ((request.headers.get("Upgrade") || "").toLowerCase() !== "websocket") return new Response("Expected WebSocket", { status: 426 });
    const dc = url.searchParams.get("dc");
    const dst = url.searchParams.get("dst");
    if (!Object.hasOwn(DATACENTERS, dc) || DATACENTERS[dc] !== dst) return new Response("Unsupported Telegram datacenter", { status: 400 });

    let socket;
    try {
      socket = connect({ hostname: DATACENTERS[dc], port: 443 });
      socket.closed?.catch(() => {});
      await socket.opened;
    } catch {
      try { Promise.resolve(socket?.close()).catch(() => {}); } catch {}
      return new Response("Telegram datacenter unavailable", { status: 502 });
    }
    const pair = new WebSocketPair();
    const client = pair[0], server = pair[1];
    server.accept();
    const reader = socket.readable.getReader();
    const writer = socket.writable.getWriter();
    let closed = false;
    function finish(code = 1000, reason = "") {
      if (closed) return;
      closed = true;
      try { server.close(code, reason); } catch {}
      Promise.resolve(reader.cancel()).catch(() => {});
      Promise.resolve(writer.abort()).catch(() => {});
      try { Promise.resolve(socket.close()).catch(() => {}); } catch {}
    }
    let writes = Promise.resolve();
    server.addEventListener("message", event => {
      writes = writes.then(async () => {
        if (closed) return;
        const data = await toBytes(event.data);
        if (data.byteLength > 16 * 1024 * 1024) { finish(1009, "Frame too large"); return; }
        await writer.write(data);
      }).catch(() => finish(1011, "Upstream write failed"));
    });
    server.addEventListener("close", () => finish());
    server.addEventListener("error", () => finish(1011, "WebSocket error"));
    (async () => {
      try {
        while (!closed) {
          const { value, done } = await reader.read();
          if (done) break;
          if (value && !closed) server.send(value);
        }
      } catch {} finally { finish(); }
    })();
    return new Response(null, { status: 101, webSocket: client });
  },
};
