#!/usr/bin/env python
import json
from libpyclient import Transport
import sys

def update_user_info(tp):
    ui = {
        "user_id": "admin",
        "user_name": "admin",
        "user_domain": "na"
    }
    ui_str = json.dumps(ui)
    tp.client_update_user(ui_str)

def update_status(tp):
    status = {
        "scene_id": "-1",
        "scene_pos": "0",
        "speed": "0"
    }
    status_str = json.dumps(status)
    tp.client_update_status(status_str)

if __name__ == "__main__":
    svr_ip = "127.0.0.1"
    svr_port = 2021

    if len(sys.argv) >= 3:
        svr_port = int(sys.argv[2])
    if len(sys.argv) >= 2:
        svr_ip = sys.argv[1]

    # 1. Connect to server
    tp = Transport(svr_ip, svr_port)
    tp.connect()

    # 2. Tell server I'm the admin
    update_user_info(tp)

    # 3. Tell server I'm not in any scene
    update_status(tp)

    # 4. Tell server to create UDP channel
    tp.create_udp_channel()

    print("Type 'help' to show valid commands")
    while True:
        in_str = input()
        if len(in_str) == 0:
            continue

        if in_str == "help":
            print("Unsurpported command [%s], ignored. Supported commands:" % in_str)
            print("    list         - List all clients")
            print("    totcp:<data> - Send tcp data to server for broadcasting")
            print("    toudp:<data> - Send udp data to server")
            print("    <data>       - Send general data to server")
            print("    quit         - Quit")
        elif in_str == "quit":
            print("exit now......")
            tp.close()
            break;
        elif in_str == "list":
            print("List of all clients:")
            tp.list_clients();
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
