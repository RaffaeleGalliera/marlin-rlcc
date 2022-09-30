import random
import logging


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
                 seed: int = 9,
                 ):

        self.period_duration_seconds = period_duration_seconds
        self.seed = seed
        self.tcp_elephant = TrafficPattern(200, "TCP", 5311)
        self.udp_elephant = TrafficPattern(100, "UDP", 4311)

        self.tcp_mice = TrafficPattern(0.333, "TCP", 5312)
        self.udp_mice = TrafficPattern(52, "UDP", 4312)

        self.extra_mice = TrafficPattern(50, "UDP", 4600)

        self.traffic_patterns = [self.udp_elephant, self.tcp_elephant, self.udp_elephant, self.extra_mice]

        self.evaluation_patterns = self.traffic_patterns
        self.current_patterns = self.traffic_patterns

        random.seed(9)

    def generate_training_script(self):
        logging.info("Choosing Random Pattern for next episode")

        while self.current_patterns != self.evaluation_patterns:
            self.current_patterns = random.sample(self.traffic_patterns, 4)

        return self.generate_script(self.current_patterns)

    def generate_evaluation_script(self):
        logging.info("Choosing Eval Pattern for next episode")
        self.current_patterns = self.evaluation_patterns

        return self.generate_script(self.current_patterns)


    def generate_script(self, chosen_list):
        logging.info("Traffic Order")
        logging.info([f"{pattern.protocol} - {pattern.packets}" for pattern in chosen_list])

        slot_0 = f"0.0 ON 1 {chosen_list[0].protocol} SRC {chosen_list[0].port} " \
                 f"DST " \
                 f"192.168.1.40/{chosen_list[0].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[0].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        slot_1 = f"2.0 ON 2 {chosen_list[1].protocol} SRC {chosen_list[1].port} " \
                 f"DST " \
                 f"192.168.1.40/{chosen_list[1].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[1].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        slot_2 = f"4.0 ON 3 {chosen_list[2].protocol} SRC {chosen_list[2].port} " \
                 f"DST " \
                 f"192.168.1.40/{chosen_list[2].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[2].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        slot_3 = f"6.0 ON 4 {chosen_list[3].protocol} SRC {chosen_list[3].port} " \
                 f"DST " \
                 f"192.168.1.40/{chosen_list[3].port} BURST [" \
                 f"REGULAR " \
                 f"8.0 PERIODIC [{chosen_list[3].packets} 1024] FIXED 2.0] " \
                 f"TTL 64"

        mice_1 = f"0.0 ON 5 TCP SRC {self.tcp_mice.port} DST 192.168.1.40/" \
                 f"{self.tcp_mice.port} " \
                 f"PERIODIC [{self.tcp_mice.packets} 32768]"

        mice_2 = f"0.0 ON 6 UDP SRC {self.udp_mice.port} DST 192.168.1.40/" \
                 f"{self.udp_mice.port} " \
                 f"BURST [REGULAR 2.5 PERIODIC [{self.udp_mice.packets} 1024] " \
                 f"FIXED 0.333]"

        return f"event \"{slot_0}\" event \"{slot_1}\" event \"{slot_2}\" " \
               f"event \"{slot_3}\" event \"{mice_1}\" event \"{mice_2}\""





