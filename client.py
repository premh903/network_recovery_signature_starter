import csv
import socket
import threading
import time

HOST = '127.0.0.1'
GATEWAY_ADDR = ('127.0.0.1', 10001)
LOCAL_PORT = 10000

DURATION_SEC = 90
INTERVAL_SEC = 0.10
OUTPUT_FILE = 'results.csv'

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, LOCAL_PORT))
sock.settimeout(0.2)

send_times = {}
receive_times = {}
lock = threading.Lock()
stop_event = threading.Event()

start_time = time.monotonic()


def receiver():
    while not stop_event.is_set():
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            return

        try:
            text = data.decode()
            # REPLY|sequence
            parts = text.split('|')
            if len(parts) != 2 or parts[0] != 'REPLY':
                continue
            seq = int(parts[1])
        except (ValueError, UnicodeDecodeError):
            continue

        now = time.monotonic()
        with lock:
            receive_times[seq] = now


threading.Thread(target=receiver, daemon=True).start()

print('Client started.')
print('Collecting data for 90 seconds: 20s baseline + 20s impairment + recovery.')

next_send = start_time
seq = 0

while True:
    now = time.monotonic()
    if now - start_time >= DURATION_SEC:
        break

    if now < next_send:
        time.sleep(next_send - now)
        continue

    seq += 1
    with lock:
        send_times[seq] = time.monotonic()

    message = f'PROBE|{seq}'.encode()
    try:
        sock.sendto(message, GATEWAY_ADDR)
    except OSError:
        pass

    next_send += INTERVAL_SEC

# Let very late replies arrive.
time.sleep(1.0)
stop_event.set()
sock.close()

rows = []
for sequence, sent_at in sorted(send_times.items()):
    with lock:
        received_at = receive_times.get(sequence)

    if received_at is None:
        rows.append([sequence, sent_at - start_time, '', 'timeout'])
    else:
        rtt_ms = (received_at - sent_at) * 1000.0
        rows.append([sequence, sent_at - start_time, f'{rtt_ms:.3f}', 'ok'])

with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['sequence', 'time_s', 'rtt_ms', 'status'])
    writer.writerows(rows)

print(f'Finished. Saved {len(rows)} probe results to {OUTPUT_FILE}')
print('Run analyzer.py next.')
