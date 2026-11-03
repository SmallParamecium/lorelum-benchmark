"""Public application runtime. Application policy lives in app.py, not here."""
import json
import sys
if __name__ == '__main__':
    sys.modules['server'] = sys.modules[__name__]
import os
import queue
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import psycopg
from psycopg.rows import dict_row


class Cancelled(BaseException):
    pass


class Pool:
    def __init__(self):
        self.free = queue.Queue(2)
        for _ in range(2):
            self.free.put(psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row))

    def acquire(self):
        return self.free.get(timeout=0.8)

    def release(self, conn):
        self.free.put_nowait(conn)

    @contextmanager
    def connection(self):
        conn = self.acquire()
        try:
            yield conn
        finally:
            if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
                conn.rollback()
            self.release(conn)


pool = Pool()
_query_count = threading.local()


def sql(conn, query, args=()):
    _query_count.value = getattr(_query_count, 'value', 0) + 1
    return conn.execute(query, args)


def checkpoint(request, name):
    if request.get('fault') == name:
        raise RuntimeError('injected interruption: ' + name)
    if request.get('cancel') == name:
        raise Cancelled('request cancelled at ' + name)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass
    def do_POST(self):
        _query_count.value = 0
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise ValueError('invalid request length')
            request = json.loads(self.rfile.read(length))
            import app
            result = app.handle(request)
            status = 200
        except BaseException as exc:
            result = {'error': type(exc).__name__, 'message': str(exc)}
            status = 500
        payload = json.dumps({'result': result, 'queries': _query_count.value}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    import app
    with pool.connection() as connection:
        app.prepare(connection)
    ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
