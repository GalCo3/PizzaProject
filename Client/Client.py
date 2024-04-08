import socket
from socket import timeout
import time
import logging
import threading
import random
import sys
import msvcrt
from colorama import init as colorama_init
from colorama import Fore

colorama_init()

names = ["Galco", "Kitzer", "Kafire", "Megatron", "Max Verstappen", "Lebron James",
         "Megatron on the counter", "Element of surprise", "Every day another angle",
         "Magnus Carlsen", "John Cena", "Lightning McQueen"]


def parse_UDP_Message(data):
    if len(data) != 39:
        return False, False

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


def retrieve_input_with_timeout(prompt, timeout):
    # Retrieves input with a timeout.
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

        self.colors = [Fore.LIGHTBLUE_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTGREEN_EX, Fore.LIGHTRED_EX, Fore.LIGHTMAGENTA_EX, Fore.LIGHTCYAN_EX, Fore.RESET]

    def main_loop(self):
        print(random.choice(self.colors) + self.name)
        while True:
            self.listen_to_broadcasts()
            if self.TCP_Connect():
                self.init_TCP_client()
                self.done = False

    def init_TCP_client(self):
        # Initializes the TCP client.
        # Sets the timeout to 20 seconds.
        self.TCP_Socket.settimeout(20)
        # Starts 2 threads, one for sending messages and one for receiving messages.
        self.thread_STDOUT = threading.Thread(target=self.receive_message_from_server)
        # Stdin for intervals for 5 seconds.
        self.thread_STDIN = threading.Thread(target=self.send_data_to_server)
        self.thread_STDOUT.start()
        self.thread_STDIN.start()
        self.thread_STDOUT.join()
        self.thread_STDIN.join()

    def receive_message_from_server(self):
        # Receives messages from the server.
        while not self.done:
            try:
                data = self.TCP_Socket.recv(1024)
                # Check if socket is closed.
                if not data:
                    raise ConnectionError
                logging.info("Received: " + data.decode('utf-8'))
                data = data.decode('utf-8')
                print("\n", random.choice(self.colors) + data)
            # Handles timeout error.
            except timeout:
                print(random.choice(self.colors) + "Connection timed out")
                continue
            except ConnectionError or ConnectionResetError:
                print(random.choice(self.colors) + "Connection closed")
                self.done = True
                # Interrupt STDIN.
                self.thread_STDIN.join(0)
                break

    def send_data_to_server(self):
        # Sends data to the server.
        while not self.done:
            try:
                # Input timeout for 5 seconds.
                message = ""
                while not self.done:
                    message = retrieve_input_with_timeout("", 3)
                    if message:
                        break
                self.TCP_Socket.send(message.encode())
                logging.info("Sent: " + message)
            except ConnectionError:
                print(random.choice(self.colors) + "Connection closed")
                self.done = True
                break

    def listen_to_broadcasts(self):
        # Listens to broadcasts.
        print(random.choice(self.colors) + "Client started, listening for offer requests...")
        self.UDP_Socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.UDP_Socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.UDP_Socket.bind(('', self.UDP_port))
        while True:
            data, addr = self.UDP_Socket.recvfrom(1024)
            # Parse the message.
            server_name, server_port = parse_UDP_Message(data)
            if server_name == False or server_port == False:
                continue
            else:
                self.server_ip = addr[0]
                self.server_name = server_name
                self.TCP_port = server_port
                break

    def TCP_Connect(self):
        # Connects via TCP.
        host_ip, _ = self.UDP_Socket.getsockname()  # For some reason host_ip is always 0.0.0.0, so it's not interesting.
        print(random.choice(self.colors) + "Received offer from \"" + self.server_name + "\", attempting to connect...")
        self.TCP_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.TCP_Socket.settimeout(10)
        try:
            self.TCP_Socket.connect((self.server_ip, self.TCP_port))
            # Send the client name.
            self.TCP_Socket.send(self.name.encode() + b'\n')
            print(random.choice(self.colors) + "Connected to the server!")
            return True
        except:
            print(random.choice(self.colors) + "Connection failed, trying again...")
            return False


if __name__ == "__main__":
    client = Client(13117)
    client.main_loop()
