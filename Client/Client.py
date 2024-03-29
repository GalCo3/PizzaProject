import socket
from socket import timeout
import time
import logging
import threading
import random
import sys
import msvcrt
import select

names = ["Galco", "Kitzer", "Kafire", "Megatron", "Max Verstappen", "Lebron James",
         "Megatron on the counter", "Element of surprise", "Every day another angle",
         "Magnus Carlsen", "John Cena", "Lightning McQueen"]


def parse_UDP_Message(data):
    if len(data) != 39:
        return False, False

    temp1 = data[:4]
    # check if the message starts with 0xabcddcba
    if data[:4] != 0xabcddcba.to_bytes(4, byteorder='big'):
        return False, False
    # check if the message type is 0x2
    if data[4] != 0x2:
        return False, False
    # check if the server name is 32 characters long
    if len(data[5:37]) != 32:
        return False, False
    # get the server name until null byte
    server_name = data[5:37].decode('utf-8').split('\x00')[0]

    # check if the last 2 bytes are the server port
    if len(data[37:]) != 2:
        return False, False
    server_port = int.from_bytes(data[37:], byteorder='big')

    return server_name, server_port


def input_with_timeout(prompt, timeout):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    start_time = time.time()
    input_data = ''
    while True:
        if msvcrt.kbhit():
            char = msvcrt.getch()
            if char == b'\r':  # Enter key
                break
            input_data += char.decode()
        if time.time() - start_time > timeout:
            break
    return input_data


class Client:
    def __init__(self, portListen):
        self.name = random.choice(names)
        logging.basicConfig(filename=self.name + "_Client.log", level=logging.DEBUG)

        self.server_ip = None
        self.done = False

        self.UDP_port = portListen
        self.UDP_Socket = None

        self.TCP_port = None
        self.TCP_Socket = None

        self.thread_STDIN = None
        self.thread_STDOUT = None

        self.server_name = None

    def main_loop(self):
        print(self.name)
        while True:
            self.UDP_Listen()
            if self.TCP_Connect():
                self.TCP_client()
                self.done = False

    def TCP_client(self):
        # set the timeout to 20 seconds
        self.TCP_Socket.settimeout(20)
        # start 2 threads, one for sending messages and one for receiving messages

        self.thread_STDOUT = threading.Thread(target=self.get_TCP_message)
        # stdin for intervals for 5 seconds
        self.thread_STDIN = threading.Thread(target=self.send_TCP_message)

        self.thread_STDOUT.start()
        self.thread_STDIN.start()

        self.thread_STDOUT.join()
        self.thread_STDIN.join()

    def get_TCP_message(self):
        while not self.done:
            try:
                data = self.TCP_Socket.recv(1024)
                # check if socket is closed
                if not data:
                    raise ConnectionError
                logging.info("Received: " + data.decode('utf-8'))
                data = data.decode('utf-8').split('\x00')[0]
                print("\n", data)
            # except timeout error
            except timeout as e:
                print("Connection timed out")
                continue
            except ConnectionError or ConnectionResetError:
                print("Connection closed")
                self.done = True
                # interrupt STDIN
                self.thread_STDIN.join(0)
                break

    def send_TCP_message(self):
        while not self.done:
            try:
                # input timeout for 5 seconds
                message = ""
                while not self.done:
                    message = input_with_timeout("", 3)
                    if message:
                        break

                self.TCP_Socket.send(message.encode())
                logging.info("Sent: " + message)
                # print("Sent: " + message)
            except ConnectionError:
                print("Connection closed")
                self.done = True
                break

    def UDP_Listen(self):

        print("Client started, listening for offer requests...")

        self.UDP_Socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.UDP_Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.UDP_Socket.bind(('', self.UDP_port))

        while True:
            data, addr = self.UDP_Socket.recvfrom(1024)
            # parse the message
            server_name, server_port = parse_UDP_Message(data)
            if server_name == False or server_port == False:
                continue
            else:
                self.server_ip = addr[0]
                self.server_name = server_name
                self.TCP_port = server_port
                break

    def TCP_Connect(self):
        host_ip, _ = self.UDP_Socket.getsockname()  # for some reason host_ip is always 0.0.0.0, so it's not interesting
        print("Received offer from \"" + self.server_name + "\", attempting to connect...")
        self.TCP_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.TCP_Socket.settimeout(10)
        try:
            self.TCP_Socket.connect((self.server_ip, self.TCP_port))
            # send the client name
            self.TCP_Socket.send(self.name.encode() + b'\n')
            print("Connected to the server!")
            return True
        except:
            print("Connection failed, trying again...")
            return False


if __name__ == "__main__":
    client = Client(13117)
    client.main_loop()
