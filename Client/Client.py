import socket


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


class Client:
    def __init__(self, name, portListen):
        self.score = 0
        self.name = name

        self.server_ip = None

        self.UDP_port = portListen
        self.UDP_Socket = None

        self.TCP_port = None
        self.TCP_Socket = None

        self.server_name = None

        self.main_loop()

    def main_loop(self):
        while True:
            self.UDP_Listen()
            if self.TCP_Connect():
                self.TCP_client()

    def TCP_client(self):
        while True:
            try:
                # get the server message
                data = self.TCP_Socket.recv(1024)
                print(data)

                # get a char from keyboard and send it to the server
                char = input("Enter Y,T,1 for True, or N,F,0 for False: ")
                if char not in ['Y', 'T', '1', 'N', 'F', '0']:
                    continue
                self.TCP_Socket.send(char.encode())
            except:
                print("Something went wrong, trying to reconnect...")
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
        print("Received offer from " + self.server_name + ", attempting to connect...")
        self.TCP_Socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.TCP_Socket.settimeout(10)
        try:
            self.TCP_Socket.connect((self.server_ip, self.TCP_port))
            # send the client name
            self.TCP_Socket.send(self.name.encode() + b'\n')
            return True
        except:
            print("Connection failed, trying again...")
            return False


client = Client("Client1", 13117)
