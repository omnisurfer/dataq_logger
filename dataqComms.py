from dataclasses import dataclass
from enum import IntEnum
import socket

"""
https://www.dataq.com/products/di-4108-e/
"""


@dataclass
class DQEnums:
    class ID(IntEnum):
        DQCOMMAND = int("0x31415926", 0)
        DQRESPONSE = int("0x21712818", 0)
        DQADCDATA = int("0x14142135", 0)
        DQTHUMBDATA = int("0x17320508", 0)
        DQTHUMBEOF = int("0x22360679", 0)
        DQTHUMBSTREAM = int("0x16180339", 0)
        DQWHCHDR = int("0x05772156", 0)

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

    class DQ4108:
        class ScanListDefinition:
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

            class AnalogIn:
                __bit_shift = 0
                ch0 = 0 << __bit_shift
                ch1 = 1 << __bit_shift
                ch2 = 2 << __bit_shift
                ch3 = 3 << __bit_shift
                ch4 = 4 << __bit_shift
                ch5 = 5 << __bit_shift
                ch6 = 6 << __bit_shift
                ch7 = 7 << __bit_shift

            class DigitalIn:
                __bit_shift = 0
                ch0 = 4 << __bit_shift

            class CountIn:
                __bit_shift = 0
                ch0 = 6 << __bit_shift


@dataclass
class DQPorts:
    # port numbers are from the loggers perspective
    logger_discovery_local_port: int  # this is fixed on the device
    logger_discovery_remote_port: int

    logger_command_local_port: int  # this is fixed on the device
    logger_command_data_client_port: int


@dataclass
class DQCommand:
    id: DQEnums.ID  # aka Type
    public_key: int  # aka GroupID
    command: DQEnums.Command
    par1: int
    par2: int
    par3: int
    payload: str


@dataclass
class DQResponse:
    id: DQEnums.ID
    public_key: int
    order: int  # Order of the instrument when used as a member of a sync group
    payload_length: int
    payload: chr


@dataclass
class DQAdcData:
    id: DQEnums.ID
    public_key: int
    order: int
    cumulative_count: int
    payload_length: int
    adc_data: int  # note this should be short but python does not have this a a type...


@dataclass
class DQ4108BinaryStreamOutput:
    analog0: int
    analog1: int
    analog2: int
    analog3: int
    analog4: int
    analog5: int
    analog6: int
    analog7: int
    digital0: int
    digital1: int


class DataqCommsManager:

    def __init__(self, dq_ports, logger_ip):
        self.dq_ports = dq_ports

        # drowan_NOTES_20200618: TBD sync device count
        self.sync_device_count = 5
        self.device_adc_buffer_size = 10  # 100000
        self.receive_timeout_sec = 2

        self.byte_order = 'little'
        self.is_signed = False

        self.sample_count_per_device = [self.sync_device_count]
        self.fill_index = [self.sync_device_count]

        rows, cols = (self.sync_device_count, self.device_adc_buffer_size)
        self.adc_data_buffer = [[0] * cols] * rows

        self.gap_count = 0
        self.b_gap = False

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
            self.process_response(response_from_logger)
        except Exception as e:
            print(e)

    # process_response is a port of the parse_udp function demonstrated in the 4208UDP
    # C# example provide by dataq
    # THIS IS A WORK IN PROGRESS
    def process_response(self, responses_from_logger):
        print("processing response")

        # myId = 0
        # myKey = 0
        # myOrder = 0
        # myRunningDataCount = 0
        # myPayloadSamples = 0
        myNumOfChan = 0
        myRealigned = 0

        response_id = int.from_bytes(responses_from_logger[0:4], byteorder=self.byte_order)
        response_public_key = 0
        response_order = 0
        response_payload_length = 0

        # check if the response carriers a group ID
        if len(responses_from_logger) > 8:
            response_public_key = int.from_bytes(responses_from_logger[4:8], byteorder=self.byte_order)
        else:
            response_public_key = 0

        # logger order for multi logger setups
        if len(responses_from_logger) > 12:
            response_order = int.from_bytes(responses_from_logger[8:12], byteorder=self.byte_order)
            # drowan_NOTES_20200618: TBD what this is used for...
            myRealigned = response_order
        else:
            response_order = 0
            myRealigned = 0

        # this may cap the number of devices, ignore orders beyond the count?
        if response_order >= self.sync_device_count:
            response_order = self.sync_device_count
        if response_order < 0:
            response_order = 0

        # the "switch" to process the packets
        if response_id == DQEnums.ID.DQADCDATA:
            print("Got DQADCDATA")
            # drowan_TODO_20200618: working on DQADCDATA portion of port, line 575
            cumulative_count = int.from_bytes(responses_from_logger[12:16], byteorder=self.byte_order)
            payload_length = int.from_bytes(responses_from_logger[16:20], byteorder=self.byte_order)

            i_not_sure = cumulative_count - self.sample_count_per_device[response_order]

            if i_not_sure != 0:
                self.gap_count += 1
                self.b_gap = True
                # create fake data to fill in gap

                for i in range(cumulative_count - self.sample_count_per_device[response_order]):
                    self.adc_data_buffer[response_order][self.fill_index[response_order]] = 3  # event markers???
                    self.fill_index[response_order] += 1

                    if self.fill_index[response_order] >= self.device_adc_buffer_size:
                        self.fill_index[response_order] = 0
                self.sample_count_per_device[response_order] = cumulative_count

            for i in range(payload_length):
                sample_start_index = 20 + i
                n = int.from_bytes(responses_from_logger[sample_start_index:sample_start_index+4], byteorder=self.byte_order)
                m = int('0xfffc', 0)

                print(n)

                x = self.adc_data_buffer[response_order][self.fill_index[response_order]] = int(n & m)

                print(x)

                self.fill_index[response_order] += 1
                if self.fill_index[response_order] >= self.device_adc_buffer_size:
                    self.fill_index[response_order] = 0

                self.sample_count_per_device[response_order] = self.sample_count_per_device[response_order] + payload_length

            print(self.adc_data_buffer[response_order][self.fill_index[response_order]])

            return 1

        elif response_id == DQEnums.ID.DQRESPONSE:
            print("Got DQRESPONSE")
            payload_length = int.from_bytes(responses_from_logger[12:16], byteorder=self.byte_order)
            payload = responses_from_logger[16:16 + payload_length]
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
    dq_command = DQCommand(
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
    scan_list_config = {
        DQEnums.DQ4108.ScanListDefinition.AnalogIn.ch0: DQEnums.DQ4108.ScanListDefinition.AnalogScale.PN_0V5,
        DQEnums.DQ4108.ScanListDefinition.AnalogIn.ch1: DQEnums.DQ4108.ScanListDefinition.AnalogScale.PN_0V5,
        DQEnums.DQ4108.ScanListDefinition.AnalogIn.ch2: DQEnums.DQ4108.ScanListDefinition.AnalogScale.PN_0V5,
        DQEnums.DQ4108.ScanListDefinition.AnalogIn.ch3: DQEnums.DQ4108.ScanListDefinition.AnalogScale.PN_0V5
    }

    for config in scan_list_config:
        dq_command.payload = "slist " + str(config) + " " + str(config | scan_list_config[config]) + "\r"
        print(dq_command.payload)
        dataq_comms.send_command(dq_command)

    # define scan rate - refer to page 47
    desired_sample_rate_hz = 10
    dividend = 60e6
    srate_setting = 0  # max is 65535
    decimation_factor = 512  # 1 reported value per 512 samples
    decimation_multiplier = 2  # multiply factor by 1
    sample_rate_hz = dividend * (srate_setting * decimation_factor * decimation_multiplier)

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
    while x < 10:
        try:
            dataq_comms.udp_response_socket.recv(1024)
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
