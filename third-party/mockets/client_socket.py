import socket

BUFFER_SIZE = 1024

HOST = "10.0.2.1"  # The server's hostname or IP address
PORT = 65432  # The port used by the server

filename = "/home/app/test_file.iso"

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    with open(filename, "rb") as f:
        total_bytes_sent = 0
        while total_bytes_sent < 3*1024*1024:
            data = f.read(BUFFER_SIZE)
            if not data:
                break
            s.sendall(data)
            total_bytes_sent += BUFFER_SIZE
    print("File sent successfully")
    f.close()


    s.close()