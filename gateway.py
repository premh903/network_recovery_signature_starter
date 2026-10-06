import random
import socket
import sys
import threading
import time

HOST = '127.0.0.1'
GATEWAY_PORT = 10001
SERVER_ADDR = ('127.0.0.1', 10002)

BASELINE_SEC = 20
IMPAIRMENT_SEC = 20

SCENARIOS = {
    'delay': {
        'delay_ms': 100,
        'jitter_ms': 10,
        'loss_prob': 0.0,
    },
    'loss': {
        'delay_ms': 0,
        'jitter_ms': 0,
        'loss_prob': 0.15,
    },
    'combined': {
        'delay_ms': 100,
        'jitter_ms': 20,
        'loss_prob': 0.10,
    },
}

scenario = sys.argv[1].lower() if len(sys.argv) > 1 else 'combined'
if scenario not in SCENARIOS:
    print('Usage: python gateway.py [delay|loss|combined]')
    raise SystemExit(1)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, GATEWAY_PORT))
sock.settimeout(0.2)

start_time = None
client_addr = None
print(f'Gateway listening on {HOST}:{GATEWAY_PORT}')
print(f'Scenario: {scenario}')
print(f'Baseline: {BASELINE_SEC}s | Impairment: {IMPAIRMENT_SEC}s | Recovery: afterwards')


def current_impairment():
    elapsed = time.monotonic() - start_time
    if elapsed < BASELINE_SEC:
        return {'delay_ms': 0, 'jitter_ms': 0, 'loss_prob': 0.0, 'phase': 'baseline'}
    if elapsed < BASELINE_SEC + IMPAIRMENT_SEC:
        cfg = SCENARIOS[scenario].copy()
        cfg['phase'] = 'impairment'
        return cfg
    return {'delay_ms': 0, 'jitter_ms': 0, 'loss_prob': 0.0, 'phase': 'recovery'}


def delayed_forward(data, destination, delay_ms, jitter_ms):
    extra_ms = random.uniform(-jitter_ms, jitter_ms) if jitter_ms else 0
    total_ms = max(0.0, delay_ms + extra_ms)
    if total_ms:
        time.sleep(total_ms / 1000.0)
    sock.sendto(data, destination)


while True:
    try:
        data, addr = sock.recvfrom(4096)
    except socket.timeout:
        continue
    except KeyboardInterrupt:
        break

    if data.startswith(b'PROBE'):
        client_addr = addr

        if start_time is None:
            start_time = time.monotonic()
            print('Experiment clock started on first probe.')

        cfg = current_impairment()

        if random.random() < cfg['loss_prob']:
            continue

        thread = threading.Thread(
            target=delayed_forward,
            args=(data, SERVER_ADDR, cfg['delay_ms'], cfg['jitter_ms']),
            daemon=True,
        )
        thread.start()

    elif data.startswith(b'REPLY') and client_addr is not None:
        sock.sendto(data, client_addr)
