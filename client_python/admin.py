#!/usr/bin/env python
import sys
from libpyclient import Transport

if __name__ == "__main__":
    svr_ip = "127.0.0.1"
    svr_port = 2021

    if len(sys.argv) >= 3:
        svr_port = int(sys.argv[2])
    if len(sys.argv) >= 2:
        svr_ip = sys.argv[1]

    tp = Transport(svr_ip, svr_port)
    tp.connect()

    print("Type 'help' to show valid commands")
    while True:
        in_str = input()
        if len(in_str) == 0:
            continue

        if in_str == "help":
            print("Unsurpported command [%s], ignored. Supported commands:" % in_str)
            print("    udp          - Ask server to create UDP channel")
            print("    totcp:<data> - Send tcp data to server for broadcasting")
            print("    toudp:<data> - Send udp data to server")
            print("    <data>       - Send general data to server")
            print("    quit         - Quit")
        elif in_str == "quit":
            print("exit now......")
            tp.close()
            break;
        elif in_str == "udp":
            print("Ask server to create UDP channel......")
            tp.create_udp_channel()
        elif in_str.startswith("totcp:"):
            print("Send tcp data to server for broadcasting......")
            tp.broadcast_tcp_message(in_str)
        elif in_str.startswith("toudp:"):
            print("Send udp data to server......")
            tp.send_udp_data(in_str.encode())
        else:
            print("Send general data to server......")
            tp.send_tcp_data(in_str)

    tp.close()
    print("Done!")
