import logging
import sys
import argparse
from envs.utils import traffic_generator
import docker
import rpyc
import netifaces as ni
import pandas as pd

logging.basicConfig(level=logging.INFO)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay-start", type=str, default="500ms")
    parser.add_argument("--bandwidth-start", type=float, default=1.)
    parser.add_argument("--loss-start", type=float, default=0.)
    parser.add_argument("--new-delay", type=str, default="125ms")
    parser.add_argument("--new-bandwidth", type=float, default=.256)
    parser.add_argument("--new-loss", type=float, default=3.)
    parser.add_argument("--variation-interval", type=int, default=15)
    parser.add_argument("--number-of-runs", type=int, default=100)
    parser.add_argument("--bg-traffic-receiver-ip", type=str, default="10.0.2.2")

    return parser.parse_args()


def get_container(name:str = None, docker_client = None):
    try:
        container = docker_client.containers.get(name)
    except docker.errors.NotFound as e:
        logging.info(f"Container {name} not found. Have you started Containernet?")
        sys.exit(1)

    logging.info(f"Container {name} found!")

    return container


def connect_containers():
    docker_client = docker.from_env()

    logging.debug("Connecting to File Sender")
    file_sender_container = get_container("mn.lh1", docker_client)

    logging.debug("Connecting to File Receiver")
    file_receiver_container = get_container("mn.rh1", docker_client)

    logging.debug("Connecting to Background Traffic Generator")
    bg_traffic_gen_container = get_container("mn.lh2", docker_client)

    logging.debug("Connecting to Background Traffic Receiver")
    bg_traffic_receiver_container = get_container("mn.rh2", docker_client)

    logging.info("Containers connected!")

    return bg_traffic_gen_container, bg_traffic_receiver_container, file_sender_container, file_receiver_container


def start_traffic_generator(traffic_script, docker_traffic_gen):
    logging.debug(f"Script used: {traffic_script}")
    docker_traffic_gen.exec_run(f"./mgen {traffic_script}", detach=True)


def start_traffic_receiver(docker_traffic_receiver):
    logging.debug("Starting traffic receiver")
    docker_traffic_receiver.exec_run('./mgen event "listen udp 4311,4312,4600" event "listen tcp 5311,5312"', detach=True)
    logging.debug(f"Receiver started!")


def start_background_traffic(script, docker_traffic_gen, docker_traffic_receiver):
    cleanup_containers(docker_traffic_gen, docker_traffic_receiver)
    start_traffic_receiver(docker_traffic_receiver)
    start_traffic_generator(script, docker_traffic_gen)


def cleanup_containers(docker_traffic_gen, docker_traffic_receiver):
    shutdown_mgen = ['sh', '-c',
                    "ps -ef | grep 'mgen' | grep -v grep | awk '{print $2}' | xargs -r kill -9"]

    logging.debug("Closing Background traffic connection")
    docker_traffic_gen.exec_run(shutdown_mgen)

    logging.debug("Closing BG Traffic receiver")
    docker_traffic_receiver.exec_run(shutdown_mgen)


if __name__ == "__main__":
    args = parse_args()
    traffic_script_gen = traffic_generator.TrafficGenerator(
        link_capacity_mbps=args.bandwidth_start
    )

    bg_traffic_gen, bg_traffic_receiver, file_sender, file_receiver = connect_containers()
    mininet_connection = rpyc.connect(ni.ifaddresses('docker0')[ni.AF_INET][0]['addr'], 18861)

    results = []
    for i in range(args.number_of_runs):
        # Start the file receiver in stream mode
        logs_receiver = file_receiver.exec_run(f"python3 /home/app/server_socket.py", stream=True)

        for line in logs_receiver.output:
            if line == b"INFO:root:Waiting for a connection...\n":
                logging.info("File receiver ready!")
                break

        # Connect to Containernet and start the link update
        timed_link_update = rpyc.async_(mininet_connection.root.timed_link_update)
        future_timed_link_update = timed_link_update(delay_start=args.delay_start,
                                                     bandwidth_start=args.bandwidth_start,
                                                     loss_start=args.loss_start,
                                                     new_delay=args.new_delay,
                                                     new_bandwidth=args.new_bandwidth,
                                                     new_loss=args.new_loss,
                                                     interval_sec=args.variation_interval)

        # Start the background traffic
        traffic_script = traffic_script_gen.generate_fixed_script(receiver_ip=args.bg_traffic_receiver_ip)
        start_background_traffic(traffic_script, bg_traffic_gen, bg_traffic_receiver)

        # Start the file transfer
        file_sender.exec_run(f"python3 /home/app/client_socket.py", detach=True)

        # Gather the future when it's ready
        logging.info("Waiting for link to be changed")
        future_timed_link_update.wait()

        # Update the link characteristics and start the new background traffic
        logging.debug("Updated link characteristics")
        traffic_script = traffic_script_gen.generate_script_new_link(
            receiver_ip=args.bg_traffic_receiver_ip,
            factor=args.new_bandwidth / args.bandwidth_start,
        )
        start_background_traffic(traffic_script, bg_traffic_gen, bg_traffic_receiver)

        for line in logs_receiver.output:
            tokens = line.decode('utf-8').split(':')
            
            if len(tokens)==4 and tokens[2] == "finished_in":
                results.append(float(tokens[3]))
                logging.info(f"Run {i} finished in {float(tokens[3])} seconds!")
                break

    logging.info(pd.Series(results).describe())
