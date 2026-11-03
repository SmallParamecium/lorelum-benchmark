"""Fixed-target host ingress. No arbitrary destination or HTTP CONNECT support."""
import socket
import threading


def copy(source, destination):
    try:
        while data := source.recv(65536):
            destination.sendall(data)
    except OSError:
        pass
    finally:
        try:
            destination.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def connection(client, target, port):
    try:
        with client, socket.create_connection((target, port), timeout=2) as upstream:
            upstream.settimeout(None)
            reverse = threading.Thread(target=copy, args=(upstream, client))
            reverse.start()
            copy(client, upstream)
            reverse.join()
    except OSError:
        client.close()


def listen(port, target):
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('0.0.0.0', port))
        listener.listen(16)
        while True:
            client, _ = listener.accept()
            threading.Thread(target=connection, args=(client, target, port), daemon=True).start()


threading.Thread(target=listen, args=(5432, 'database'), daemon=True).start()
listen(8080, 'application')
