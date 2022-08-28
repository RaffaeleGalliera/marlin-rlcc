from paramiko import SSHClient
from scp import SCPClient
import logging
import sys
import time
logging.basicConfig(level=logging.INFO)


def connect(ssh, ssh_traffic_gen):
    logging.info("Connecting to Traffic Gen")
    ssh_traffic_gen.connect("192.168.2.40", username="raffaele",
                            password="armageddon12345")

    logging.info("Connecting to Receiver")
    ssh.connect("192.168.1.17", username="marlin", password="nomads")

    logging.info("Connecting SCP")
    scp = SCPClient(ssh.get_transport())
    return scp


def clean(ssh, ssh_traffic_gen):
    logging.info("Closing Background traffic gen")
    ssh_traffic_gen.close()

    logging.info("Closing Receiver")
    ssh.close()


for x in range(0, 10):
    ssh_traffic_gen = SSHClient()
    ssh_traffic_gen.load_system_host_keys()

    ssh = SSHClient()
    ssh.load_system_host_keys()

    scp = connect(ssh, ssh_traffic_gen)
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
    clean(ssh_traffic_gen, ssh)
