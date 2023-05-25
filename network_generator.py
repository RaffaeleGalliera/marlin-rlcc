import time
import typing

from mininet.cli import CLI
from mininet.net import Containernet, Mininet
from mininet.node import Node, Controller
from mininet.link import TCIntf
from mininet.link import TCLink
from mininet.topo import Topo
from mininet.log import info, setLogLevel

from mininet.node import (Node, Docker, Host, OVSKernelSwitch,
                          DefaultController, Controller, OVSSwitch, OVSBridge)

import rpyc
from rpyc.utils.server import ThreadedServer
from rpyc.utils.helpers import classpartial
import docker
import envs.utils.traffic_generator as tg

setLogLevel('info')


def cleanup_background_traffic(sender, receiver):
    shutdown_mgen = ['sh', '-c',
                     "ps -ef | grep 'mgen' | grep -v grep | awk '{print $2}' | xargs -r kill -9"]

    sender.exec_run(shutdown_mgen)
    receiver.exec_run(shutdown_mgen)

def start_traffic(sender, receiver, traffic_script):
    receiver.exec_run('./mgen event "listen udp 4311,4312,4600" event "listen tcp 5311,5312"', detach=True)
    sender.exec_run(f"./mgen {traffic_script}", detach=True)


class LinuxRouter(Node):
    # A Node with IP forwarding enabled.
    # pylint: disable=arguments-differ

    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        # Enable forwarding on the router
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()


class DumbbellTopology(Topo):
    # Simple Dumbell topology example.

    def build(self):
        # Create custom topo

        r0 = self.addNode('r0', cls=LinuxRouter, ip='10.0.1.254/24')

        # Add switches
        info('*** Add switches\n')
        ls1 = self.addSwitch('ls1')
        rs1 = self.addSwitch('rs1')

        # Add hosts
        lh1 = self.addHost('lh1',
                           cls=Docker,
                           ip='10.0.1.1/24',
                           defaultRoute='via 10.0.1.254',
                           dimage='mockets:0.1')

        lh2 = self.addHost('lh2',
                           cls=Docker,
                           ip='10.0.1.2/24',
                           defaultRoute='via 10.0.1.254',
                           dimage='mgen:0.1')

        rh1 = self.addHost('rh1',
                           cls=Docker,
                           ip='10.0.2.1/24',
                           defaultRoute='via 10.0.2.254',
                           dimage='mockets:0.1')

        rh2 = self.addHost('rh2',
                           cls=Docker,
                           ip='10.0.2.2/24',
                           defaultRoute='via 10.0.2.254',
                           dimage='mgen:0.1')

        # Add links
        info('*** Connect the switches to the router\n')
        self.addLink(ls1, r0, intf=TCIntf, delay='50ms', bw=2,
                     params2={'ip': '10.0.1.254/24'})
        self.addLink(rs1, r0, intf=TCIntf, params2={'ip': '10.0.2.254/24'})

        info("*** Connect the switches to the hosts\n")
        self.addLink(lh1, ls1, intf=TCIntf)
        self.addLink(lh2, ls1, intf=TCIntf)
        self.addLink(rh1, rs1, intf=TCIntf)
        self.addLink(rh2, rs1, intf=TCIntf)

class MininetService(rpyc.Service):
    def __init__(self, mininet, sender, receiver, script_gen):
        self.mininet = mininet
        self.sender = sender
        self.receiver = receiver
        self.script_gen = script_gen

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        self.mininet.stop()
        return "Mininet stopped"

    def get_links(self, node_1='ls1', node_2='r0'):
        links = self.mininet.getNodeByName(node_1).connectionsTo(
            self.mininet.getNodeByName(node_2)
        )

        return links[0][0], links[0][1]

    def exposed_manual_link_update(self, delay=None, bandwidth=None, loss=None):
        # Update latency of the shared link
        src_link, dst_link = self.get_links()

        src_link.config(delay=delay, bw=bandwidth, loss=loss)
        dst_link.config(delay=delay, bw=bandwidth, loss=loss)

        return f'Changed link to {delay} {bandwidth}Mbit {loss}%'

    def exposed_timed_link_update(self,
                                  delay_start=None,
                                  bandwidth_start=None,
                                  loss_start=None,
                                  new_delay=None,
                                  new_bandwidth=None,
                                  new_loss=None,
                                  interval_sec=None):
        # Resets to normal state and then generate a new script
        traffic_script = self.script_gen.generate_fixed_script(receiver_ip="10.0.2.2")
        cleanup_background_traffic(self.sender, self.receiver)
        start_traffic(self.sender, self.receiver, traffic_script)

        # Update latency of the shared link
        src_link, dst_link = self.get_links()

        src_link.config(delay=delay_start, bw=bandwidth_start, loss=loss_start)
        dst_link.config(delay=delay_start, bw=bandwidth_start, loss=loss_start)

        time.sleep(interval_sec)

        src_link.config(delay=new_delay, bw=new_bandwidth, loss=new_loss)
        dst_link.config(delay=new_delay, bw=new_bandwidth, loss=new_loss)

        traffic_script = self.script_gen.generate_script_new_link(
            receiver_ip="10.0.2.2",
            factor=new_bandwidth / bandwidth_start,
        )
        cleanup_background_traffic(self.sender, self.receiver)
        start_traffic(self.sender, self.receiver, traffic_script)

        return f'Changed link from {delay_start} {bandwidth_start}Mbit {loss_start}%' \
               f' to {new_delay} {new_bandwidth}Mbit {new_loss}%'

if __name__ == '__main__':
    topo = DumbbellTopology()
    net = Mininet(topo=topo, controller=Controller, waitConnected=True)
    net.start()
    docker_client = docker.from_env()

    traffic_script_gen = tg.TrafficGenerator()
    bg_sender = docker_client.containers.get("mn.lh2")
    bg_receiver = docker_client.containers.get("mn.rh2")

    service = classpartial(MininetService, net, bg_sender, bg_receiver, traffic_script_gen)
    server = ThreadedServer(service, port=18861)
    info('*** Starting Mininet Service\n')
    server.start()
    info('*** Shutting down Mininet Service\n')
