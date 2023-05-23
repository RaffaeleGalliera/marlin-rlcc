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

setLogLevel('info')

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
    def __init__(self, mininet):
        self.mininet = mininet

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

    def exposed_update_link(self, delay=None, bandwidth=None, loss=None):
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
        # Update latency of the shared link
        src_link, dst_link = self.get_links()

        src_link.config(delay=delay_start, bw=bandwidth_start, loss=loss_start)
        dst_link.config(delay=delay_start, bw=bandwidth_start, loss=loss_start)

        time.sleep(interval_sec)

        src_link.config(delay=new_delay, bw=new_bandwidth, loss=new_loss)
        dst_link.config(delay=new_delay, bw=new_bandwidth, loss=new_loss)

        return f'Changed link from {delay_start} {bandwidth_start}Mbit {loss_start}%' \
               f' to {new_delay} {new_bandwidth}Mbit {new_loss}%'

if __name__ == '__main__':
    topo = DumbbellTopology()
    net = Mininet(topo=topo, controller=Controller, waitConnected=True)
    net.start()

    service = classpartial(MininetService, net)
    server = ThreadedServer(service, port=18861)
    info('*** Starting Mininet Service\n')
    server.start()
    info('*** Shutting down Mininet Service\n')
