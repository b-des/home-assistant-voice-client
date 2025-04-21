import socket
import threading
import time

import logger

UDP_PORT = 8888
BROADCAST_INTERVAL = 3  # seconds

known_peers = set()
log = logger.get(__name__)


def get_own_ip():
    # Best effort to get the LAN IP
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


my_ip = get_own_ip()


def udp_broadcast():
    msg = f"hello;{my_ip}".encode("utf-8")
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(msg, ("<broadcast>", UDP_PORT))
            s.close()
        except Exception as e:
            print(f"[broadcast] Error: {e}")
        time.sleep(BROADCAST_INTERVAL)


def udp_listener(loop, queue):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", UDP_PORT))
    log.info(f"[listen] Listening on UDP port {UDP_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode("utf-8")
            if msg.startswith("hello;"):
                _, peer_ip = msg.split(";")
                if peer_ip != my_ip and peer_ip not in known_peers:
                    known_peers.add(peer_ip)
                    loop.call_soon_threadsafe(queue.put_nowait, peer_ip)
                    log.info(f"[peer] Discovered: {peer_ip}")
        except Exception as e:
            log.info(f"[listen] Error: {e}")


if __name__ == "__main__":
    log.info(f"[startup] Running as {my_ip}")
    threading.Thread(target=udp_listener, daemon=True).start()
    threading.Thread(target=udp_broadcast, daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\n[exit] Shutting down.")
