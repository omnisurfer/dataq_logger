from dataclasses import dataclass
from enum import IntEnum
from typing import List
import socket


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
                PN_10V0 = 1 << __bit_shift
                PN_5V0 = 2 << __bit_shift
                PN_2V0 = 3 << __bit_shift
                PN_1V0 = 4 << __bit_shift
                PN_0V5 = 5 << __bit_shift
                PN_0V2 = 6 << __bit_shift

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

            channel_carryover_index: int
            cumulative_samples_received: int


class DQDataContainer:
    def __init__(self, device_order, dq_data_structure):
        self.device_order = device_order
        self.dq_data_structure = dq_data_structure


@dataclass
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


@dataclass
class DQPorts:
    # port numbers are from the loggers perspective
    logger_discovery_local_port: int  # this is fixed on the device
    logger_discovery_remote_port: int

    logger_command_local_port: int  # this is fixed on the device
    logger_command_data_client_port: int


class DataqCommsManager:

    def __init__(self, dq_ports, logger_ip):
        self.dq_ports = dq_ports

        # drowan_NOTES_20200618: TBD sync device count
        self.sync_device_count = 5
        self.device_adc_buffer_size = 10  # 100000
        self.receive_timeout_sec = 2

        self.byte_order = 'little'
        self.is_signed = False

        self.sample_count_received_per_device = [self.sync_device_count]
        self.fill_index = [self.sync_device_count]

        rows, cols = (self.sync_device_count, self.device_adc_buffer_size)
        self.adc_data_buffer = [[0] * cols] * rows

        self.gap_count = 0
        self.b_gap = False

        self.scan_list_configuration = []
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
        UDP Socket Code
        """
        # drowan_TODO_20200618: Code needed to deal with exceptions.
        # THIS IS VERY MUCH DEBUG/PROOF OF CONCEPT CODE THAT NEEDS WORK.
        self.udp_command_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.udp_command_socket.settimeout(self.receive_timeout_sec)

        self.dataq_server_address_and_port = (logger_ip, self.dq_ports.logger_command_local_port)
        self.client_outbound_address_and_port = ("0.0.0.0", self.dq_ports.logger_command_data_client_port)

        self.udp_command_socket.bind(self.client_outbound_address_and_port)

        self.udp_response_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        self.udp_response_socket.settimeout(self.receive_timeout_sec)

        self.client_inbound_address_and_port = ("0.0.0.0", self.dq_ports.logger_discovery_remote_port)

        self.udp_response_socket.bind(self.client_inbound_address_and_port)

    def send_command(self, dq_command):

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

        # print(command_string)

        # for char in command_string:
        #    print(hex(char), end="")
        # print("\n\r")

        # output = ''.join('%02x' % char for char in command_string)
        # print(output)

        self.udp_command_socket.sendto(command_string, self.dataq_server_address_and_port)

        buffer_size = 1024

        try:
            response_from_logger = self.udp_response_socket.recv(buffer_size)
            self.process_response_alt(response_from_logger)
        except Exception as e:
            print(e)

    # process_response is a port of the parse_udp function demonstrated in the 4208UDP
    # C# example provide by dataq
    # THIS IS A WORK IN PROGRESS
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

            missing_sample_count = cumulative_sample_count_reported - self.sample_count_received_per_device[responsding_device_order]

            # create fake data to fill any gaps
            if missing_sample_count != 0:
                self.gap_count += 1
                self.b_gap = True

                for i in range(cumulative_sample_count_reported - self.sample_count_received_per_device[responsding_device_order]):
                    self.adc_data_buffer[responsding_device_order][self.fill_index[responsding_device_order]] = 3  # event markers???
                    self.fill_index[responsding_device_order] += 1

                    if self.fill_index[responsding_device_order] >= self.device_adc_buffer_size:
                        self.fill_index[responsding_device_order] = 0
                self.sample_count_received_per_device[responsding_device_order] = cumulative_sample_count_reported

            # the payload length is defined by the chosen packet size. The bytes sent are divided amongst the number
            # of channels being read in
            for i in range(payload_sample_count):
                sample_start_index = 20 + i * 2
                n = int.from_bytes(response_from_logger[sample_start_index:sample_start_index + 4], byteorder=self.byte_order)
                m = int('0xfffc', 0)

                result = int(n & m)

                print("n raw: ", n, " m: ", m, " result: ", result)

                self.adc_data_buffer[responsding_device_order][self.fill_index[responsding_device_order]] = result

                self.fill_index[responsding_device_order] += 1
                if self.fill_index[responsding_device_order] >= self.device_adc_buffer_size:
                    self.fill_index[responsding_device_order] = 0

                self.sample_count_received_per_device[responsding_device_order] = self.sample_count_received_per_device[responsding_device_order] + payload_sample_count

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

    def process_response_alt(self, response_from_logger):
        # print("processing response alt")

        response_id = int.from_bytes(response_from_logger[0:4], byteorder=self.byte_order)
        response_public_key = 0
        responding_device_order = 0
        response_payload_length = 0

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
            # print("Got DQADCDATA")

            cumulative_sample_count_from_device = int.from_bytes(response_from_logger[12:16], byteorder=self.byte_order)
            payload_sample_count_from_device = int.from_bytes(response_from_logger[16:20], byteorder=self.byte_order)

            missing_sample_count = \
                cumulative_sample_count_from_device - \
                self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received

            # create fake data to fill any gaps
            if missing_sample_count != 0:
                print("Missing smaple processing TBD")

            # the payload length is defined by the chosen packet size. The bytes sent are divided amongst the number
            # of channels being read in
            for payload_index in range(payload_sample_count_from_device):
                sample_start_index = 20 + payload_index * 2
                raw_bytes = int.from_bytes(response_from_logger[sample_start_index:sample_start_index + 4], byteorder=self.byte_order)
                byte_modifier = int('0xfffc', 0)

                result = int(raw_bytes & byte_modifier)

                current_channel_index = (payload_index + self.dataq_group_container[responding_device_order].dq_data_structure.channel_carryover_index) % len(self.scan_list_configuration)
                # print("current_index: ", current_channel_index, " payload_index: ", payload_index, " carryover index: ", self.dataq_group_container[responding_device_order].dq_data_structure.channel_carryover_index)

                current_channel_in_list = list(self.scan_list_configuration.keys())[current_channel_index]

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
                    print("ch not found")

            self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received = \
                self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received + payload_sample_count_from_device

            self.dataq_group_container[responding_device_order].dq_data_structure.channel_carryover_index = current_channel_index + 1

            # print("Logger Data: ", self.dataq_group_container[responding_device_order].dq_data_structure)
            print("device reported bytes: ", cumulative_sample_count_from_device, " program count: ", self.dataq_group_container[responding_device_order].dq_data_structure.cumulative_samples_received)
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


def main():
    print("Main...")

    dq_ports = DQPorts(
        logger_discovery_local_port=1235,
        logger_discovery_remote_port=1234,
        logger_command_local_port=51235,
        logger_command_data_client_port=1427
    )

    logger_ip = "192.168.1.209"

    my_key = int("0x06681444", 0)

    # Dataq notes it may be necessary to change MYKEY every time acquisition is reconfigured.
    dq_command = DQCommandResponseStructures.DQCommand(
        id=DQEnums.ID.DQCOMMAND,
        public_key=my_key,
        command=DQEnums.Command.CONNECT,
        par1=dq_ports.logger_discovery_remote_port,
        par2=1,  # master
        par3=0,  # device order in group
        payload="192.168.1.3"  # IP of Host
    )

    dataq_comms = DataqCommsManager(dq_ports, logger_ip)

    dataq_comms.send_command(dq_command)

    # modify for second command
    dq_command.id = DQEnums.ID.DQCOMMAND
    dq_command.public_key = my_key
    dq_command.command = DQEnums.Command.SECONDCOMMAND
    dq_command.par1 = 0
    dq_command.par2 = 0
    dq_command.par3 = 0
    dq_command.payload = "info 1\r"

    dataq_comms.send_command(dq_command)

    # setup multi-unit sync
    # not using multiple devices at this time

    # set device time

    # set encoding - using already present packet info above
    dq_command.payload = "encode 0\r"

    dataq_comms.send_command(dq_command)

    # set packet size
    dq_command.payload = "ps 0\r"

    dataq_comms.send_command(dq_command)

    # define channel config
    dataq_comms.scan_list_configuration = {
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch1: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0,
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch3: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0,
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch4: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0,
        DQMasks.DQ4108.ScanListDefinition.AnalogIn.ch2: DQMasks.DQ4108.ScanListDefinition.AnalogScale.PN_10V0
    }

    for config in dataq_comms.scan_list_configuration:
        dq_command.payload = "slist " + str(config) + " " + str(config | dataq_comms.scan_list_configuration[config]) + "\r"
        # dq_command.payload = "slist 0 3\r"
        print(dq_command.payload)
        dataq_comms.send_command(dq_command)

    # define scan rate - refer to page 47
    desired_sample_rate_hz = 600
    dividend = 60e6
    srate_setting = 0  # max is 65535
    decimation_factor = 10  # 512  # 1 reported value per 512 samples
    decimation_multiplier = 1  # multiply factor by 1
    # sample_rate_hz = dividend / (srate_setting * decimation_factor * decimation_multiplier)

    srate_setting = dividend / (decimation_factor * decimation_multiplier * desired_sample_rate_hz)

    dq_command.payload = "srate " + str(int(srate_setting)) + "\r"

    dataq_comms.send_command(dq_command)

    # dec and deca
    dq_command.payload = "dec " + str(decimation_factor) + "\r"

    dataq_comms.send_command(dq_command)

    dq_command.payload = "deca " + str(decimation_multiplier) + "\r"

    dataq_comms.send_command(dq_command)

    # sync start/start
    dq_command.id = DQEnums.ID.DQCOMMAND
    dq_command.command = DQEnums.Command.SYNCSTART
    dq_command.payload = "start 0\r"

    dataq_comms.send_command(dq_command)

    # start sampling...
    x = 0
    while x < 10000:
        try:
            response = dataq_comms.udp_response_socket.recv(1024)
            dataq_comms.process_response_alt(response)

            print("Channel 2: ", dataq_comms.dataq_group_container[0].dq_data_structure.analog2.pop())
        except Exception as e:
            print(e)
        x += 1
        if x % 10:
            dq_command.id = DQEnums.ID.DQCOMMAND
            dq_command.command = DQEnums.Command.KEEPALIVE
            dq_command.payload = "Keep Alive\r"
            dataq_comms.send_command(dq_command)

    # stop
    dq_command.payload = "stop\r"

    dataq_comms.send_command(dq_command)


if __name__ == "__main__":
    main()
