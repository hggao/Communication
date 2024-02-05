#!/usr/bin/env python3

import signal
import socket
import sys
import time
from datetime import datetime
from threading import Thread
import json

def log(msg):
    # Remove these two lines for debugging
    if len(msg) > 1024:
        msg = msg[:1016] + "[......]"

    t_now = datetime.now()
    fmt_msg = "%s %s\n" % (str(t_now), msg)
    try:
        f = open(LOG_PATH, 'a+')
        f.write(fmt_msg)
        f.close()
    except IOError:
        pass

class TcpConnection(Thread):
    PACKET_LIMIT = 1024 * 1024
    HEADER_LEN = 4

    def __init__(self, socket, client_addr, recv_cb, close_cb):
        Thread.__init__(self)
        self.recv_cb = recv_cb
        self.close_cb = close_cb
        self.socket = socket
        self.socket.settimeout(1)
        self.client_addr = client_addr
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
        self.send_data(b'{"action": "Welcome!", "data":""}') #Debugging purpose
        self.running = True
        while self.running:
            try:
                data_buf = self.recv_data()
                if not data_buf:
                    log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                log("Socket recv exception: %s" % str(e))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(data_buf)
                else:
                    log("XXX: Discard data due to callback not available")

        log("TcpConnection exit.")
        self.socket.close()
        self.socket = None
        self.close_cb()

    def stop(self):
        self.running = False
        #TODO: wait up to 1 second until thread quit

class UdpConnection(Thread):
    PACKET_LIMIT = 1024

    def __init__(self, socket, recv_cb, close_cb):
        Thread.__init__(self)
        self.recv_cb = recv_cb
        self.close_cb = close_cb
        self.socket = socket
        self.client_addr = None
        self.running = False

    def send_data(self, data_bytes):
        if self.client_addr is None:
            log("XXX: Don't know client UDP addr yet, discard sending")
            return
        data_len = len(data_bytes)
        assert data_len != 0, "Try to send empty string shouldn't happen."
        if data_len > self.PACKET_LIMIT:
            data_len = self.PACKET_LIMIT
            data_bytes = data_bytes[:data_len]
        self.socket.sendto(data_bytes, self.client_addr)

    def recv_data(self):
        data, addr = self.socket.recvfrom(self.PACKET_LIMIT)
        if not data:
            return b""
        if self.client_addr is None:
            log("Received first UDP data, save addr %s" % str(addr))
            self.client_addr = addr
        elif self.client_addr != addr:
            log("XXX: Received UDP data not from %s, not initial addr %s" % (str(addr), str(self.client_addr)))
            #TODO: Need further handling about this
        return data

    def run(self):
        self.running = True
        while self.running:
            try:
                data_buf = self.recv_data()
                if not data_buf:
                    log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                log("Socket recv exception: %s" % str(e))
                break
            else:
                if data_buf == b"010011000111":
                    pass #Hacking, first package for telling server the client udp address
                else:
                    if self.recv_cb is not None:
                        self.recv_cb(data_buf)
                    else:
                        log("XXX: Discard data due to callback not available")

        log("UdpConnection exit.")
        self.socket.close()
        self.socket = None
        self.close_cb()

    def stop(self):
        self.running = False
        #TODO: wait up to 1 second until thread quit

class Transport(object):
    def __init__(self, tp_id, tp_svr, tcp_socket, tcp_addr, tcp_recv_cb, udp_recv_cb, tp_close_cb):
        self.tp_id = tp_id;
        self.tcp_conn = None
        self.udp_conn = None
        self.tp_svr = tp_svr
        self.tcp_socket = tcp_socket
        self.tcp_addr = tcp_addr
        self.tcp_recv_cb = tcp_recv_cb
        self.udp_recv_cb = udp_recv_cb
        self.tp_close_cb = tp_close_cb
        self.closed = False

    def start(self):
        self.tcp_conn = TcpConnection(self.tcp_socket, self.tcp_addr, self.on_tcp_data_recv_callback, self.on_tcp_close_cb)
        self.tcp_conn.start()

    def on_tcp_data_recv_callback(self, data_bytes):
        cmd = json.loads(data_bytes.decode())
        if cmd["action"] == "create_udp_channel":
            log("Client request to create UDP channel")
            udp_port = self.creat_udp_channel()
            reply = {
                      "action": "create_udp_channel",
                      "data": "%d" % udp_port
                    }
            self.send_tcp_data(json.dumps(reply).encode())
        else:
            self.tcp_recv_cb(self, data_bytes)

    def on_udp_data_recv_callback(self, data_bytes):
        self.udp_recv_cb(self, data_bytes)

    def creat_udp_channel(self):
        if self.udp_conn is not None:
            log("UDP socket channel created already, Ignore this request")
            return
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        udp_socket.settimeout(1)
        udp_port = self.tp_svr.get_next_udp_port()
        while True:
            try:
                udp_socket.bind(("", udp_port))
                break
            except socket.error:
                log("Bind on port %d failed, try another port" % udp_port)
                udp_port = self.tp_svr.get_next_udp_port()
                continue
        self.udp_conn = UdpConnection(udp_socket, self.on_udp_data_recv_callback, self.on_udp_close_cb)
        self.udp_conn.start()
        return udp_port

    def send_tcp_data(self, data):
        if self.tcp_conn is None:
            log("XXX: tcp_conn is none is not right.")
            return
        self.tcp_conn.send_data(data)

    def send_udp_data(self, data):
        if self.udp_conn is None:
            log("Warning: No Udp connection for this tp client, skip sending data to it.")
            return
        self.udp_conn.send_data(data)

    def on_tcp_close_cb(self):
        if self.closed:
            return
        self.stop()

    def on_udp_close_cb(self):
        if self.closed:
            return
        self.stop()

    def stop(self):
        self.closed = True
        if self.tcp_conn is not None:
            self.tcp_conn.stop()
            self.tcp_conn = None
        if self.udp_conn is not None:
            self.udp_conn.stop()
            self.udp_conn = None
        self.tp_close_cb(self)

class CommServerListener(Thread):
    def __init__(self, ip, port, new_connect_cb):
        Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.new_connect_cb = new_connect_cb
        self.running = True

    def run(self):
        # 1. Setup server socket
        while True:
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            except Exception as msg:
                log("Error create socket: %s" % msg)
                server_socket = None
                continue
            try:
                server_socket.bind((self.ip, self.port))
                server_socket.listen(2)
                server_socket.settimeout(1)
                listen_ip = self.ip
                if listen_ip == "":
                    listen_ip = "*"
                log("TCP listening at : %s:%d" % (listen_ip, self.port))
            except Exception as msg:
                log("Error create socket: %s" % msg)
                server_socket.close()
                server_socket = None
                continue
            break

        # 2. Server socket keep listening and accepting client connections
        while self.running:
            try:
                client_sock, client_addr = server_socket.accept()
            except socket.timeout:
                pass
            except:
                raise
            else:
                log("Accept connection from: %s" % '.'.join(map(str, client_addr)))
                self.new_connect_cb(client_sock, client_addr)

        # 3. Server socket close after got quit signal
        server_socket.close()

    def stop(self):
        log("Stop communication server listener.")
        self.running = False

class TransportServer(object):
    def __init__(self, svr_ip, svr_port):
        self.udp_port = 30000
        self.listener = None
        self.client_id_generator = 0
        self.clients = []

    def get_client_count(self):
        return len(self.clients)

    def get_next_udp_port(self):
        self.udp_port += 1
        if self.udp_port > 40000:
            self.udp_port = 30001
        return self.udp_port

    def on_tcp_recv_callback(self, tp, data_bytes):
        data_str = data_bytes.decode()
        log("Tcp data from %d: [%s]" % (tp.tp_id, data_str))
        cmd = json.loads(data_str)
        if cmd["action"] == "broadcast":
            log("Client request to broadcast message")
            for client in self.clients:
                if client != tp:
                    client.send_tcp_data(data_bytes)
        else:
            log("No handling on the data, discard.")

    def on_udp_recv_callback(self, tp, data_bytes):
        #log("Received UDP data %d bytes from %d, dispatch to all other clients" % (len(data_bytes), tp.tp_id))
        for client in self.clients:
            if client != tp:
                client.send_udp_data(data_bytes)

    def on_new_connect_cb(self, tcp_socket, tcp_addr):
        self.client_id_generator += 1
        tp = Transport(self.client_id_generator, self, tcp_socket, tcp_addr,
                       self.on_tcp_recv_callback, self.on_udp_recv_callback, self.on_connection_close_cb)
        self.clients.append(tp)
        tp.start()

    def on_connection_close_cb(self, tp):
        log("Remove client: %d" % tp.tp_id)
        self.clients.remove(tp)

    def start_service(self):
        self.listener = CommServerListener(svr_ip, svr_port, self.on_new_connect_cb)
        self.listener.start()

    def stop_service(self):
        log("Stop listening.")
        self.listener.stop()
        log("Stop service, ask all clients to stop.")
        for tp in self.clients:
            tp.stop()


# This enables communication server to listen on port LISTEN_PORT for incoming connections
LISTEN_IP   = ""
LISTEN_PORT = 2021
LOG_PATH = "/var/log/atto-comm/atto-comm.log"

# Define the signal handler
def signal_handler(sig, frame):
    global service_running
    service_running = False

if __name__ == "__main__":
    svr_ip   = LISTEN_IP
    svr_port = LISTEN_PORT
    service_running = True

    # Register the signal handler for SIGTERM
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    log("Start atto-comm service")
    comm_svr = TransportServer(svr_ip, svr_port)
    comm_svr.start_service()

    while service_running:
        time.sleep(1)

    comm_svr.stop_service()
    sys.exit(0)
