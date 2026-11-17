"""Opt-in route probes. No Telegram login, account data, or proxy secrets."""
import asyncio
import json
import os
import socket
import struct
import time
import ssl
import android_bridge  # Installs the Android AES adapter before core imports.
from proxy.raw_websocket import RawWebSocket
from proxy.utils import create_ssl_context
from proxy.config import CFPROXY_DEFAULT_DOMAINS
from android_aes import Cipher, algorithms, modes

results = []

async def https(host, path='/', tls12=False):
    started=time.monotonic()
    stage='DNS'
    writer=None
    try:
        addresses=await asyncio.wait_for(asyncio.get_running_loop().getaddrinfo(host,443,type=socket.SOCK_STREAM),6)
        families=sorted(set('IPv6' if a[0]==socket.AF_INET6 else 'IPv4' for a in addresses))
        stage='TLS'
        context=create_ssl_context()
        if tls12:context.maximum_version=ssl.TLSVersion.TLSv1_2
        reader,writer=await asyncio.wait_for(asyncio.open_connection(host,443,ssl=context,server_hostname=host),7)
        stage='HTTP'
        writer.write(f'HEAD {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n'.encode())
        await writer.drain()
        status=await asyncio.wait_for(reader.readline(),5)
        return {'route':'https:'+host+(':tls12' if tls12 else ''),'ok':True,'status':status.decode(errors='replace').strip(),'families':families,'seconds':round(time.monotonic()-started,2)}
    except Exception as exc:
        return {'route':'https:'+host+(':tls12' if tls12 else ''),'ok':False,'stage':stage,'error':type(exc).__name__+': '+str(exc)[:160],'seconds':round(time.monotonic()-started,2)}
    finally:
        if writer is not None:
            writer.close()

async def websocket(dc,target,domain=None,front=False):
    domain=domain or f'kws{dc}.web.telegram.org'
    route=f'ws:DC{dc}:{target}'+(':front' if front else '')
    started=time.monotonic()
    try:
        ws=await RawWebSocket.connect(target,domain,timeout=5,sni='sprinthost.ru' if front else None)
        await ws.close()
        return {'route':route,'ok':True,'seconds':round(time.monotonic()-started,2)}
    except Exception as exc:
        return {'route':route,'ok':False,'error':type(exc).__name__+': '+str(exc)[:160],'seconds':round(time.monotonic()-started,2)}

def direct_mtproto(dc,host):
    started=time.monotonic()
    stage='TCP'
    try:
        core=android_bridge.core
        init=core._generate_relay_init(b'\xdd'*4,dc)
        key_iv=init[8:56]
        enc=Cipher(algorithms.AES(key_iv[:32]),modes.CTR(key_iv[32:])).encryptor()
        enc.update(bytes(64))
        reverse=key_iv[::-1]
        dec=Cipher(algorithms.AES(reverse[:32]),modes.CTR(reverse[32:])).encryptor()
        nonce=os.urandom(16)
        body=struct.pack('<I',0xbe7e8ef1)+nonce
        packet=struct.pack('<QQI',0,int(time.time()*(1<<32))&~3,len(body))+body+os.urandom(8)
        def receive(sock,count):
            output=b''
            while len(output)<count:
                data=sock.recv(count-len(output))
                if not data:raise ConnectionError('Connection closed')
                output+=data
            return output
        with socket.create_connection((host,443),5) as sock:
            stage='MTProto'
            sock.settimeout(7)
            sock.sendall(init+enc.update(struct.pack('<I',len(packet))+packet))
            length=struct.unpack('<I',dec.update(receive(sock,4)))[0]
            if not 40<=length<=1048576:raise ValueError('Invalid response length')
            response=dec.update(receive(sock,length))
            if response[20:24]!=struct.pack('<I',0x05162463) or response[24:40]!=nonce:raise ValueError('resPQ/nonce mismatch')
        return {'route':f'tcp:DC{dc}','ok':True,'response':'resPQ; nonce verified','seconds':round(time.monotonic()-started,2)}
    except Exception as exc:
        return {'route':f'tcp:DC{dc}','ok':False,'stage':stage,'error':type(exc).__name__+': '+str(exc)[:160],'seconds':round(time.monotonic()-started,2)}

async def main():
    if globals().get('diagnostic_mode')=='cloudflare':
        return await asyncio.gather(https('workers.dev'),https('dash.cloudflare.com'),https('example.com'))
    jobs=[https('example.com'),https('ya.ru'),https('www.google.com','/generate_204'),https('raw.githubusercontent.com','/Flowseal/tg-ws-proxy/main/.github/cfproxy-domains.txt')]
    for dc,ip in ((2,'149.154.167.51'),(4,'149.154.167.91')):
        jobs += [websocket(dc,'149.154.167.220'),websocket(dc,f'kws{dc}.web.telegram.org'),websocket(dc,'149.154.167.220',front=True),asyncio.to_thread(direct_mtproto,dc,ip)]
    for base in CFPROXY_DEFAULT_DOMAINS:
        jobs.append(websocket(2,'kws2.'+base,'kws2.'+base))
    for base in CFPROXY_DEFAULT_DOMAINS[:2]:
        jobs += [https('kws2.'+base),https('kws2.'+base,tls12=True)]
    semaphore=asyncio.Semaphore(5)
    async def limited(job):
        async with semaphore:
            return await job
    return await asyncio.gather(*(limited(job) for job in jobs))

report_json=json.dumps(asyncio.run(main()))
