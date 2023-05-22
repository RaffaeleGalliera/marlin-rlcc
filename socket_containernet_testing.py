import logging
import sys
import time
from envs.utils import traffic_generator
import docker

logging.basicConfig(level=logging.INFO)

def connect_containers():
    docker_client = docker.from_env()
    logging.info("Connecting to Containernet Background Traffic Gen")
    try:
        docker_traffic_gen = docker_client.containers.get("mn.lh2")
    except docker.errors.NotFound as e:
        logging.error("Docker background traffic generator not found, new attempt...")
    except docker.errors.APIError as e:
        logging.error("Server error background traffic generator, new attempt...")

    logging.info("Connecting to Containernet Background Traffic Receiver")
    try:
        docker_traffic_receiver = docker_client.containers.get("mn.rh2")
    except docker.errors.NotFound as e:
        logging.error("Docker traffic receiver not found, new attempt...")
    except docker.errors.APIError as e:
        logging.error("Server error traffic receiver, new attempt...")

    logging.info("Connecting to Containernet Sender")
    try:
        docker_file_sender = docker_client.containers.get("mn.lh1")
    except docker.errors.NotFound as e:
        logging.error("Docker traffic receiver not found, new attempt...")
    except docker.errors.APIError as e:
        logging.error("Server error traffic receiver, new attempt...")

    return docker_traffic_gen, docker_traffic_receiver, docker_file_sender
    
def start_traffic_generator(traffic_script, docker_traffic_gen):
    logging.info("Starting Background traffic")
    logging.info(f"Script used: {traffic_script}")
    docker_traffic_gen.exec_run(f"./mgen {traffic_script}", detach=True)

def start_traffic_receiver(docker_traffic_receiver):
    logging.info("Starting traffic receiver")
    docker_traffic_receiver.exec_run('./mgen event "listen udp 4311,4312,4600" event "listen tcp 5311,5312"', detach=True)
    logging.info(f"Receiver started!")

def start_background_traffic(traffic_script, docker_traffic_gen, docker_traffic_receiver):
    start_traffic_receiver(docker_traffic_receiver)
    start_traffic_generator(traffic_script, docker_traffic_gen)

def cleanup_background_traffic(docker_traffic_gen, docker_traffic_receiver):
    shutdown_mgen = ['sh', '-c',
                    "ps -ef | grep 'mgen' | grep -v grep | awk '{print $2}' | xargs -r kill -9"]

    logging.info("Closing Background traffic connection")
    docker_traffic_gen.exec_run(shutdown_mgen)

    logging.info("Closing BG Traffic receiver")
    docker_traffic_receiver.exec_run(shutdown_mgen)

traffic_gen = traffic_generator.TrafficGenerator(link_capacity_mbps=2)
d_traffic_gen, d_traffic_rec, d_sender = connect_containers()

while True:
    traffic_script = traffic_gen.generate_fixed_script(receiver_ip="10.0.2.2")
    #Starting background traffic
    logging.info("Launching Traffic gen script")
    start_background_traffic(traffic_script, d_traffic_gen, d_traffic_rec)
    #Starting TCP connection testing
    d_sender.exec_run(f"python3 /home/app/client_socket.py")
    cleanup_background_traffic(d_traffic_gen, d_traffic_rec)
