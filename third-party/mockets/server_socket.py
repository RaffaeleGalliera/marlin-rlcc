import socket
import time

HOST = "10.0.2.1"  # The server's hostname or IP address
PORT = 65432  # The port used by the server

BUFFER_SIZE = 1024

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind((HOST, PORT))
s.listen()


times = []
best = 100
worst = 0

for x in range(1, 20):
    print(f"Test no. {x}")
    print("Waiting for a connection...")
    conn, addr = s.accept()
    print(f"Connected by {addr}")
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
    print("Total Bytes received: " + str(total_bytes_received) + " - File received successfully\n")
    finish = (time.time() - start)
    print(f"Finished in {finish}s")
    if finish < best:
        best = finish
    if finish > worst:
        worst = finish
    times.append(finish)
        
    f.close()
    conn.close()
s.close()


print(f"Average Time taken: {sum(times)/len(times)}")
print(f"Best Time taken: {best}")
print(f"Worst Time taken: {worst}")
    
    
