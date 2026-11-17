import { test } from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import { readFile } from 'node:fs/promises';

const key = 'example-test-key-not-a-real-secret';
const source = await readFile(new URL('./worker.js', import.meta.url), 'utf8');

async function setup() {
  const state = { connects: [], writes: [], sent: [], closed: 0 };
  class Socket {
    constructor() { this.listeners = {}; }
    accept() { this.accepted = true; }
    addEventListener(type, callback) { this.listeners[type] = callback; }
    send(data) { state.sent.push(Array.from(data)); }
    close() { this.closed = true; }
    emit(type, data) { this.listeners[type]?.({ data }); }
  }
  class WebSocketPair {
    constructor() { this[0] = new Socket(); this[1] = new Socket(); state.server = this[1]; }
  }
  const context = vm.createContext({ URL, ArrayBuffer, Uint8Array, WebSocketPair,
    Response: class { constructor(body, options = {}) { this.body = body; Object.assign(this, { status: 200 }, options); } },
  });
  const sockets = new vm.SyntheticModule(['connect'], function() {
    this.setExport('connect', address => {
      state.connects.push(address);
      return {
        opened: Promise.resolve({}),
        readable: new ReadableStream({ start(controller) { state.upstream = controller; } }),
        writable: new WritableStream({ write(data) { state.writes.push(Array.from(data)); } }),
        close() { state.closed++; },
      };
    });
  }, { context });
  const module = new vm.SourceTextModule(source, { context });
  await module.link(name => { assert.equal(name, 'cloudflare:sockets'); return sockets; });
  await module.evaluate();
  const request = (path = '/apiws?dc=2&dst=149.154.167.51', headers = {}) => new Request('https://bridge.example' + path, {
    headers: { Upgrade: 'websocket', Authorization: 'Bearer ' + key, ...headers },
  });
  return { state, request, fetch: (request, env = { AUTH_TOKEN: key }) => module.namespace.default.fetch(request, env) };
}

test('missing secret rejects the upgrade without opening TCP', async () => {
  const t = await setup();
  assert.equal((await t.fetch(t.request(), {})).status, 503);
  assert.equal(t.state.connects.length, 0);
});
test('wrong bearer key is rejected without opening TCP', async () => {
  const t = await setup();
  assert.equal((await t.fetch(t.request(undefined, { Authorization: 'Bearer wrong' }))).status, 401);
  assert.equal(t.state.connects.length, 0);
});
test('arbitrary targets and mismatched datacenters are rejected', async () => {
  const t = await setup();
  for (const path of ['/apiws?dc=2&dst=127.0.0.1', '/apiws?dc=1&dst=149.154.167.51', '/apiws?dc=99&dst=149.154.167.51']) {
    assert.equal((await t.fetch(t.request(path))).status, 400);
  }
  assert.equal(t.state.connects.length, 0);
});
test('normal HTTP does not open a TCP bridge', async () => {
  const t = await setup();
  assert.equal((await t.fetch(t.request('/'))).status, 200);
  assert.equal((await t.fetch(t.request('/wrong'))).status, 404);
  assert.equal((await t.fetch(t.request(undefined, { Upgrade: '' }))).status, 426);
  assert.equal(t.state.connects.length, 0);
});
test('authorized frames retain order and both directions close together', async () => {
  const t = await setup();
  assert.equal((await t.fetch(t.request())).status, 101);
  assert.equal(t.state.connects.length, 1);
  assert.equal(t.state.connects[0].hostname, '149.154.167.51');
  assert.equal(t.state.connects[0].port, 443);
  assert.equal(t.state.server.accepted, true);
  let completeFirst;
  const first = new Promise(resolve => { completeFirst = resolve; });
  t.state.server.emit('message', { arrayBuffer: () => first });
  t.state.server.emit('message', new Uint8Array([3, 4]).buffer);
  await new Promise(setImmediate);
  assert.deepEqual(t.state.writes, []);
  completeFirst(new Uint8Array([1, 2]).buffer);
  await new Promise(setImmediate);
  assert.deepEqual(t.state.writes, [[1, 2], [3, 4]]);
  t.state.upstream.enqueue(new Uint8Array([5, 6]));
  await new Promise(setImmediate);
  assert.deepEqual(t.state.sent, [[5, 6]]);
  t.state.server.emit('close');
  await new Promise(setImmediate);
  assert.equal(t.state.closed, 1);
  assert.equal(t.state.server.closed, true);
});
