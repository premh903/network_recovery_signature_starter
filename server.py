import socket

HOST = '127.0.0.1'
PORT = 10002

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((HOST, PORT))

print(f'Server listening on {HOST}:{PORT}')
print('Press Ctrl+C to stop.')

while True:
    data, addr = sock.recvfrom(4096)
    # Echo the probe back to the gateway.
    sock.sendto(data.replace(b'PROBE', b'REPLY', 1), addr)
