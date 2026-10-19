"""The mock over a unix socket: the same handler and state as TCP, for the container envelope's network-less containers."""
import http.client
import json
import os
import socket
import tempfile
import unittest

from buffon.mock import MockServer


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path):
        super().__init__("localhost")
        self.path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.path)


class MockOverUnixSocket(unittest.TestCase):
    def post(self, conn):
        conn.request("POST", "/v1/chat/completions", json.dumps({"model": "bench-1", "stream": False, "messages": [{"role": "user", "content": "hi"}]}), {"Content-Type": "application/json"})
        return conn.getresponse()

    def test_a_request_over_the_socket_is_served_and_counted_like_a_tcp_one(self):
        path = os.path.join(tempfile.mkdtemp(), "mock.sock")
        with MockServer(unix_path=path) as server:
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o666)
            response = self.post(UnixConnection(path))
            body = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertTrue(body["choices"][0]["message"]["content"])
            tcp = http.client.HTTPConnection("127.0.0.1", server.port)
            self.assertEqual(self.post(tcp).status, 200)
            self.assertEqual(server.total, 2)            # one state: both listeners count
        self.assertFalse(os.path.exists(path))           # the socket file goes away with the server

    def test_without_a_unix_path_there_is_no_socket(self):
        with MockServer() as server:
            self.assertIsNone(server.unix_httpd)
