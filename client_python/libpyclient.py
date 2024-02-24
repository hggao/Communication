#!/usr/bin/env python
import json
import socket
from threading import Thread
import time

debugging_on = True

def dbg_log(msg):
    if debugging_on:
        print(msg)

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

    def is_connected(self):
        return self.running;

    def run(self):
        dbg_log("Connect to communication server at %s:%d" % (self.svr_ip, self.svr_port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.svr_ip, self.svr_port))
        self.socket.settimeout(1)

        self.running = True
        while self.running:
            try:
                client_pdu = self.recv_data()
                if not client_pdu:
                    dbg_log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except socket.error as v:
                errorcode = v[0]
                dbg_log("Socket recv exception: %s" % str(errorcode))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(client_pdu)
                else:
                    dbg_log("XXX: Discard message due to callback not available")

        dbg_log("Client TcpConnection exit.")
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
        dbg_log("Connect to communication server at %s:%d" % (self.svr_ip, self.svr_port))
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.connect((self.svr_ip, self.svr_port))
        self.socket.settimeout(1)
        self.send_data(b"010011000111")

        self.running = True
        while self.running:
            try:
                client_pdu = self.recv_data()
                if not client_pdu:
                    dbg_log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except socket.error as v:
                errorcode = v[0]
                dbg_log("Socket recv exception: %s" % str(errorcode))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(client_pdu)
                else:
                    dbg_log("Discard message due to no callback available")

        dbg_log("Client UdpConnection exit.")
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
        cmd = json.loads(data_bytes.decode())
        if cmd["action"] == "create_udp_channel":
            assert self.udp_conn is None, "Udp channel had already created."
            self.udp_port = int(cmd["data"])
            self.udp_conn = UdpConnection(self.svr_ip, self.udp_port, self.on_udp_data_recv_callback)
            self.udp_conn.start()
        elif cmd["action"] == "list_clients":
            print(cmd["data"])
        else:
            dbg_log("PDU not handled: [%s]" % data_bytes.decode())

    def on_udp_data_recv_callback(self, data_bytes):
        #dbg_log("Udp data received from server, %d bytes. (XXX: Not handled.)" % len(data_bytes))
        #i = 0;
        #while i < len(data_bytes):
        #    print(int.from_bytes(data_bytes[i:i+1], byteorder='little', signed=True))
        #    i += 2
        pass

    def connect(self):
        self.tcp_conn = TcpConnection(self.svr_ip, self.svr_port, self.on_tcp_data_recv_callback)
        self.tcp_conn.start()
        wait_tries = 50
        while wait_tries > 0:
            if self.tcp_conn.is_connected():
                return
            time.sleep(0.1)
            wait_tries -= 1

    def send_tcp_pdu(self, action, data):
        cmd = {"action": action,
               "data": data
              }
        cmd_str = json.dumps(cmd)
        self.tcp_conn.send_data(cmd_str.encode())

    def create_udp_channel(self):
        self.send_tcp_pdu("create_udp_channel", "")

    def client_update_user(self, usr_info):
        self.send_tcp_pdu("update_user", usr_info)

    def client_update_status(self, status_str):
        self.send_tcp_pdu("update_status", status_str)

    def broadcast_tcp_message(self, msg_str):
        self.send_tcp_pdu("broadcast", msg_str)

    def list_clients(self):
        self.send_tcp_pdu("list_clients", "")

    def send_tcp_data(self, data_str):
        self.send_tcp_pdu("data", data_str)

    def send_udp_data(self, data_bytes):
        if self.udp_conn is None:
            dbg_log("XXX: No Udp connection yet.")
            return
        self.udp_conn.send_data(data_bytes)

    def close(self):
        if self.tcp_conn is not None:
            self.tcp_conn.stop()
            self.tcp_conn = None
        if self.udp_conn is not None:
            self.udp_conn.stop()
            self.udp_conn = None
