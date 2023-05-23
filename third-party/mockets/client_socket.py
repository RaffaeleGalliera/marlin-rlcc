import socket
import logging
import argparse
import time

logging.basicConfig(level=logging.INFO)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip-address", type=str, default="10.0.2.1")
    parser.add_argument("--port", type=int, default=65433)
    parser.add_argument("--buffer-size", type=int, default=1024)
    parser.add_argument("--file-path", type=str, default="/home/app/test_file.iso")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            s.connect((args.ip_address, args.port))
        except ConnectionRefusedError as e:
            logging.info("Waiting for the socket to be released...")
            time.sleep(1)
            continue
        else:
            break

    with open(args.file_path, "rb") as f:
        while True:
            data = f.read(args.buffer_size)
            if not data:
                break
            s.sendall(data)
        f.close()
    s.close()
