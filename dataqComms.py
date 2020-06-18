from dataclasses import dataclass
from enum import IntEnum
import socket


@dataclass
class DQCommand:
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
        TEST_COMMAND = int("0xC0FFEEBA", 0)

    class Key(IntEnum):
        MYKEY = int("0x6681444", 0)
        TEST_KEY = int("0xDEADBEEF", 0)

    id: ID
    public_key: Key
    command: Command
    par1: int
    par2: int
    par3: int
    payload: str


def send_command(dq_command, local_port, remote_port, client_port, command_port):
    byte_order = 'little'
    is_signed = False

    command_string = ''
    id_byte = dq_command.id.to_bytes(4, byteorder=byte_order, signed=is_signed)
    public_key_byte = dq_command.public_key.to_bytes(4, byteorder=byte_order, signed=is_signed)
    command_byte = dq_command.command.to_bytes(4, byteorder=byte_order, signed=is_signed)
    par1_byte = dq_command.par1.to_bytes(4, byteorder=byte_order, signed=is_signed)
    par2_byte = dq_command.par2.to_bytes(4, byteorder=byte_order, signed=is_signed)
    par3_byte = dq_command.par3.to_bytes(4, byteorder=byte_order, signed=is_signed)

    command_string = id_byte + public_key_byte + command_byte + par1_byte + par2_byte + par3_byte + dq_command.payload.encode('utf-8')

    print(command_string)

    for char in command_string:
        # print(char.encode('utf-8').hex(), end="")
        print(hex(char), end="")
    print("\n\r")

    output = ''.join('%02x' %char for char in command_string)
    print(output)

    udp_command_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    udp_command_socket.settimeout(3)

    dataq_server_address_and_port = ("192.168.1.209", command_port)
    client_outbound_address_and_port = ("0.0.0.0", client_port)

    udp_command_socket.bind(client_outbound_address_and_port)

    udp_command_socket.sendto(command_string, dataq_server_address_and_port)

    buffer_size = 1024

    udp_response_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    udp_response_socket.settimeout(3)

    client_inbound_address_and_port = ("0.0.0.0", remote_port)

    udp_response_socket.bind(client_inbound_address_and_port)

    message_from_server = udp_response_socket.recv(buffer_size)

    message_from_server = message_from_server.decode("utf-8")

    print("Message from server: ", str(message_from_server))


def main():
    print("Main...")

    local_port = 1235
    remote_port = 1234
    client_port = 1427
    command_port = 51235

    dq_command = DQCommand(
        id=DQCommand.ID.DQCOMMAND,
        command=DQCommand.Command.CONNECT,
        public_key=DQCommand.Key.MYKEY,
        par1=remote_port,
        par2=1,  # master
        par3=0,  # device order in group
        payload="192.168.1.3"  # IP of Host
    )

    send_command(dq_command, local_port, remote_port, client_port, command_port)


if __name__ == "__main__":
    main()
