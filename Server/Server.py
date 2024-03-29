import random
import socket
from socket import timeout
import time
import threading

import logging


def create_message(server_name, port):
    magic_cookie = 0xabcddcba
    message_type = 0x2
    # pad server name to 32 characters with null bytes
    server_name = server_name.ljust(32, '\0')
    server_port = port
    message = magic_cookie.to_bytes(4, byteorder='big') + message_type.to_bytes(1,
                                                                                byteorder='big') + server_name.encode() + server_port.to_bytes(
        2, byteorder='big')
    return message


def create_question_bank():
    # return a dictionary of questions and answers true or false
    return {
        "Pizza originated in Italy.": True,
        "Hawaiian pizza typically includes pineapple and ham toppings.": True,
        "The world's largest pizza ever made measured over 100 feet in diameter.": True,
        "The first pizzeria in the United States opened in New York City.": True,
        "Deep dish pizza was invented in Chicago.": True,
        "Pizza Margherita was named after a queen.": True,
        "The world's most expensive pizza costs over $12,000.": True,
        "Pizza Hut was founded in the 1950s.": True,
        "The pizza delivery industry is estimated to be worth over $10 billion annually.": True,
        "The record for the most pizzas made in one hour is over 6,000.": True,
        "Pizza boxes are generally square-shaped to fit the round pizza inside.": False,
        "Neapolitan pizza should have a thin, crispy crust.": False,
        "The pizza margherita was named after a famous Italian chef.": False,
        "Authentic Italian pizza is typically topped with cheddar cheese.": False,
        "The Hawaiian pizza originated in Hawaii.": False,
        "The world's largest pizza was cooked in less than an hour.": False,
        "The first frozen pizza was created in the 1940s.": False,
        "Pizza delivery was first introduced in the 19th century.": False,
        "The original pizza was sweet rather than savory.": False,
        "The word 'pizza' is derived from Greek.": False
    }


players = {}  # map of player sockets to their names and status


class Server:
    server_name = "PizzaProject"

    state = 0  # 0 = waiting for client, 1 = game mode
    timeout = 10
    question_index = 0
    questions = create_question_bank()
    questions_order = [i for i in range(len(questions))]

    answers = 0
    players_alive = 0
    socket_crashed = False
    lock = threading.Lock()
    correct_answers = set()
    wrong_answers = set()

    def __init__(self, min_players):
        # start logging to the desktop
        logging.basicConfig(filename='Server.log', level=logging.DEBUG)

        random.shuffle(self.questions_order)

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
        while True:
            print("New Game Started")
            # start UDP thread
            self.UDP_server()
            # start TCP thread
            self.TCP_server()
            # self.start_client_threads()
            # Game manager thread
            self.game_manager()
            self.reset()

    def reset(self):
        self.state = 0
        self.question_index = 0
        global players
        players = {}
        self.answers = 0
        self.players_alive = 0
        self.correct_answers = set()
        self.wrong_answers = set()
        self.questions_order = [i for i in range(len(self.questions))]
        self.shuffle()

    def game_manager(self):
        if self.state == 0:
            with self.condition_gameManager:
                self.condition_gameManager.wait()
        while self.players_alive > 1:
            with self.condition_gameManager:
                self.condition_gameManager.wait()
            print("wrong answers - ", len(self.wrong_answers))
            print("correct answers - ", len(self.correct_answers))
            print()
            with self.lock:

                if self.players_alive == len(self.wrong_answers):
                    for sock in self.wrong_answers:
                        players[sock]["status"] = True
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
                    self.send_stats_for_all()
                    if self.players_alive == 1:
                        self.state = 2
                        self.send_winner_for_all()
                        time.sleep(0.1)
                    with self.condition:
                        self.condition.notify_all()
        print("End Game manager\n\n")
        return

    def send_winner_for_all(self):
        winner = ""
        for val in players.values():
            if val["status"]:
                # remove the last character which is a newline
                winner = val["name"][:-1]
                break
        if winner == "Max Verstappen":
            message = "https:\/\/youtu.be\/cvj5OA1iQ8s?si=rS29y5nqHax1uDj7&t=14"
        else:
            message = winner + " is the winner !"
        for sock in players.keys():
            self.send_to_TCP(message, sock)
        time.sleep(0.5)

        for sock in players.keys():  # close all sockets
            sock.close()

        print("Game Over - Winner is: ", winner)

    def send_stats_for_all(self):
        message = ""
        for sock in self.correct_answers:
            message += players[sock]["name"] + " is correct !\n"
        for sock in self.wrong_answers:
            message += players[sock]["name"] + " is incorrect !\n"

        for sock in players.keys():
            self.send_to_TCP(message, sock)

    def shuffle(self):
        random.shuffle(self.questions_order)

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
            players[client_socket] = {"name": None, "status": True}
            client_thread = threading.Thread(target=self.TCP_client, args=(client_socket,))
            self.players_alive += 1
            client_thread.start()

        time.sleep(1)
        print("Starting game...")
        self.state = 1

        # check that are enough players

        with self.condition_gameManager:
            self.condition_gameManager.notify_all()

        with self.condition:
            self.condition.notify_all()

    def TCP_client(self, client_socket):
        # first receive is name
        while client_socket in players and players[client_socket]["name"] is None:
            try:
                data = client_socket.recv(1024)
                logging.info("Received: " + data.decode())
                players[client_socket]["name"] = data.decode()
                print("Client name: ", players[client_socket]["name"], end="\n\n")
            except:
                print("timeout")

        # sleep on state until notify

        with self.condition:
            self.condition.wait()

        client_socket.settimeout(10)

        while self.state == 1:

            question = str(list(self.questions.keys())[self.questions_order[self.question_index]])
            self.send_to_TCP(question, client_socket)
            # receive answer
            with self.lock:
                if client_socket not in players:
                    return
                elif not players[client_socket]["status"]:
                    with self.condition:
                        self.condition.wait()
                        continue

            time.sleep(0.5)
            # self.send_to_TCP("input", client_socket)

            data = self.receive_from_TCP(client_socket)
            if data == "":
                break

            answer = data in ['Y', 'T', '1']
            if not answer == self.questions[question] or data == "timeout":
                players[client_socket]["status"] = False
                # self.send_to_TCP("wrong", client_socket)
                with self.lock:
                    self.wrong_answers.add(client_socket)
                    # self.players_alive -= 1
                    self.answers += 1
            else:
                # self.send_to_TCP("correct", client_socket)
                with self.lock:
                    self.correct_answers.add(client_socket)
                    self.answers += 1

            with self.condition_gameManager:
                self.condition_gameManager.notify_all()

            with self.condition:
                self.condition.wait()

    def receive_from_TCP(self, socket):
        while True:
            try:
                data = socket.recv(1024)
                logging.info("Received: " + data.decode())
                data = data.decode('utf-8').split('\x00')[0]
                return data
            except ConnectionError as e:
                print("Connection closed")
                self.socket_crashed(socket)
                return ""
            except timeout:
                return "timeout"

    def send_to_TCP(self, message, socket):
        # pad message to 512 bytes
        # message = message.ljust(512, '\0')

        try:
            socket.send(message.encode())
            logging.info("Sent: " + message)
        # catch exception
        except ConnectionError as e:
            self.socket_crashed(socket)

    def socket_crashed(self, socket):
        with self.lock:
            self.answers += 1
            # if exist
            if socket in players:
                print("Player ", players[socket]["name"], " has left the game.")
                players.pop(socket)

        with self.condition_gameManager:
            self.condition_gameManager.notify_all()


server = Server()
server.main_loop()
