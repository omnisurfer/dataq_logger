from dataclasses import dataclass
from enum import IntEnum
from typing import List
import socket
import logging
import sys
import threading
import time
import random

"""
https://pythonprogramming.net/live-graphs-matplotlib-tutorial/
"""

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style

"""
https://www.dataq.com/products/di-4108-e/
"""


@dataclass()
class DQEnums:
    @dataclass()
    class ID(IntEnum):
        DQCOMMAND = int("0x31415926", 0)
        DQRESPONSE = int("0x21712818", 0)
        DQADCDATA = int("0x14142135", 0)
        DQTHUMBDATA = int("0x17320508", 0)
        DQTHUMBEOF = int("0x22360679", 0)
        DQTHUMBSTREAM = int("0x16180339", 0)
        DQWHCHDR = int("0x05772156", 0)

    @dataclass()
    class Command(IntEnum):
        SYNCSTART = 1
        SYNC = 2
        ROUNDTRIPQUERY = 3
        ROUNDTRIPQUERYACK = 4
        SLAVEIP = 5
        SYNCSTOP = 6
        CONNECT = 10
        DISCONNECT = 11
        KEEPALIVE = 12
        SECONDCOMMAND = 13
        FINDOUTSLAVEDELAY = 15
        SETSLAVEDELAY = 16
        UDPDEBUG = 20
        USBDRIVECOMMAND = 22

    @dataclass()
    class PacketSize(IntEnum):
        PS_16_BYTES_DEFAULT = 0
        PS_32_BYTES = 1
        PS_64_BYTES = 2
        PS_128_BYTES = 3
        PS_256_BYTES = 4
        PS_512_BYTES = 5
        PS_1024_BYTES = 6
        PS_2048_BYTES = 7

    @dataclass()
    class InfoRequests(IntEnum):
        MFG = 0
        MODEL = 1
        FIRMWARE_REV = 2
        DEVICE_STRING = 5
        SERIAL_NO = 6
        SAMPLE_RATE = 9

    @dataclass()
    class DeviceRole(IntEnum):
        MASTER = 0
        SLAVE = 1
        STANDALONE = 2

    @dataclass()
    class Encoding(IntEnum):
        BINARY_DEFAULT = 0
        ASCII = 1


@dataclass()
class DQMasks:
    @dataclass()
    class DQ4108:
        @dataclass()
        class ScanListDefinition:
            @dataclass()
            class AnalogScale:
                # The last four bits represent the values defined in the table on page 44 of the
                # Data Acquisition Communications Protocol pdf. Of the 16 bit command, these bits
                # would be 15:8. The upper bits are unused and marked 0
                __bit_shift = 8
                PN_10V0 = 0 << __bit_shift
                PN_5V0 = 1 << __bit_shift
                PN_2V0 = 2 << __bit_shift
                PN_1V0 = 3 << __bit_shift
                PN_0V5 = 4 << __bit_shift
                PN_0V2 = 5 << __bit_shift

            @dataclass()
            class RateRange:
                __bit_shift = 8
                rate_50KHz = 1 << __bit_shift
                rate_20KHz = 2 << __bit_shift
                rate_10KHz = 3 << __bit_shift
                rate_5KHz = 4 << __bit_shift
                rate_2KHz = 5 << __bit_shift
                rate_1KHz = 6 << __bit_shift
                rate_500Hz = 7 << __bit_shift
                rate_200Hz = 8 << __bit_shift
                rate_100Hz = 9 << __bit_shift
                rate_50Hz = 10 << __bit_shift
                rate_20Hz = 11 << __bit_shift
                rate_10Hz = 12 << __bit_shift

            @dataclass()
            class AnalogIn:
                __bit_shift = 0
                ch1 = 0 << __bit_shift
                ch2 = 1 << __bit_shift
                ch3 = 2 << __bit_shift
                ch4 = 3 << __bit_shift
                ch5 = 4 << __bit_shift
                ch6 = 5 << __bit_shift
                ch7 = 6 << __bit_shift
                ch8 = 7 << __bit_shift

            @dataclass()
            class DigitalIn:
                __bit_shift = 0
                ch1 = 4 << __bit_shift

            @dataclass()
            class CountIn:
                __bit_shift = 0
                ch1 = 6 << __bit_shift


@dataclass()
class DQDataStructures:
    @dataclass()
    class DQ4108:
        @dataclass()
        class BinaryStreamOutput:
            analog1: List[int]
            analog2: List[int]
            analog3: List[int]
            analog4: List[int]
            analog5: List[int]
            analog6: List[int]
            analog7: List[int]
            analog8: List[int]
            digital1: List[int]
            digital2: List[int]

            # channel_carryover_index keeps track of which channel the first byte within the received packet should go
            # to. For example, if three channels are being sampled and the packet size is 4, the first three bytes
            # will line up but the fourth will be the start of another first channel byte. The next received packet
            # will have its first byte start for the second channel.
            channel_packet_carryover_index: int
            cumulative_samples_received: int


@dataclass()
class DQCommandResponseStructures:
    @dataclass
    class DQCommand:
        id: DQEnums.ID  # aka Type
        public_key: int  # aka GroupID
        command: DQEnums.Command
        par1: int
        par2: int
        par3: int
        payload: str

    @dataclass()
    class DQResponse:
        id: DQEnums.ID
        public_key: int
        order: int  # Order of the instrument when used as a member of a sync group
        payload_length: int
        payload: chr

    @dataclass()
    class DQAdcData:
        id: DQEnums.ID
        public_key: int
        order: int
        cumulative_count: int
        payload_length: int
        adc_data: int  # note this should be short but python does not have this a a type...


@dataclass()
class DQPorts:
    # port numbers are from the loggers perspective
    logger_discovery_local_port: int  # this is fixed on the device
    logger_discovery_remote_port: int

    logger_command_local_port: int  # this is fixed on the device
    logger_command_data_client_port: int


@dataclass()
class DQDeviceConfiguration:
    encode: DQEnums.Encoding
    ps: DQEnums.PacketSize
    dec: int
    deca: int
    s_rate: int
    s_list: []
    device_role: DQEnums.DeviceRole
    device_group_order: int
    device_group_key_id: int


class DQDataContainer:
    def __init__(self, device_order, dq_data_structure):
        self.device_order = device_order
        self.dq_data_structure = dq_data_structure


# https://www.loggly.com/ultimate-guide/python-logging-basics/
logging.basicConfig(stream=sys.stderr, level=logging.INFO)


class DataqCommsManager:

    def __init__(self, dq_ports, logger_ip, client_ip):
        self.log = logging.getLogger("DataqCommsManager")

        self.dq_ports = dq_ports
        self.logger_ip = logger_ip
        self.client_ip = client_ip

        # drowan_NOTES_20200618: Only one device used so setting to 1
        self.sync_device_count = 1
        self.receive_timeout_sec = 2

        self.keep_alive_thread_enable = False
        self.keep_alive_thread = None
        self.keep_alive_thread_event = threading.Event()

        self.receive_data_thread_enable = False
        self.receive_data_thread = None
        self.receive_data_handler = None
        self.receive_data_thread_event = threading.Event()

        self.byte_order = 'little'
        self.is_signed = False

        self.device_configuration = None

        self.dataq_group_container = []

        for device_order in range(self.sync_device_count):
            __analog_ch1_list = []
            __analog_ch2_list = []
            __analog_ch3_list = []
            __analog_ch4_list = []
            __analog_ch5_list = []

            __analog_ch6_list = []
            __analog_ch7_list = []
            __analog_ch8_list = []
            __digital_ch1_list = []
            __digital_ch2_list = []
            __carryover_channel_index = 0
            __cumulative_samples_received = 0

            dataq_logger_data = DQDataStructures.DQ4108.BinaryStreamOutput(
                __analog_ch1_list,
                __analog_ch2_list,
                __analog_ch3_list,
                __analog_ch4_list,
                __analog_ch5_list,

                __analog_ch6_list,
                __analog_ch7_list,
                __analog_ch8_list,
                __digital_ch1_list,
                __digital_ch2_list,
                __carryover_channel_index,
                __cumulative_samples_received
            )

            self.dataq_group_container.append(DQDataContainer(device_order, dataq_logger_data))

        """
        # drowan_NOTES_20200624: The variables between this note and the string of ### is
        # used for the C# port that I attempted. I am keeping it here for context.
        # CSharp Code ##########################################################################
        self.device_adc_buffer_size = 10  # 100000
        self.sample_count_received_per_device = [self.sync_device_count]
        self.fill_index = [self.sync_device_count]

        rows, cols = (self.sync_device_count, self.device_adc_buffer_size)
        self.adc_data_buffer = [[0] * cols] * rows

        self.gap_count = 0
        self.b_gap = False
        # CSharp Code ##########################################################################
        """

        """
        UDP Socket Config
        """

        # Where to send the data I think, need to look further into this...
        self.dataq_server_address_and_port = (self.logger_ip, self.dq_ports.logger_command_local_port)

        # UDP Command Socket Setup
        self.udp_command_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.udp_command_socket.settimeout(self.receive_timeout_sec)
        self.client_outbound_address_and_port = ("0.0.0.0", self.dq_ports.logger_command_data_client_port)

        # UDP Response Socket Setup
        self.udp_response_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.udp_response_socket.settimeout(self.receive_timeout_sec)
        self.client_inbound_address_and_port = ("0.0.0.0", self.dq_ports.logger_discovery_remote_port)

    def initialize_socket(self):
        name = "initialize_socket"
        self.log.info(name)
        try:
            self.udp_command_socket.bind(self.client_outbound_address_and_port)
        except socket.error as e:
            self.log.exception(name + ": ")
            return 0

        try:
            self.udp_response_socket.bind(self.client_inbound_address_and_port)
        except socket.error as e:
            self.log.exception(name + ": ")
            return 0

        # drowan_TODO_20200624: test the connection

        # everything went OK
        return 1

    def configure_and_connect_device(self, configuration: DQDeviceConfiguration, receive_data_handler):
        name = "configure_and_connect_device"
        self.log.info(name + ": " + repr(configuration))

        self.device_configuration = configuration

        self.receive_data_handler = receive_data_handler

        scan_list = configuration.s_list

        # configure key, connection, role, group
        dq_command = DQCommandResponseStructures.DQCommand(
            id=DQEnums.ID.DQCOMMAND,
            public_key=self.device_configuration.device_group_key_id,
            command=DQEnums.Command.CONNECT,
            par1=self.dq_ports.logger_discovery_remote_port,
            par2=self.device_configuration.device_role,
            par3=self.device_configuration.device_group_order,
            payload=self.client_ip
        )

        command_ok = self.send_command(dq_command, False)

        if not command_ok:
            self.log.error(name + ": command error")

        # configure encoding
        dq_command.command = DQEnums.Command.SECONDCOMMAND
        dq_command.par1 = 0
        dq_command.par2 = 0
        dq_command.par3 = 0
        dq_command.payload = "encode " + str(int(self.device_configuration.encode)) + "\r"

        self.send_command(dq_command, False)

        # configure packet size
        dq_command.command = DQEnums.Command.SECONDCOMMAND
        dq_command.par1 = 0
        dq_command.par2 = 0
        dq_command.par3 = 0
        dq_command.payload = "ps " + str(int(self.device_configuration.ps)) + "\r"

        self.send_command(dq_command, False)

        # configure srate
        dq_command.command = DQEnums.Command.SECONDCOMMAND
        dq_command.par1 = 0
        dq_command.par2 = 0
        dq_command.par3 = 0
        dq_command.payload = "srate " + str(int(self.device_configuration.s_rate)) + "\r"

        self.send_command(dq_command, False)

        # configure dec
        dq_command.command = DQEnums.Command.SECONDCOMMAND
        dq_command.par1 = 0
        dq_command.par2 = 0
        dq_command.par3 = 0
        dq_command.payload = "dec " + str(int(self.device_configuration.dec)) + "\r"

        self.send_command(dq_command, False)

        # configure deca
        dq_command.command = DQEnums.Command.SECONDCOMMAND
        dq_command.par1 = 0
        dq_command.par2 = 0
        dq_command.par3 = 0
        dq_command.payload = "deca " + str(int(self.device_configuration.deca)) + "\r"

        self.send_command(dq_command, False)

        # configure keep alive
        dq_command.command = DQEnums.Command.SECONDCOMMAND
        dq_command.par1 = 0
        dq_command.par2 = 0
        dq_command.par3 = 0
        dq_command.payload = "keepalive 8000\r"

        self.send_command(dq_command, False)

        for scan_config in scan_list:
            dq_command.payload = "slist " + str(scan_config) + " " + str(
                scan_config | scan_list[scan_config]) + "\r"
            self.log.info("slist config " + dq_command.payload)
            self.send_command(dq_command, False)

        self.keep_alive_thread_enable = True
        self.keep_alive_thread = threading.Thread(target=self.keep_alive_runnable)

        self.keep_alive_thread.start()
        self.keep_alive_thread_event.set()

    def start_acquisition(self):
        name = "start_acquisition"
        self.log.info(name)

        # start the read thread
        self.receive_data_thread_enable = True
        self.receive_data_thread = threading.Thread(target=self.receive_data_runnable)

        self.receive_data_thread.start()
        self.receive_data_thread_event.set()

        # configure key, connection, role, group
        dq_command = DQCommandResponseStructures.DQCommand(
            id=DQEnums.ID.DQCOMMAND,
            public_key=self.device_configuration.device_group_key_id,
            command=DQEnums.Command.SYNCSTART,
            par1=0,
            par2=0,
            par3=0,
            payload="start 0\r"
        )

        command_ok = self.send_command(dq_command, False)

        if not command_ok:
            self.log.error(name + " command error")

    def stop_acquisition(self):
        name = "stop_acquisition"
        self.log.info(name)

        # configure key, connection, role, group
        dq_command = DQCommandResponseStructures.DQCommand(
            id=DQEnums.ID.DQCOMMAND,
            public_key=self.device_configuration.device_group_key_id,
            command=DQEnums.Command.SYNCSTOP,
            par1=0,
            par2=0,
            par3=0,
            payload="stop\r"
        )

        command_ok = self.send_command(dq_command, False)

        if not command_ok:
            self.log.error(name + " command error")

        # drowan_TODO_20200624: find a way to pause the thread?
        self.receive_data_thread_event.clear()

    def disconnect_device(self):
        name = "disconnect_device"
        self.log.info(name)

        # send disconnect command
        dq_command = DQCommandResponseStructures.DQCommand(
            id=DQEnums.ID.DQCOMMAND,
            public_key=self.device_configuration.device_group_key_id,
            command=DQEnums.Command.DISCONNECT,
            par1=0,
            par2=0,
            par3=0,
            payload="disconnect\r"
        )

        command_ok = self.send_command(dq_command, False)

        if not command_ok:
            self.log.error(name + " command error")

        self.keep_alive_thread_enable = False
        self.keep_alive_thread_event.set()
        self.keep_alive_thread.join()

        self.receive_data_thread_enable = False
        self.receive_data_thread_event.set()
        self.receive_data_thread.join()

        self.udp_command_socket.close()
        self.udp_response_socket.close()

    def send_command(self, dq_command: DQEnums.Command, ignore_timeout):
        name = "send_command"
        self.log.info(name + ": " + repr(dq_command))

        command_string = ''
        id_byte = dq_command.id.to_bytes(4, byteorder=self.byte_order, signed=self.is_signed)
        public_key_byte = dq_command.public_key.to_bytes(4, byteorder=self.byte_order, signed=self.is_signed)
        command_byte = dq_command.command.to_bytes(4, byteorder=self.byte_order, signed=self.is_signed)
        par1_byte = dq_command.par1.to_bytes(4, byteorder=self.byte_order, signed=self.is_signed)
        par2_byte = dq_command.par2.to_bytes(4, byteorder=self.byte_order, signed=self.is_signed)
        par3_byte = dq_command.par3.to_bytes(4, byteorder=self.byte_order, signed=self.is_signed)

        command_string = id_byte + \
                         public_key_byte + \
                         command_byte + \
                         par1_byte + \
                         par2_byte + \
                         par3_byte + \
                         dq_command.payload.encode('utf-8')

        self.udp_command_socket.sendto(command_string, self.dataq_server_address_and_port)

        buffer_size = 1024

        # this is for commands that don't echo
        if ignore_timeout is True:
            return 1
        else:
            try:
                response_from_logger = self.udp_response_socket.recv(buffer_size)
                response_ok = self.process_response(response_from_logger)

                if not response_ok:
                    self.log.error(name + ": got bad response")
                    return 0
                else:
                    return 1

            except socket.error as e:
                self.log.exception(name + ": ")
                self.log.warning(name + ": Code to handle exception needed!")
                return 0

    def keep_alive_runnable(self):
        name = "keep_alive_runnable"
        self.log.info(name)

        while True:

            if self.keep_alive_thread_enable is False:
                self.log.info(name + ": told to exit thread")
                break
            else:
                self.log.info(name + ": waiting for keep alive event")
                self.keep_alive_thread_event.wait()
                self.log.info(name + ": got keep alive event")

            # configure key, connection, role, group
            dq_command = DQCommandResponseStructures.DQCommand(
                id=DQEnums.ID.DQCOMMAND,
                public_key=self.device_configuration.device_group_key_id,
                command=DQEnums.Command.KEEPALIVE,
                par1=0,
                par2=0,
                par3=0,
                payload="keepalive\r"
            )

            command_ok = self.send_command(dq_command, True)

            if not command_ok:
                self.log.error(name + " command error")

            # just chose 6 seconds
            time.sleep(6)

        self.log.info(name + ": exiting...")

    def receive_data_runnable(self):
        name = "receive_data_runnable"

        while True:

            if self.receive_data_thread_enable is False:
                self.log.info(name + ": told to exit thread")
                break
            else:
                self.log.info(name + ": waiting for receive event")
                self.receive_data_thread_event.wait()
                self.log.info(name + ": got receive event")

            try:
                response = self.udp_response_socket.recv(1024)
                self.process_response(response)

                # print("Channel 2: ", self.dataq_group_container[0].dq_data_structure.analog2.pop())
                data = self.dataq_group_container[0].dq_data_structure.analog2.pop()
                self.receive_data_handler(self.dataq_group_container)
            except socket.error as e:
                self.log.exception(name + ": ")
                self.log.warning(name + ": Code to handle exception needed!")

        self.log.info(name + ": exiting...")

    """
    # process_response is a port of the parse_udp function demonstrated in the 4208UDP
    # C# example provide by dataq
    # The port is not used since it was difficult to follow. I recreated the functionality in a manner that
    # I believe will work for multiple loggers. This would need to be tested at a future date.
    def process_response_csharp(self, response_from_logger):
        print("processing response")

        # myId = 0
        # myKey = 0
        # myOrder = 0
        # myRunningDataCount = 0
        # myPayloadSamples = 0
        myNumOfChan = 0
        myRealigned = 0

        response_id = int.from_bytes(response_from_logger[0:4], byteorder=self.byte_order)
        response_public_key = 0
        responsding_device_order = 0
        response_payload_length = 0

        # check if the response carriers a group ID
        if len(response_from_logger) > 8:
            response_public_key = int.from_bytes(response_from_logger[4:8], byteorder=self.byte_order)
        else:
            response_public_key = 0

        # logger order for multi logger setups
        if len(response_from_logger) > 12:
            responsding_device_order = int.from_bytes(response_from_logger[8:12], byteorder=self.byte_order)
            # drowan_NOTES_20200618: TBD what this is used for...
            myRealigned = responsding_device_order
        else:
            responsding_device_order = 0
            myRealigned = 0

        # this may cap the number of devices, ignore orders beyond the count?
        if responsding_device_order >= self.sync_device_count:
            responsding_device_order = self.sync_device_count
        if responsding_device_order < 0:
            responsding_device_order = 0

        # the "switch" to process the packets
        if response_id == DQEnums.ID.DQADCDATA:
            print("Got DQADCDATA")
            # drowan_TODO_20200618: working on DQADCDATA portion of port, line 575
            cumulative_sample_count_reported = int.from_bytes(response_from_logger[12:16], byteorder=self.byte_order)
            payload_sample_count = int.from_bytes(response_from_logger[16:20], byteorder=self.byte_order)

            missing_sample_count = cumulative_sample_count_reported - self.sample_count_received_per_device[
                responsding_device_order]

            # create fake data to fill any gaps
            if missing_sample_count != 0:
                self.gap_count += 1
                self.b_gap = True

                for i in range(cumulative_sample_count_reported - self.sample_count_received_per_device[
                    responsding_device_order]):
                    self.adc_data_buffer[responsding_device_order][
                        self.fill_index[responsding_device_order]] = 3  # event markers???
                    self.fill_index[responsding_device_order] += 1

                    if self.fill_index[responsding_device_order] >= self.device_adc_buffer_size:
                        self.fill_index[responsding_device_order] = 0
                self.sample_count_received_per_device[responsding_device_order] = cumulative_sample_count_reported

            # the payload length is defined by the chosen packet size. The bytes sent are divided amongst the number
            # of channels being read in
            for i in range(payload_sample_count):
                sample_start_index = 20 + i * 2
                n = int.from_bytes(response_from_logger[sample_start_index:sample_start_index + 4],
                                   byteorder=self.byte_order)
                m = int('0xfffc', 0)

                result = int(n & m)

                print("n raw: ", n, " m: ", m, " result: ", result)

                self.adc_data_buffer[responsding_device_order][self.fill_index[responsding_device_order]] = result

                self.fill_index[responsding_device_order] += 1
                if self.fill_index[responsding_device_order] >= self.device_adc_buffer_size:
                    self.fill_index[responsding_device_order] = 0

                self.sample_count_received_per_device[responsding_device_order] = self.sample_count_received_per_device[
                                                                                      responsding_device_order] + payload_sample_count

            # print(self.adc_data_buffer[responsding_device_order][self.fill_index[responsding_device_order]])

            return 1

        elif response_id == DQEnums.ID.DQRESPONSE:
            print("Got DQRESPONSE")
            payload_sample_count = int.from_bytes(response_from_logger[12:16], byteorder=self.byte_order)
            payload = response_from_logger[16:16 + payload_sample_count]
            payload = payload.decode("utf-8").replace('\r', '')
            print("response: ", payload)
            return 0
        else:
            print("Got unknown command!")

        return 0
    """

    def process_response(self, response_from_logger):
        name = "process_response"
        self.log.info(name)

        response_id = int.from_bytes(response_from_logger[0:4], byteorder=self.byte_order)
        response_public_key = 0
        responding_device_order = 0

        # check if the response carriers a group ID
        if len(response_from_logger) > 8:
            response_public_key = int.from_bytes(response_from_logger[4:8], byteorder=self.byte_order)
        else:
            response_public_key = 0

        # logger order for multi logger setups
        if len(response_from_logger) > 12:
            responding_device_order = int.from_bytes(response_from_logger[8:12], byteorder=self.byte_order)
        else:
            responding_device_order = 0

        # this may cap the number of devices, ignore orders beyond the count?
        if responding_device_order >= self.sync_device_count:
            responding_device_order = self.sync_device_count
        if responding_device_order < 0:
            responding_device_order = 0

        if response_id == DQEnums.ID.DQADCDATA:
            self.log.info(name + ": processing DQADCDATA")

            # init to something so its not a null reference
            current_channel_index = 0

            cumulative_sample_count_from_device = int.from_bytes(response_from_logger[12:16], byteorder=self.byte_order)
            payload_sample_count_from_device = int.from_bytes(response_from_logger[16:20], byteorder=self.byte_order)

            missing_sample_count = \
                cumulative_sample_count_from_device - \
                self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received

            # create fake data to fill any gaps
            if missing_sample_count != 0:
                # drowan_TODO_20200624: make code to deal with missing samples
                self.log.warning(name + ": missing samples detected! Code to mitigate not implemented yet!")

            # the payload length is defined by the chosen packet size. The bytes sent are divided amongst the number
            # of channels being read in
            for payload_index in range(payload_sample_count_from_device):
                sample_start_index = 20 + payload_index * 2
                raw_bytes = int.from_bytes(response_from_logger[sample_start_index:sample_start_index + 4],
                                           byteorder=self.byte_order)
                byte_modifier = int('0xfffc', 0)

                result = int(raw_bytes & byte_modifier)

                current_channel_index = (payload_index + self.dataq_group_container[
                    responding_device_order].dq_data_structure.channel_packet_carryover_index) % len(
                    self.device_configuration.s_list)

                self.log.debug(
                    name + ": " +
                    "\n\tcurrent_channel_index: " + str(current_channel_index) +
                    "\n\tpayload_index: " + str(payload_index) +
                    "\n\tchannel_carryover_index: " + str(self.dataq_group_container[responding_device_order].dq_data_structure.channel_packet_carryover_index)
                )

                current_channel_in_list = list(self.device_configuration.s_list.keys())[current_channel_index]

                if current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch1:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog1.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch2:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog2.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch3:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog3.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch4:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog4.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch5:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog5.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch6:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog6.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch7:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog7.append(result)

                elif current_channel_in_list == DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch8:
                    self.dataq_group_container[responding_device_order].dq_data_structure.analog8.append(result)

                else:
                    self.log.warning(name + ": channel not found in list: " + current_channel_in_list)

            self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received = \
                self.dataq_group_container[
                    responding_device_order].dq_data_structure.cumulative_samples_received + payload_sample_count_from_device

            self.dataq_group_container[
                responding_device_order].dq_data_structure.channel_packet_carryover_index = current_channel_index + 1

            self.log.debug(
                name + ": " +
                "\n\tcumulative_sample_count_from_device: " + str(cumulative_sample_count_from_device) +
                "\n\tcumulative_samples_received: " + str(self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received)
            )

            return 1

        elif response_id == DQEnums.ID.DQRESPONSE:
            self.log.info(name + ": processing DQRESPONSE")
            payload_sample_count = int.from_bytes(response_from_logger[12:16], byteorder=self.byte_order)
            payload = response_from_logger[16:16 + payload_sample_count]
            payload = payload.decode("utf-8").replace('\r', '')
            self.log.debug(name + ": response: " + payload)

            # drowan_TODO_20200624: create code that actually checks against the responses
            self.log.warning(name + ": code to assess response not implemented yet!")
            return 1
        else:
            self.log.warning(name + ": rejecting unknown command")
            return 0


def data_consumption_handler(data_container: DQDataContainer):
    name = "consume_data"
    print(name)

    print("ch 2: " + str(int(data_container[0].dq_data_structure.analog2.pop())))


# style.use('fivethirtyeight')
fig, axes = plt.subplots(4, 1)


def animation_function(frame_number):

    graph_data = []

    current_index = frame_number % 100

    #"""
    for x in range(100):
        graph_data.append([x, random.random()])

    xs = []
    ys = []

    for line in graph_data:
        xs.append(line[0])
        ys.append(line[1])

    # https://stackoverflow.com/questions/31726643/how-do-i-get-multiple-subplots-in-matplotlib
    # https://matplotlib.org/examples/animation/basic_example.html
    #"""

    for ax in axes:
        # ax.clear()
        ax.set_ylim(0, 1)

    # axes[0].plot(xs, ys, 'r')
    axes[1].plot(xs, ys, 'g')
    axes[2].plot(xs, ys, 'b')
    axes[3].plot(xs, ys, 'k')


def main():
    print("Entering main")

    # debug plot code
    ani = animation.FuncAnimation(fig, animation_function, interval=10, save_count=50)
    plt.show()

    input("Press enter to continue...")

    return 0

    # define ports, IPs, keys
    dq_ports = DQPorts(
        logger_discovery_local_port=1235,
        logger_discovery_remote_port=1234,
        logger_command_local_port=51235,
        logger_command_data_client_port=1427
    )

    logger_ip = "192.168.1.209"
    client_ip = "192.168.1.3"

    my_group_key_id = int("0x06681444", 0)

    # define channel config
    scan_list_configuration = {
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch1: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0,
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch3: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0,
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch4: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0,
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch2: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0
    }

    dataq_comms = DataqCommsManager(dq_ports, logger_ip, client_ip)

    if dataq_comms.initialize_socket():
        print("socket initialized")
    else:
        return -1

    # define scan rate - refer to page 47
    desired_sample_rate_hz = 600
    dividend = 60e6
    decimation_factor = 10  # 512  # 1 reported value per 512 samples
    decimation_multiplier = 1  # multiply factor by 1
    srate_setting = int(dividend / (decimation_factor * decimation_multiplier * desired_sample_rate_hz))  # max is 65535

    # create configuration
    dataq_config = DQDeviceConfiguration(
        encode=DQEnums.Encoding.BINARY_DEFAULT,
        ps=DQEnums.PacketSize.PS_16_BYTES_DEFAULT,
        dec=decimation_factor,
        deca=decimation_multiplier,
        s_rate=srate_setting,
        s_list=scan_list_configuration,
        device_role=DQEnums.DeviceRole.MASTER,
        device_group_key_id=my_group_key_id,
        device_group_order=0
    )

    dataq_comms.configure_and_connect_device(dataq_config, data_consumption_handler)

    # set device time
    # TBD

    # sync start/start acquisition
    dataq_comms.start_acquisition()

    time.sleep(60)
    # stop
    dataq_comms.stop_acquisition()

    # disconnect
    dataq_comms.disconnect_device()


if __name__ == "__main__":
    main()
