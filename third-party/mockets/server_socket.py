import socket
import time
import logging

HOST = "10.0.2.1"  # The server's hostname or IP address
PORT = 65432  # The port used by the server

BUFFER_SIZE = 1024

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()

#Time metrics initial values
times = []
best = 100
worst = 0

#TCP connection performance testing
for x in range(1, 20):
    logging.info(f"Test no. {x}")
    logging.info("Waiting for a connection...")
    conn, addr = s.accept()
    logging.info(f"Connected by {addr}")
    start = time.time()
    file_path = "/home/app/test_file_received.iso"
    total_bytes_received = 0
    f = open(file_path, "wb")
    while total_bytes_received < 3*1024*1024:
        data = conn.recv(BUFFER_SIZE)
        if not data:
            break
        f.write(data)
        total_bytes_received += BUFFER_SIZE
    logging.info("Total Bytes received: " + str(total_bytes_received) + " - File received successfully\n")
    finish = (time.time() - start)
    logging.info(f"Finished in {finish}s")
    if finish < best:
        best = finish
    if finish > worst:
        worst = finish
    times.append(finish)
        
    f.close()
    conn.close()
s.close()

logging.info(f"Average Time taken: {sum(times)/len(times)}")
logging.info(f"Best Time taken: {best}")
logging.info(f"Worst Time taken: {worst}")
