import logging
import sys
import os
import argparse
from envs.utils import traffic_generator
import docker
import rpyc
import netifaces as ni
import pandas as pd
import pyshark
import multiprocessing
from statistics import mean

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

    logging.info("Containers connected!")

    return file_sender_container, file_receiver_container


def capture_interface(output_file, interface):
    captured_interface = pyshark.LiveCapture(interface=interface, output_file=output_file)

    logging.info("Interface " + interface + " captured correctly")

    return captured_interface


def capture_packets(capture, stop_event):
    for packet in capture.sniff_continuously():
        if stop_event.is_set():
            break


def count_episodic_retransmissions(captured_packets_file):
    retransmissions = 0
    capture_retransmissions = pyshark.FileCapture(captured_packets_file, display_filter="tcp.analysis.retransmission")

    for packet in capture_retransmissions:
        retransmissions += 1

    return retransmissions


def measure_episodic_rtt(captured_packets_file):
    rtt = 0
    captured_packets = pyshark.FileCapture(captured_packets_file)
    for packet in captured_packets:
        if 'TCP' in packet:
            tcp = packet['TCP']
            try:
                rtt += float(packet.tcp.analysis_ack_rtt)
            except AttributeError:
                rtt += 0
    
    return rtt


def stop_capture(capture):
    capture.close()


if __name__ == "__main__":
    args = parse_args()
    traffic_script_gen = traffic_generator.TrafficGenerator(
        link_capacity_mbps=args.bandwidth_start
    )

    file_sender, file_receiver = connect_containers()
    mininet_connection = rpyc.connect(ni.ifaddresses('docker0')[ni.AF_INET][0]['addr'], 18861)

    results = []
    episodic_retransmissions = []
    episodic_rtt = []
    stop_event = multiprocessing.Event()
    for i in range(args.number_of_runs):
        # Start the file receiver in stream mode
        capture_ls1 = capture_interface("outputLs1.pcap", 'ls1-eth2')
        capture_rs1 = capture_interface("outputRs1.pcap", 'rs1-eth1')

        #Start packets capture
        capture_process_ls1 = multiprocessing.Process(target=capture_packets, args=(capture_ls1, stop_event))
        capture_process_rs1 = multiprocessing.Process(target=capture_packets, args=(capture_rs1, stop_event))
        capture_process_ls1.start()
        capture_process_rs1.start()

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

        # Start the file transfer
        file_sender.exec_run(f"python3 /home/app/client_socket.py", detach=True)

        # Gather the future when it's ready
        logging.info("Waiting for link to be changed")
        future_timed_link_update.wait()
        logging.debug("Updated link characteristics")

        for line in logs_receiver.output:
            tokens = line.decode('utf-8').split(':')
            
            if len(tokens)==4 and tokens[2] == "finished_in":
                results.append(float(tokens[3]))
                logging.info(f"Run {i} finished in {float(tokens[3])} seconds!")
                break
        
        # Stop the packets capture on both interfaces and calculate 
        # episodic retransmission and rtt
        stop_capture(capture_ls1)
        stop_capture(capture_rs1)
        stop_event.set()
        capture_process_ls1.join()
        capture_process_rs1.join()
        capture_process_ls1.terminate()
        capture_process_rs1.terminate()
        episodic_retransmissions.append(count_episodic_retransmissions("outputLs1.pcap") + count_episodic_retransmissions("outputRs1.pcap"))
        episodic_rtt.append(measure_episodic_rtt("outputLs1.pcap") + measure_episodic_rtt("outputRs1.pcap"))
        os.remove("outputLs1.pcap")
        os.remove("outputRs1.pcap")

    logging.info(pd.Series(results).describe())

    #Just for debugging
    print(episodic_retransmissions)
    print(mean(episodic_retransmissions))
    print(episodic_rtt)
    print(mean(episodic_rtt))
