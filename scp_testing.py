from paramiko import SSHClient, AutoAddPolicy
from scp import SCPClient
import logging
import sys
import time
logging.basicConfig(level=logging.INFO)


def connect(ssh, ssh_traffic_gen, ssh_receiver):
    logging.info("Connecting to Traffic Gen Receiver")
    ssh_receiver.connect("192.168.1.40", username="nomads", password="nomads")

    time.sleep(1)

    logging.info("Connecting to Traffic Gen")
    ssh_traffic_gen.connect("192.168.2.40", username="raffaele",
                            password="armageddon12345")

    logging.info("Connecting to Receiver")
    ssh.connect("192.168.1.17", username="marlin", password="nomads")

    logging.info("Connecting SCP")
    scp = SCPClient(ssh.get_transport())
    return scp


def clean(ssh, ssh_traffic_gen, ssh_receiver):
    logging.info("Closing Background traffic Receiver")
    ssh_receiver.close()

    logging.info("Closing Background traffic gen")
    ssh_traffic_gen.close()

    logging.info("Closing Receiver")
    ssh.close()


for x in range(0, 10):
    ssh_traffic_gen = SSHClient()
    ssh_traffic_gen.set_missing_host_key_policy(AutoAddPolicy())

    ssh_receiver = SSHClient()
    ssh_receiver.set_missing_host_key_policy(AutoAddPolicy())

    ssh = SSHClient()
    ssh.set_missing_host_key_policy(AutoAddPolicy())

    scp = connect(ssh, ssh_traffic_gen, ssh_receiver)
    logging.info("Launching Traffic gen Receiver script")
    ssh_receiver.exec_command(
        "mgen inpuT /home/nomads/Muddasar-mgen/receiver.mgen nolog",
        get_pty=True)

    time.sleep(1)

    logging.info("Launching Traffic gen script")
    ssh_traffic_gen.exec_command(
        "/Users/raffaele/Documents/IHMC/mgen/makefiles/mgen inpuT "
        "/Users/raffaele/Documents/IHMC/evaluation_generator_100MB.mgen",
        get_pty=True)
    logging.info(f"Test no. {x + 1}")
    start = time.time()
    scp.put("third-party/rl-baselines3-zoo/test_file.iso")
    logging.info(f"Finished in {(time.time() - start)}s")
    scp.close()
    clean(ssh_traffic_gen, ssh, ssh_receiver)
