#!/usr/bin/env python

import socket
import sys
import time
from datetime import datetime
from threading import Thread

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

class ClientWorkerConnection(Thread):
    PACKET_LIMIT = 1024 * 1024

    def __init__(self, client_socket, client_addr, comm_svr):
        Thread.__init__(self)
        self.comm_svr = comm_svr
        #Register self from communication server
        self.comm_svr.add_client(self)
        self.client_socket = client_socket
        self.client_socket.settimeout(1)
        self.client_addr = client_addr
        self.running = True

    def send_data(self, data_str):
        data_len = len(data_str)
        assert data_len != 0, "Try to send empty string shouldn't happen."
        if data_len > self.PACKET_LIMIT:
            data_len = self.PACKET_LIMIT
            data_str = data_str[:data_len]
        header = "%12d" % data_len
        self.client_socket.send(header.encode())
        self.client_socket.send(data_str.encode())

    def recv_data(self):
        data = ""
        header = self.client_socket.recv(12)
        if not header:
            return ""
        lens = int(header.decode())
        # Receiving data block
        n_received = 0
        while n_received < lens:
            remaining = lens - n_received
            buf_len = min(remaining, 4096)
            bytes_block = self.client_socket.recv(buf_len)
            data += bytes_block.decode()
            n_received = len(data)
        return data

    def run(self):
        self.send_data("Welcome!")
        while self.running:
            try:
                client_pdu = self.recv_data()
                if not client_pdu:
                    log("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                log("Socket recv exception: %s" % str(e))
                break
            else:
                log("Got message from client: %s" % client_pdu)
                #Queue into comm svr for dispatching
                self.comm_svr.new_PDU_from_client(self, client_pdu)

        log("ClientWorkerConnection exit.")
        self.client_socket.close()
        #Unregister self from communication server
        self.comm_svr.remove_client(self)

    def stop_running(self):
        self.running = False

class CommServerListener(Thread):
    def __init__(self, ip, port, comm_svr):
        Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.comm_svr = comm_svr
        self.running = True

    def run(self):
        # 1. Setup server socket
        while True:
            try:
                server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            except Exception as msg:
                log("Error create socket: %s", msg)
                server_socket = None
                continue
            try:
                server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
                client = ClientWorkerConnection(client_sock, client_addr, self.comm_svr)
                client.start()

        # 3. Server socket close after got quit signal
        server_socket.close()

    def stop(self):
        log("Stop communication server listener.")
        self.running = False

class CommServer(object):
    def __init__(self, svr_ip, svr_port):
        self.clients = []
        self.listener = CommServerListener(svr_ip, svr_port, self)

    def add_client(self, client):
        log("Add new client: %s" % str(client))
        self.clients.append(client)

    def remove_client(self, client):
        log("Remove client: %s" % str(client))
        self.clients.remove(client)

    def new_PDU_from_client(self, client, pdu):
        log("PDU dispathing ......")
        for cli in self.clients:
            if cli != client:
                cli.send_data(pdu)
        log("PDU dispathing Done!")

    def get_client_count(self):
        return len(self.clients)

    def stop_service(self):
        log("Stop listening.")
        self.listener.stop()
        log("Stop service, ask all clients to stop.")
        for cli in self.clients:
            cli.stop_running()

    def start_service(self):
        self.listener.start()


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
    comm_svr = CommServer(svr_ip, svr_port)
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
