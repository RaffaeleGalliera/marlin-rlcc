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
    def __init__(self, seed, n_envs):
        self.seed = seed
        self.n_envs = n_envs
        super().__init__()


    def build(self):

        for i in range(self.n_envs):
            rank = (self.seed + i) * 10
            print(rank)
            # Create custom topology
            r0 = self.addNode(f'r{rank}', cls=LinuxRouter, ip=f'10.0.{rank}.254/24')

            # Add switches
            info('*** Add switches\n')
            ls1 = self.addSwitch(f'ls{rank}')
            rs1 = self.addSwitch(f'rs{rank}')

            # Add hosts
            lh1 = self.addHost(f'lh{rank}',
                               cls=Docker,
                               ip=f'10.0.{rank}.1/24',
                               defaultRoute=f'via 10.0.{rank}.254',
                               dimage='mockets:0.1')

            lh2 = self.addHost(f'lh{rank + 1}',
                               cls=Docker,
                               ip=f'10.0.{rank}.2/24',
                               defaultRoute=f'via 10.0.{rank}.254',
                               dimage='mgen:0.1')

            rh1 = self.addHost(f'rh{rank}',
                               cls=Docker,
                               ip=f'10.0.{rank + 1}.1/24',
                               defaultRoute=f'via 10.0.{rank + 1}.254',
                               dimage='mockets:0.1')

            rh2 = self.addHost(f'rh{rank + 1}',
                               cls=Docker,
                               ip=f'10.0.{rank + 1}.2/24',
                               defaultRoute=f'via 10.0.{rank + 1}.254',
                               dimage='mgen:0.1')

            # Add links
            info('*** Connect the switches to the router\n')
            self.addLink(ls1, r0, intf=TCIntf, delay='50ms', bw=2,
                         params2={'ip': f'10.0.{rank}.254/24'})
            self.addLink(rs1, r0, intf=TCIntf, params2={'ip': f'10.0.{rank + 1}.254/24'})

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

    def exposed_update_link(self,
                            delay=None,
                            bandwidth=None,
                            loss=None,
                            node_1='ls1',
                            node_2='r0'):
        # Update latency of the shared link
        src_link, dst_link = self.get_links(node_1=node_1, node_2=node_2)

        src_link.config(delay=delay, bw=bandwidth, loss=loss)
        dst_link.config(delay=delay, bw=bandwidth, loss=loss)

        return f'Changed link to {delay} {bandwidth}Mbit {loss}%'

if __name__ == '__main__':
    topo = DumbbellTopology(seed=9, n_envs=3)
    net = Mininet(topo=topo, controller=Controller, waitConnected=True)
    net.start()

    service = classpartial(MininetService, net)
    server = ThreadedServer(service, port=18861)
    info('*** Starting Mininet Service\n')
    server.start()
    info('*** Shutting down Mininet Service\n')
