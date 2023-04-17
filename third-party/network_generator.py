from mininet.cli import CLI
from mininet.net import Containernet, Mininet
from mininet.node import Node, Controller
from mininet.link import TCIntf
from mininet.topo import Topo
from mininet.log import info, setLogLevel

from mininet.node import (Node, Docker, Host, OVSKernelSwitch,
                          DefaultController, Controller, OVSSwitch, OVSBridge)

setLogLevel('info')


def pings(mn):
    mn.pingAll()


def update_lat(self, lat):
    # Update latency of the shared link
    net = self.mn
    links = net.getNodeByName('ls1').connectionsTo(net.getNodeByName('r0'))

    srcLink = links[0][0]
    dstLink = links[0][1]

    srcLink.config(delay=lat)
    dstLink.config(delay=lat)


def update_bw(self, bandwidth):
    # Update latency of the shared link
    net = self.mn
    links = net.getNodeByName('ls1').connectionsTo(net.getNodeByName('r0'))

    srcLink = links[0][0]
    dstLink = links[0][1]

    srcLink.config(bw=int(bandwidth))
    dstLink.config(bw=int(bandwidth))


def cli(mn):
    mn.pingAll()
    CLI(mn)


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


CLI.do_updateLat = update_lat
CLI.do_updateBw = update_bw

topo = DumbbellTopology()
net = Mininet(topo=topo, controller=Controller, waitConnected=True)
net.start()
cli(net)
net.stop()

# tests = { 'cli': cli }
topos = {'dumbell': (lambda: DumbbellTopology())}
