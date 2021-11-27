#!/usr/bin/env python

import socket
import sys
import time
from datetime import datetime
from threading import Thread
import json

# This enables communication server to listen on port LISTEN_PORT for incoming connections
LISTEN_IP   = ""
LISTEN_PORT = 2021

def log(msg):
    # Removed these two lines for debugging
    if len(msg) > 1024:
        msg = msg[:1016] + "[......]"

    t_now = datetime.now()
    fmt_msg = "%s %s\n" % (str(t_now), msg)
    print(fmt_msg)
    try:
        f = open('comm_server.log', 'a+')
        f.write(fmt_msg)
        f.close()
    except IOError:
        pass

class TcpConnection(Thread):
    PACKET_LIMIT = 1024 * 1024

    def __init__(self, socket, client_addr, recv_cb):
        Thread.__init__(self)
        self.recv_cb = recv_cb
        self.socket = socket
        self.socket.settimeout(1)
        self.client_addr = client_addr
        self.running = False

    def send_data(self, data_str):
        data_len = len(data_str)
        assert data_len != 0, "Try to send empty string shouldn't happen."
        if data_len > self.PACKET_LIMIT:
            data_len = self.PACKET_LIMIT
            data_str = data_str[:data_len]
        header = "%12d" % data_len
        self.socket.send(header.encode())
        self.socket.send(data_str.encode())

    def recv_data(self):
        data = ""
        header = self.socket.recv(12)
        if not header:
            return ""
        lens = int(header.decode())
        # Receiving data block
        n_received = 0
        while n_received < lens:
            remaining = lens - n_received
            buf_len = min(remaining, 4096)
            bytes_block = self.socket.recv(buf_len)
            data += bytes_block.decode()
            n_received = len(data)
        return data

    def run(self):
        self.send_data('{"pdu_type": "Welcome!", "data":""}') #Debugging purpose
        self.running = True
        while self.running:
            try:
                data_str = self.recv_data()
                if not data_str:
                    log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                log("Socket recv exception: %s" % str(e))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(data_str)
                else:
                    log("XXX: Discard data due to callback not available")

        log("TcpConnection exit.")
        self.socket.close()
        self.socket = None

    def stop(self):
        self.running = False
        #TODO: wait up to 1 second until thread quit


class UdpConnection(Thread):
    PACKET_LIMIT = 1024 * 1024

    def __init__(self, socket, recv_cb):
        Thread.__init__(self)
        self.recv_cb = recv_cb
        self.socket = socket
        self.socket.settimeout(1)
        self.running = False

    def send_data(self, data_str):
        data_len = len(data_str)
        assert data_len != 0, "Try to send empty string shouldn't happen."
        if data_len > self.PACKET_LIMIT:
            data_len = self.PACKET_LIMIT
            data_str = data_str[:data_len]
        header = "%12d" % data_len
        self.socket.send(header.encode())
        self.socket.send(data_str.encode())

    def recv_data(self):
        data = ""
        header = self.socket.recv(12)
        if not header:
            return ""
        lens = int(header.decode())
        # Receiving data block
        n_received = 0
        while n_received < lens:
            remaining = lens - n_received
            buf_len = min(remaining, 4096)
            bytes_block = self.socket.recv(buf_len)
            data += bytes_block.decode()
            n_received = len(data)
        return data

    def run(self):
        self.running = True
        while self.running:
            try:
                data_str = self.recv_data()
                if not data_str:
                    log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                log("Socket recv exception: %s" % str(e))
                break
            else:
                if self.recv_cb is not None:
                    self.recv_cb(data_str)
                else:
                    log("XXX: Discard data due to callback not available")

        log("UdpConnection exit.")
        self.socket.close()
        self.socket = None

    def stop(self):
        self.running = False
        #TODO: wait up to 1 second until thread quit

class Transport(object):
    def __init__(self, tp_svr, tcp_socket, tcp_addr, tcp_recv_cb, udp_recv_cb):
        self.tcp_conn = None
        self.udp_conn = None
        self.tp_svr = tp_svr
        self.tcp_socket = tcp_socket
        self.tcp_addr = tcp_addr
        self.tcp_recv_cb = tcp_recv_cb
        self.udp_recv_cb = udp_recv_cb

    def start(self):
        self.tcp_conn = TcpConnection(self.tcp_socket, self.tcp_addr, self.on_tcp_data_recv_callback)
        self.tcp_conn.start()

    def on_tcp_data_recv_callback(self, data_str):
        cmd = json.loads(data_str)
        if cmd["pdu_type"] == "create_udp_channel":
            log("Client request to create UDP channel")
            udp_port = self.creat_udp_channel()
            reply = {
                      "pdu_type": "create_udp_channel",
                      "data": "%d" % udp_port
                    }
            self.send_tcp_data(json.dumps(reply))
        else:
            self.tcp_recv_cb(self, data_str)

    def on_udp_data_recv_callback(self, data_str):
        self.udp_recv_cb(self, data_str)

    def creat_udp_channel(self):
        if self.udp_conn is not None:
            log("UDP socket channel created already, Ignore this request")
            return
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
        udp_port = self.tp_svr.get_next_udp_port()
        while True:
            try:
                udp_socket.bind(("", udp_port))
                break
            except socket.error:
                log("Bind on port %d failed, try another port" % udp_port)
                udp_port = self.tp_svr.get_next_udp_port()
                continue
        self.udp_conn = UdpConnection(udp_socket, self.on_udp_data_recv_callback)
        self.udp_conn.start()
        return udp_port

    def send_tcp_data(self, data_str):
        self.tcp_conn.send_data(data_str)

    def send_udp_data(self, data_str):
        self.udp_conn.send_data(data_str)

    def stop(self):
        if self.tcp_conn is not None:
            self.tcp_conn.stop()
            self.tcp_conn = None
        if self.udp_conn is not None:
            self.udp_conn.stop()
            self.udp_conn = None


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
                log("Error create socket: %s", msg)
                server_socket = None
                continue
            try:
                server_socket.bind((self.ip, self.port))
                server_socket.listen(2)
                server_socket.settimeout(1)
                log("Listen at : %s:%d" % (self.ip, self.port))
            except Exception as msg:
                log("Error create socket: %s", msg)
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
        self.clients = []

    def remove_client(self, client):
        log("Remove client: %s" % str(client))
        self.clients.remove(client)

    def get_client_count(self):
        return len(self.clients)

    def get_next_udp_port(self):
        self.udp_port += 1
        if self.udp_port > 40000:
            self.udp_port = 30001
        return self.udp_port

    def on_tcp_recv_callback(self, tp, data_str):
        log("Tcp data from %s: [%s]" % (str(tp), data_str))

    def on_udp_recv_callback(self, tp, data_str):
        log("Ucp data from %s: [%s]" % (str(tp), data_str))

    def on_new_connect_cb(self, tcp_socket, tcp_addr):
        tp = Transport(self, tcp_socket, tcp_addr, self.on_tcp_recv_callback, self.on_udp_recv_callback)
        self.clients.append(tp)
        tp.start()

    def start_service(self):
        self.listener = CommServerListener(svr_ip, svr_port, self.on_new_connect_cb)
        self.listener.start()

    def stop_service(self):
        log("Stop listening.")
        self.listener.stop()
        log("Stop service, ask all clients to stop.")
        for tp in self.clients:
            tp.stop()


if __name__ == "__main__":
    svr_ip   = LISTEN_IP
    svr_port = LISTEN_PORT

    if len(sys.argv) >= 3:
        svr_port = int(sys.argv[2])
    if len(sys.argv) >= 2:
        svr_ip = sys.argv[1]
        
    print("usage: %s [svr_ip(default:all local IPs)] [port(default 2021)]" % sys.argv[0])
    print("")

    log("Start communication service at %s:%d" % (svr_ip, svr_port))
    comm_svr = TransportServer(svr_ip, svr_port)
    comm_svr.start_service()

    print("Type 'exit' to quit communication server")
    while True:
        in_str = input()
        if in_str == "exit":
            print("communication server exit now!")
            break;
        elif in_str == "client":
            print("Number of clients: %d" % comm_svr.get_client_count())

    comm_svr.stop_service()
    sys.exit(0)
