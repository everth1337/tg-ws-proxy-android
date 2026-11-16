"""Request resPQ through an Android proxy, without logging in to Telegram.

Requires cryptography on the host; reads the debug app's local secret using
ADB run-as and forwards a host port to the device's loopback listener.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import socket
import struct
import subprocess
import time
import xml.etree.ElementTree as ET

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

def probe(port, secret, dc):
    init = bytearray(os.urandom(64))
    init[0] = 0x42
    init[56:60] = b'\xdd' * 4
    init[60:62] = struct.pack('<h', dc)
    key_iv = bytes(init[8:56])
    enc = Cipher(algorithms.AES(hashlib.sha256(key_iv[:32] + secret).digest()), modes.CTR(key_iv[32:])).encryptor()
    reverse = key_iv[::-1]
    dec = Cipher(algorithms.AES(hashlib.sha256(reverse[:32] + secret).digest()), modes.CTR(reverse[32:])).encryptor()
    encrypted = enc.update(bytes(init))
    init[56:64] = encrypted[56:64]
    nonce = os.urandom(16)
    body = struct.pack('<I', 0xbe7e8ef1) + nonce
    message_id = (int(time.time() * (1 << 32)) & ~3)
    packet = struct.pack('<QQI', 0, message_id, len(body)) + body + os.urandom(8)

    def receive(sock, length):
        out = bytearray()
        while len(out) < length:
            chunk = sock.recv(length - len(out))
            if not chunk:
                raise ConnectionError('Proxy closed connection')
            out.extend(chunk)
        return bytes(out)

    started = time.monotonic()
    try:
        with socket.create_connection(('127.0.0.1', port), 10) as sock:
            sock.settimeout(60)
            sock.sendall(bytes(init) + enc.update(struct.pack('<I', len(packet)) + packet))
            length = struct.unpack('<I', dec.update(receive(sock, 4)))[0]
            if not 40 <= length <= 1048576:
                raise ValueError(f'Invalid response length {length}')
            response = dec.update(receive(sock, length))
            assert response[:8] == bytes(8), 'Unexpected auth_key_id'
            assert response[20:24] == struct.pack('<I', 0x05162463), 'Not a resPQ response'
            assert response[24:40] == nonce, 'Nonce mismatch'
        return {'dc': dc, 'ok': True, 'response': 'resPQ; nonce verified', 'seconds': round(time.monotonic() - started, 2)}
    except Exception as exc:
        return {'dc': dc, 'ok': False, 'error': str(exc), 'seconds': round(time.monotonic() - started, 2)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--serial', required=True)
    ap.add_argument('--dc', type=int, nargs='+', default=[1,2,3,4,5])
    ap.add_argument('--host-port', type=int, default=21443)
    args = ap.parse_args()
    adb = ['adb', '-s', args.serial]
    raw = subprocess.check_output(adb + ['shell', 'run-as', 'org.flowseal.tgws.android', 'cat', 'shared_prefs/proxy.xml'])
    prefs = ET.fromstring(raw)
    secret = bytes.fromhex(prefs.find("string[@name='secret']").text)
    port_node = prefs.find("int[@name='port']")
    port = int(port_node.get('value')) if port_node is not None else 1443
    subprocess.run(adb + ['forward', f'tcp:{args.host_port}', f'tcp:{port}'], check=True, capture_output=True)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda dc: probe(args.host_port, secret, dc), args.dc))
        print(json.dumps(results, indent=2))
        return 0 if all(r['ok'] for r in results) else 1
    finally:
        subprocess.run(adb + ['forward', '--remove', f'tcp:{args.host_port}'], check=True, capture_output=True)

if __name__ == '__main__':
    raise SystemExit(main())
