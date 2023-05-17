import random
import logging
import itertools

class TrafficPattern:
    def __init__(self,
                 packets: float,
                 protocol: str,
                 port: int,
                 ):
        self.packets = packets
        self.protocol = protocol
        self.port = port


class TrafficGenerator:
    def __init__(self,
                 period_duration_seconds: int = 10,
                 link_capacity_mbps: float = 1,
                 seed: int = 9,
                 ):

        self.period_duration_seconds = period_duration_seconds
        self.seed = seed
        self.n_episode = 0
        self.link_capacity_kilo_bytes_ps = link_capacity_mbps * 125
        self.tcp_elephant = TrafficPattern(self.link_capacity_kilo_bytes_ps * .8,
                                           "TCP",
                                           5311)
        self.udp_elephant = TrafficPattern(self.link_capacity_kilo_bytes_ps * .4,
                                           "UDP",
                                           4311)
        self.tcp_mice = TrafficPattern(self.link_capacity_kilo_bytes_ps * .001332,
                                       "TCP",
                                       5312)
        self.udp_mice = TrafficPattern(self.link_capacity_kilo_bytes_ps * .2,
                                       "UDP",
                                       4312)
        self.extra_udp = TrafficPattern(self.link_capacity_kilo_bytes_ps * .208,
                                        "UDP",
                                        4600)
        self.mice_flows_kbs = self.link_capacity_kilo_bytes_ps * .08

        self.traffic_patterns = (self.udp_elephant, self.tcp_elephant, self.udp_elephant, self.extra_udp)
        self.training_patterns = list(itertools.permutations(self.traffic_patterns))
        self.evaluation_pattern = self.traffic_patterns

        self.current_patterns = self.traffic_patterns

        random.seed(9)


    def reset_elephant_to_default(self):
        self.tcp_elephant.packets = self.link_capacity_kilo_bytes_ps * .8
        self.udp_elephant.packets = self.link_capacity_kilo_bytes_ps * .4
        self.extra_udp.packets = self.link_capacity_kilo_bytes_ps * .208


    def reset_mice_to_default(self):
        self.udp_mice.packets = self.link_capacity_kilo_bytes_ps * .2
        self.tcp_mice.packets = self.link_capacity_kilo_bytes_ps * .001332
        self.mice_flows_kbs = self.link_capacity_kilo_bytes_ps * .08


    def random_packets_number(self):
        return random.randint(int(self.link_capacity_kilo_bytes_ps * .05),
                              int(self.link_capacity_kilo_bytes_ps * .8))
    def generate_random_script(self, receiver_ip):
        logging.info("Choosing Training Pattern for next episode")

        self.tcp_elephant.packets = self.random_packets_number()
        self.udp_elephant.packets = self.random_packets_number()
        self.extra_udp.packets = self.random_packets_number()
        self.reset_mice_to_default()

        pattern = [self.udp_elephant, self.tcp_elephant, self.udp_elephant, self.extra_udp]
        random.shuffle(pattern)
        self.current_patterns = tuple(pattern)

        return self.generate_script(self.current_patterns, receiver_ip)

    def generate_fixed_script(self, receiver_ip):
        logging.info("Choosing Eval Pattern for next episode")

        # Set to default values
        self.reset_elephant_to_default()
        self.reset_mice_to_default()
        self.current_patterns = self.evaluation_pattern

        pattern = [self.udp_elephant, self.tcp_elephant, self.udp_elephant, self.extra_udp]
        self.current_patterns = tuple(pattern)

        return self.generate_script(self.current_patterns, receiver_ip)

    def generate_script_new_link(self, receiver_ip, factor):
        # UDP elephant traffic is excluded when changing the link capacity
        self.tcp_elephant.packets *= factor
        self.tcp_mice.packets *= factor
        self.udp_mice.packets *= factor
        self.extra_udp.packets *= factor
        self.mice_flows_kbs *= factor

        pattern = [self.tcp_elephant, self.extra_udp, self.tcp_elephant, self.extra_udp]
        self.current_patterns = tuple(pattern)

        return self.generate_script(self.current_patterns, receiver_ip)

    def generate_script(self, chosen_list, receiver_ip):
        logging.info("Traffic Order")
        logging.info([f"{pattern.protocol} - {pattern.packets}" for pattern in chosen_list])

        slot_0 = f"0.0 ON 1 {chosen_list[0].protocol} SRC {chosen_list[0].port} " \
                 f"DST " \
                 f"{receiver_ip}/{chosen_list[0].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[0].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        slot_1 = f"2.0 ON 2 {chosen_list[1].protocol} SRC {chosen_list[1].port} " \
                 f"DST " \
                 f"{receiver_ip}/{chosen_list[1].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[1].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        slot_2 = f"4.0 ON 3 {chosen_list[2].protocol} SRC {chosen_list[2].port} " \
                 f"DST " \
                 f"{receiver_ip}/{chosen_list[2].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[2].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        slot_3 = f"6.0 ON 4 {chosen_list[3].protocol} SRC {chosen_list[3].port} " \
                 f"DST " \
                 f"{receiver_ip}/{chosen_list[3].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[3].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        mice_1 = f"0.0 ON 5 TCP SRC {self.tcp_mice.port} DST {receiver_ip}/" \
                 f"{self.tcp_mice.port} " \
                 f"PERIODIC [{self.tcp_mice.packets} 32768]"

        mice_2 = f"0.0 ON 6 UDP SRC {self.udp_mice.port} DST {receiver_ip}/" \
                 f"{self.udp_mice.port} " \
                 f"BURST [REGULAR 2.5 PERIODIC [{self.udp_mice.packets} 1024] " \
                 f"FIXED 0.333]"

        return f"event \"{slot_0}\" event \"{slot_1}\" event \"{slot_2}\" " \
               f"event \"{slot_3}\" event \"{mice_1}\" event \"{mice_2}\""
