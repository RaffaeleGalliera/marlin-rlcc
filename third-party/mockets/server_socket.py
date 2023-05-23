import socket
import time
import logging
import argparse


logging.basicConfig(level=logging.INFO)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip-address", type=str, default="10.0.2.1")
    parser.add_argument("--port", type=int, default=65433)
    parser.add_argument("--buffer-size", type=int, default=1024)
    parser.add_argument("--file-path", type=str, default="/home/app/test_file_received.iso")

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Try to bind the socket until it is released
    while True:
        try:
            s.bind((args.ip_address, args.port))
        except OSError as e:
            logging.info("Waiting for the socket to be released...")
            time.sleep(1)
            continue
        else:
            break
    s.listen()

    logging.info("Waiting for a connection...")
    conn, addr = s.accept()

    logging.info(f"Connected with {addr}")
    start = time.time()

    # Receive data until the connection is closed
    f = open(args.file_path, "wb")
    while True:
        data = conn.recv(args.buffer_size)
        if not data:
            break
        f.write(data)

    logging.info(f"finished_in:{(time.time() - start)}")
    f.close()
    conn.close()
    s.close()
