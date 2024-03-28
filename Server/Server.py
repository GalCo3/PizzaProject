import socket
import sys
import time
import threading

import select


def create_message(server_name,port):
    magic_cookie = 0xabcddcba
    message_type = 0x2
    #padd server name to 32 characters with null bytes
    server_name = server_name.ljust(32, '\0')
    server_port = port
    message = magic_cookie.to_bytes(4, byteorder='big') + message_type.to_bytes(1, byteorder='big') + server_name.encode() + server_port.to_bytes(2, byteorder='big')
    return message


def create_question_bank():
    #return a dictionary of questions and answers true or false
    return {"question1": True, "question2": False, "question3": True, "question4": False, "question5": True}


class Server:
    server_name = "PizzaProject"

    state = 0  # 0 = waiting for client, 1 = game mode
    timeout = 10
    question_index = 0
    players = {} # map of player sockets to their names and scores
    questions = create_question_bank()
    def __init__(self):

        self.UDP_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.UDP_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.UDP_socket.bind(('', 0))

        self.TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.TCP_socket.bind(('', 0))
        self.port = self.TCP_socket.getsockname()[1]

        self.UDP_thread = None
        self.TCP_thread = None
    def main_loop(self):
        #start UDP thread
        self.UDP_server()
        #start TCP thread
        # self.TCP_server()



    def UDP_server(self):

        message = create_message(self.server_name,self.port)
        # self.UDP_thread = threading.Thread(target=self.send_UDP_message, args=(message,))
        # self.UDP_thread.start()
        # self.send_UDP_message(message)
        self.UDP_socket.sendto(message, ('<broadcast>', 13117))

    def send_UDP_message(self, message):
        while self.state == 0:
            self.UDP_socket.sendto(message, ('<broadcast>', 13117))
            time.sleep(1)

    def TCP_server(self):
        self.TCP_socket.bind(('', self.port))
        self.TCP_socket.listen(1)
        self.TCP_socket.settimeout(1)
        # accept connection from client
        self.TCP_thread = threading.Thread(target=self.TCP_accept)
        self.TCP_thread.start()

    def TCP_accept(self):
        last_accepted = None
        while True:
            if last_accepted is not None and time.time() - last_accepted > self.timeout:
                break
            #accept connection
            try:
                client_socket, client_address = self.TCP_socket.accept()
            except:
                continue

            if client_socket:
                last_accepted = time.time()

            self.players[client_socket] = {"name": None, "score": 0}

            print("Connection from: ", client_address)
            # start thread for client
            client_thread = threading.Thread(target=self.TCP_client, args=(client_socket,))
            client_thread.start()

        # kill UDP thread
        print("Starting game...")
        self.state = 1

    def TCP_client(self, client_socket):
        # first receive is name
        if self.players[client_socket]["name"] is None:
            data = client_socket.recv(1024)
            self.players[client_socket]["name"] = data.decode()
            print("Client name: ", self.players[client_socket]["name"])

        # send question
        while self.state == 1:
            question = list(self.questions.keys())[self.question_index]
            client_socket.send(question.encode())
            # receive answer
            data = client_socket.recv(1024)
            if data.decode() == str(self.questions[question]):
                self.players[client_socket]["score"] += 1
            self.question_index += 1
            if self.question_index == len(self.questions):
                self.state = 2
                break

server = Server()
server.main_loop()