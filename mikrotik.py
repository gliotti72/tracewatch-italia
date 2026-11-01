"""Minimal read-only RouterOS binary API over verified TLS (standard library only)."""
import socket
import ssl
import struct

MAX_WORD = 1024 * 1024


def _length(n):
    if n < 0x80: return bytes([n])
    if n < 0x4000: return struct.pack('>H', n | 0x8000)
    if n < 0x200000: return struct.pack('>I', n | 0xC00000)[1:]
    if n < 0x10000000: return struct.pack('>I', n | 0xE0000000)
    return b'\xf0' + struct.pack('>I', n)


def _read_exact(sock, count):
    result = bytearray()
    while len(result) < count:
        chunk = sock.recv(count - len(result))
        if not chunk: raise ConnectionError('Connessione API interrotta')
        result.extend(chunk)
    return bytes(result)


def _read_length(sock):
    first = _read_exact(sock, 1)[0]
    if first < 0x80: return first
    if first < 0xC0: return ((first & 0x3f) << 8) | _read_exact(sock, 1)[0]
    if first < 0xE0: return ((first & 0x1f) << 16) | int.from_bytes(_read_exact(sock, 2), 'big')
    if first < 0xF0: return ((first & 0x0f) << 24) | int.from_bytes(_read_exact(sock, 3), 'big')
    if first == 0xF0: return int.from_bytes(_read_exact(sock, 4), 'big')
    raise ValueError('Lunghezza API non valida')


def _command(sock, words):
    payload = b''.join(_length(len(w.encode('utf-8'))) + w.encode('utf-8') for w in words) + b'\x00'
    sock.sendall(payload)
    rows = []
    for _ in range(1000):
        parts = []
        while True:
            length = _read_length(sock)
            if length == 0: break
            if length > MAX_WORD: raise ValueError('Risposta API troppo grande')
            parts.append(_read_exact(sock, length).decode('utf-8', 'replace'))
        if not parts: raise ValueError('Risposta API vuota')
        if parts[0] in ('!trap', '!fatal'):
            message = next((p[9:] for p in parts[1:] if p.startswith('=message=')), 'Accesso API negato')
            raise RuntimeError(message)
        if parts[0] == '!done': return rows
        if parts[0] == '!re':
            rows.append({p[1:].split('=', 1)[0]: p[1:].split('=', 1)[1] for p in parts[1:] if p.startswith('=') and '=' in p[1:]})
    raise ValueError('Troppe risposte API')


def poll(host, port, username, password, ca_file):
    context = ssl.create_default_context(cafile=ca_file)
    context.check_hostname = True
    with socket.create_connection((host, int(port)), timeout=8) as raw:
        with context.wrap_socket(raw, server_hostname=host) as sock:
            sock.settimeout(8)
            _command(sock, ['/login', '=name=' + username, '=password=' + password])
            peers = _command(sock, ['/ip/ipsec/active-peers/print', '=.proplist=id,remote-address,state,uptime,ph2-total'])
            sas = _command(sock, ['/ip/ipsec/installed-sa/print', '=.proplist=src-address,dst-address,state,auth-algorithm,enc-algorithm,current-bytes,current-packets'])
    return {'connected': True, 'active_peers': peers[:30], 'installed_sa': sas[:60]}
