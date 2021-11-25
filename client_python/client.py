#!/usr/bin/env python
import socket
import sys
import time
from threading import Thread


class Connection(Thread):
    SVR_PORT = 2021
    PACKET_LIMIT = 1024 * 1024

    def __init__(self, svr_ip):
        Thread.__init__(self)
        self.svr_ip = svr_ip
        self.client_socket = None
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
        n_received = 0
        while n_received < lens:
            remaining = lens - n_received
            buf_len = min(remaining, 4096)
            bytes_block = self.client_socket.recv(buf_len)
            data += bytes_block.decode()
            n_received = len(data)
        return data

    def run(self):
        print("Connect to communication server at %s:%d" % (self.svr_ip, self.SVR_PORT))
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(1)
        self.client_socket.connect((self.svr_ip, self.SVR_PORT))

        while self.running:
            try:
                client_pdu = self.recv_data()
                if not client_pdu:
                    print("Connnection closed by peer, quit this connection.")
                    break
            except socket.timeout:
                pass
            except socket.error as v:
                errorcode = v[0]
                print("Socket recv exception: %s" % str(errorcode))
                break
            else:
                print("Got message: [%s]" % client_pdu)

        print("Client Connection exit.")
        self.client_socket.close()
        self.client_socket = None

    def is_closed(self):
        return self.client_socket is None
        
    def stop_running(self):
        self.running = False

if __name__ == "__main__":
    svr_ip = ""
    svr_port = 2021

    if len(sys.argv) >= 3:
        svr_port = int(sys.argv[2])
    if len(sys.argv) >= 2:
        svr_ip = sys.argv[1]
    else:
        print("usage: %s <svr_ip> [port]" % sys.argv[0])
        print("")
        sys.exit(2)

    conn = Connection(svr_ip)
    conn.start()

    print("Type 'quit' to quit or anything else as a message send to other clients")
    while True:
        in_str = input()
        if conn.is_closed():
            print("Connection to server is closed, quit now")
            break
        if in_str == "quit":
            print("exit now......")
            conn.stop_running()
            break;
        elif len(in_str) > 0:
            print("Send to other clients: [%s]" % in_str)
            conn.send_data(in_str)
    print("Done!")
