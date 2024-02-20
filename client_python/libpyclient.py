#!/usr/bin/env python
import socket
import time
from threading import Thread
import json


class TcpConnection(Thread):
    PACKET_LIMIT = 1024 * 1024
    HEADER_LEN = 4

    def __init__(self, svr_ip, svr_port=2021, recv_cb=None):
        Thread.__init__(self)
        self.svr_ip = svr_ip
        self.svr_port = svr_port
        self.recv_cb = recv_cb
        self.socket = None
        self.running = False

    def send_data(self, data_bytes):
        data_len = len(data_bytes)
        assert data_len != 0, "Try to send empty string shouldn't happen."
        if data_len > self.PACKET_LIMIT:
            data_len = self.PACKET_LIMIT
            data_bytes = data_bytes[:data_len]
        header = data_len.to_bytes(self.HEADER_LEN, byteorder="little")
        self.socket.send(header + data_bytes)

    def recv_data(self):
        data = bytes([])
        header = self.socket.recv(self.HEADER_LEN)
        if not header:
            return b""
        lens = int.from_bytes(header, byteorder="little")
        # Receiving data block
        n_received = 0
        while n_received < lens:
            remaining = lens - n_received
            buf_len = min(remaining, 4096)
            data += self.socket.recv(buf_len)
            n_received = len(data)
        return data

    def run(self):
        print("Connect to communication server at %s:%d" % (self.svr_ip, self.svr_port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.svr_ip, self.svr_port))
        self.socket.settimeout(1)

        self.running = True
        while self.running:
            try:
                client_pdu = self.recv_data()
                if not client_pdu:
                    print("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except socket.error as v:
                errorcode = v[0]
                print("Socket recv exception: %s" % str(errorcode))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(client_pdu)
                else:
                    print("XXX: Discard message due to callback not available")

        print("Client TcpConnection exit.")
        self.socket.close()
        self.socket = None

    def is_connected(self):
        return self.socket is not None
        
    def stop(self):
        self.running = False
        #TODO: should wait till self.is_connected() to false. This may take up to 1 second.

class UdpConnection(Thread):
    PACKET_LIMIT = 1024

    def __init__(self, svr_ip, svr_port=2021, recv_cb=None):
        Thread.__init__(self)
        self.svr_ip = svr_ip
        self.svr_port = svr_port
        self.recv_cb = recv_cb
        self.socket = None
        self.running = False

    def send_data(self, data_bytes):
        data_len = len(data_bytes)
        assert data_len != 0, "Try to send empty string shouldn't happen."
        if data_len > self.PACKET_LIMIT:
            data_len = self.PACKET_LIMIT
            data_bytes = data_bytes[:data_len]
        self.socket.send(data_bytes)

    def recv_data(self):
        data = self.socket.recv(self.PACKET_LIMIT)
        if not data:
            return b""
        return data

    def run(self):
        print("Connect to communication server at %s:%d" % (self.svr_ip, self.svr_port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.connect((self.svr_ip, self.svr_port))
        self.socket.settimeout(1)
        self.send_data(b"010011000111")

        self.running = True
        while self.running:
            try:
                client_pdu = self.recv_data()
                if not client_pdu:
                    print("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except socket.error as v:
                errorcode = v[0]
                print("Socket recv exception: %s" % str(errorcode))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(client_pdu)
                else:
                    print("Discard message due to no callback available")

        print("Client UdpConnection exit.")
        self.socket.close()
        self.socket = None

    def is_connected(self):
        return self.socket is not None
        
    def stop(self):
        self.running = False
        #TODO: should wait till self.is_connected() to false. This may take up to 1 second.

class Transport(object):
    def __init__(self, svr_ip, svr_port):
        Thread.__init__(self)
        self.svr_ip = svr_ip
        self.svr_port = svr_port
        self.udp_port = None
        self.tcp_conn = None
        self.udp_conn = None

    def on_tcp_data_recv_callback(self, data_bytes):
        print("Tcp data received from server: [%s]" % data_bytes.decode())
        cmd = json.loads(data_bytes.decode())
        if cmd["action"] == "create_udp_channel":
            assert self.udp_conn is None, "Udp channel had already created."
            self.udp_port = int(cmd["data"])
            self.udp_conn = UdpConnection(self.svr_ip, self.udp_port, self.on_udp_data_recv_callback)
            self.udp_conn.start()
        else:
            print("XXX: PDU is not handled.")

    def on_udp_data_recv_callback(self, data_bytes):
        print("Udp data received from server, %d bytes. (XXX: Not handled.)" % len(data_bytes))

    def connect(self):
        self.tcp_conn = TcpConnection(self.svr_ip, self.svr_port, self.on_tcp_data_recv_callback)
        self.tcp_conn.start()

    def send_tcp_pdu(self, action, data):
        cmd = {"action": action,
               "data": data
              }
        cmd_str = json.dumps(cmd)
        self.tcp_conn.send_data(cmd_str.encode())

    def create_udp_channel(self):
        self.send_tcp_pdu("create_udp_channel", "")

    def client_update_status(self, status_str):
        self.send_tcp_pdu("update_status", status_str)

    def broadcast_tcp_message(self, msg_str):
        self.send_tcp_pdu("broadcast", msg_str)

    def send_tcp_data(self, data_str):
        self.send_tcp_pdu("data", data_str)

    def send_udp_data(self, data_bytes):
        if self.udp_conn is None:
            print("XXX: No Udp connection yet.")
            return
        self.udp_conn.send_data(data_bytes)

    def close(self):
        if self.tcp_conn is not None:
            self.tcp_conn.stop()
            self.tcp_conn = None
        if self.udp_conn is not None:
            self.udp_conn.stop()
            self.udp_conn = None
