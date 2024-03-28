import socket
import sys
import time
import threading

import select



def get_available_port():
    temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    temp_socket.bind(('', 0))
    port = temp_socket.getsockname()[1]
    temp_socket.close()
    return port

def create_message(server_name,port):
    magic_cookie = 0xabcddcba
    message_type = 0x2
    #padd server name to 32 characters with null bytes
    server_name = server_name.ljust(32, '\0')
    server_port = port
    message = magic_cookie.to_bytes(4, byteorder='big') + message_type.to_bytes(1, byteorder='big') + server_name.encode() + server_port.to_bytes(2, byteorder='big')
    return message, server_port

class Server:
    server_name = "PizzaProject"
    state = 0  # 0 = waiting for client, 1 = game mode
    timeout = 10
    player_socket = []
    player_name = []
    addr = []

    def __init__(self):
        self.port = get_available_port()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.socket.bind(('localhost', self.port))
        self.socket.listen(3)
        print("Server started, listening on IP address "
              + str(socket.gethostbyname(socket.gethostname())) + ":" + str(self.port))
        message = create_message(self.server_name, self.port)
        self.start_broadcasting(message)
        self.start_receiver(self, 0)
        self.start_receiver(self, 1)
        self.start_receiver(self, 2)


    def close(self):
        self.socket.close()

    def sendOutMessage(self, message):
        self.socket.send(message.encode())
        print("Message sent: " + message)

    def broadcast(self, message):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # use UDP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)  # enable broadcasting
        while self.state == 0:
            self.socket.sendto(message.encode(), ('<broadcast>', self.port))
            print("Broadcast message sent: " + message)

    def start_broadcasting(self, message):
        broadcast_thread = threading.Thread(target=self.broadcast, args=(message,))
        broadcast_thread.start()

    def receive(self, rc_id, timeout=10):
        client_ready = False
        while not client_ready:
            readable, writable, exceptional = select.select([self.socket], [], [], timeout)
            if self.state == 0:
                for s in readable:
                    data, addr = s.recvfrom(1024)
                    print("Received message: " + data.decode() + " from " + str(addr))
                    self.player_name[rc_id] = data.decode()
                    self.player_socket[rc_id] = s
                    self.addr[rc_id] = addr
                    client_ready = True

    def start_receiver(self, rc_id, timeout=10):
        receive_thread = threading.Thread(target=self.receive, args=(rc_id, timeout))
        receive_thread.start()

    def timer(self):
        # start timer
        num_of_players = 0
        start_time = time.time()
        while num_of_players < 3:
            time.sleep(1)
            if time.time() - start_time > self.timeout:
                print("Game has begun.")
                self.state = 1
                break
            if self.state == 0:
                num_of_players = 0
                for i in range(3):
                    if self.player_socket[i] is not None:
                        num_of_players += 1



    def start_timer(self):
        timer_thread = threading.Thread(target=self.timer)
        timer_thread.start()