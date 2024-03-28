import random
import socket
import sys
import time
import threading

import select


def create_message(server_name, port):
    magic_cookie = 0xabcddcba
    message_type = 0x2
    # padd server name to 32 characters with null bytes
    server_name = server_name.ljust(32, '\0')
    server_port = port
    message = magic_cookie.to_bytes(4, byteorder='big') + message_type.to_bytes(1,
                                                                                byteorder='big') + server_name.encode() + server_port.to_bytes(
        2, byteorder='big')
    return message


def create_question_bank():
    # return a dictionary of questions and answers true or false
    return {"question1": True, "question2": False, "question3": True, "question4": False, "question5": True}


class Server:
    server_name = "PizzaProject"

    state = 0  # 0 = waiting for client, 1 = game mode
    timeout = 10
    question_index = 0
    players = {}  # map of player sockets to their names and status
    questions = create_question_bank()

    stack = []

    answers = 0
    players_alive = 0
    lock = threading.Lock()
    correct_answers = set()
    wrong_answers = set()

    def __init__(self):

        self.UDP_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.UDP_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.UDP_socket.bind(('', 0))

        self.TCP_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.TCP_socket.bind(('', 0))
        self.port = self.TCP_socket.getsockname()[1]

        self.UDP_thread = None
        self.TCP_thread = None

        self.condition = threading.Condition()
        self.condition_gameManager = threading.Condition()
        self.condition_stack = threading.Condition()

    def main_loop(self):
        # start UDP thread
        self.UDP_server()
        # start TCP thread
        self.TCP_server()

        self.start_client_threads()

        # Game manager thread
        self.game_manager()
    def game_manager(self):
        while True:

            with self.condition_gameManager:
                self.condition_gameManager.wait()
            print("wrong answers - ", len(self.wrong_answers))
            print("correct answers - ", len(self.correct_answers))
            print()
            with self.lock:

                if self.players_alive == len(self.wrong_answers):
                    for socket in self.wrong_answers:
                        self.players[socket]["status"] = True
                    self.wrong_answers.clear()
                    self.answers = 0
                    self.question_index += 1
                    if self.question_index == len(self.questions):
                        self.shuffle()
                        self.question_index = 0
                    with self.condition:
                        self.condition.notify_all()
                    self.send_stats_for_all()

                elif self.players_alive == self.answers:
                    self.players_alive = len(self.correct_answers)
                    self.answers = 0
                    self.question_index += 1

                    self.correct_answers.clear()
                    self.wrong_answers.clear()

                    if self.question_index == len(self.questions):
                        self.shuffle()
                        self.question_index = 0
                    with self.condition:
                        self.condition.notify_all()
                    self.send_stats_for_all()
    def send_winner_for_all(self):
        winner = ""
        for val in self.players.values():
            if val["status"] == True:
                winner = val["name"]

        message = (winner + " is the winner !").encode()
        for socket in self.players.keys():
            socket.send(message)
    def send_stats_for_all(self):
        message = ""
        for socket in self.correct_answers:
            message += self.players[socket]["name"] +" is correct !\n"
        for socket in self.wrong_answers:
            message += self.players[socket]["name"] +" is iorrect !\n"

        message = message.encode()
        for socket in self.players.keys():
            socket.send(message)
    def shuffle(self):
        pass
    def start_client_threads(self):
        while self.state == 0:
            with self.condition_stack:
                self.condition_stack.wait()
            if len(self.stack) > 0:
                client_thread = self.stack.pop()
                try:
                    client_thread.start()
                    print("Thread started")
                except:
                    print("Error starting thread")

    def UDP_server(self):

        message = create_message(self.server_name, self.port)
        # create a thread for the UDP server
        self.UDP_thread = threading.Thread(target=self.send_UDP_message, args=(message,))
        self.UDP_thread.start()

    def send_UDP_message(self, message):
        while self.state == 0:
            sent = self.UDP_socket.sendto(message, ('<broadcast>', 13117))
            time.sleep(1)

    def TCP_server(self):

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
            # accept connection
            try:
                client_socket, client_address = self.TCP_socket.accept()
                last_accepted = time.time()
                print("Connection from: ", client_address)
            except:
                continue

            # start thread for client
            client_thread = threading.Thread(target=self.TCP_client, args=(client_socket,))
            self.players[client_socket] = {"name": None, "status": True}
            with self.lock:
                self.players_alive += 1
                self.stack.append(client_thread)
            with self.condition_stack:
                self.condition_stack.notify_all()

        # kill UDP thread
        print("Starting game...")
        self.state = 1

        with self.condition_stack:
            self.condition_stack.notify_all()

        with self.condition:
            self.condition.notify_all()

    def TCP_client(self, client_socket):
        # first receive is name
        while self.players[client_socket]["name"] is None:
            try:
                data = client_socket.recv(1024)
                self.players[client_socket]["name"] = data.decode()
                print("Client name: ", self.players[client_socket]["name"])
            except:
                print("timeout")

        # sleep on state until notify

        with self.condition:
            self.condition.wait()

        while self.state == 1:

            question = list(self.questions.keys())[self.question_index]
            client_socket.send(question.encode())
            # receive answer
            if self.players[client_socket]["status"] == False:
                with self.condition:
                    self.condition.wait()
                    continue

            data = client_socket.recv(1024)
            answer = data.decode() in ['Y', 'T', '1']
            if not answer == self.questions[question]:
                self.players[client_socket]["status"] = False
                with self.lock:
                    self.wrong_answers.add(client_socket)
                    # self.players_alive -= 1
                    self.answers += 1
            else:
                with self.lock:
                    self.correct_answers.add(client_socket)
                    self.answers += 1


            with self.condition_gameManager:
                self.condition_gameManager.notify_all()

            with self.condition:
                self.condition.wait()


server = Server()
server.main_loop()
