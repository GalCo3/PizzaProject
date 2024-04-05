import random
import socket
from socket import timeout
import time
import threading
import logging
import pygame


def create_message(server_name, port):
    magic_cookie = 0xabcddcba
    message_type = 0x2
    # pad server name to 32 characters with null bytes
    server_name = server_name.ljust(32, '\0')
    server_port = port
    message = (magic_cookie.to_bytes(4, byteorder='big') +
               message_type.to_bytes(1, byteorder='big') +
               server_name.encode() + server_port.to_bytes(2, byteorder='big'))
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
    lock = threading.Lock()
    correct_answers = set()
    wrong_answers = set()

    players_wins = {}
    players_strike_wins = {}
    players_rounds = []
    questions_percentage = {}
    roundCounter = 0
    currentWinner = ""
    currentStrikeWinner = 0

    def __init__(self):
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

    def top3_sort_winner(self, scores):
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        top3 = "DID YOU KNOW?? THE TOP-3 WINNERS ON THIS SERVER ARE:\n"
        for i in range(len(sorted_scores)):
            top3 += str(i + 1) + ". " + sorted_scores[i][0] + ": " + str(sorted_scores[i][1]) + " wins\n"
        return top3

    def top3_sort_rounds(self, rounds):
        sorted_rounds = sorted(rounds, key=lambda x: x[1], reverse=True)[:3]
        top3 = "DID YOU KNOW?? THE TOP-3 LONGEST ROUNDS ON THIS SERVER ARE:\n"
        for i in range(len(sorted_rounds)):
            top3 += str(i + 1) + ". " + str(sorted_rounds[i][1]) + "rounds (the winner was: " + sorted_rounds[i][0] + ")\n"
        return top3
    def top3_difficult_question(self, question_bank):
        win_ratio = {name: round(val[0] / (val[1] + val[0]) * 100, 2) for name, val in question_bank.items()}
        sorted_win_ratio = sorted(win_ratio.items(), key=lambda x: x[1], reverse=True)[:3]
        top3 = "DID YOU KNOW?? THE TOP-3 MOST DIFFICULT QUESTIONS ON THIS SERVER ARE:\n"
        for i in range(len(sorted_win_ratio)):
            top3 += str(i + 1) + ". " + sorted_win_ratio[i][0] + ": " + str(sorted_win_ratio[i][1]) + " % from all the players were wrong\n"
        return top3

    def top3_sort_strike_winner(self, scores):
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
        top3 = "DID YOU KNOW?? THE TOP-3 LONGEST WINNING STRIKES ON THIS SERVER ARE:\n"
        for i in range(len(sorted_scores)):
            top3 += str(i + 1) + ". " + sorted_scores[i][0] + ": " + str(sorted_scores[i][1]) + " strike wins\n"
        return top3

    def random_statistics(self):
        action = random.randint(1, 4)
        if action == 1:
            return self.top3_sort_winner(self.players_wins)
        elif action == 2:
            return self.top3_sort_rounds(self.players_rounds)
        elif action == 3:
            return self.top3_difficult_question(self.questions_percentage)
        else:
            return self.top3_sort_strike_winner(self.players_strike_wins)

    def handle_question_statistics(self):
        question = str(list(self.questions.keys())[self.questions_order[self.question_index]])
        #check if question is in the dictionary (key)
        if question in self.questions_percentage:
            self.questions_percentage[question][0] += len(self.wrong_answers)
            self.questions_percentage[question][1] += len(self.correct_answers)
        else:
            self.questions_percentage[question] = [len(self.wrong_answers), len(self.correct_answers)]

    def handle_winner_statistic(self, winner):
        if winner in self.players_wins:
            self.players_wins[winner] += 1
        else:
            self.players_wins[winner] = 1

    def handle_round_statistic(self, winner):
        self.players_rounds.append((winner, self.roundCounter))
        self.roundCounter = 0

    def handle_strike_winner_statistic(self, winner):
        if winner == self.currentWinner:
            self.currentStrikeWinner += 1
            self.players_strike_wins[winner] = max(self.currentStrikeWinner,self.players_strike_wins[winner])
        else:
            self.currentWinner = winner
            self.currentStrikeWinner = 1
            if winner in self.players_strike_wins:
                self.players_strike_wins[winner] = max(self.currentStrikeWinner,self.players_strike_wins[winner])
            else:
                self.players_strike_wins[winner] = self.currentStrikeWinner

    def main_loop(self):
        while True:
            # print("New Game Started")
            # start UDP thread
            self.init_protocol_part_UDP()
            # start TCP thread
            self.init_protocol_part_TCP()
            # self.start_client_threads()
            # Game manager thread
            self.init_game_manager()
            self.reset_game()

    def reset_game(self):
        self.state = 0
        self.question_index = 0
        global players
        players = {}
        self.answers = 0
        self.players_alive = 0
        self.correct_answers = set()
        self.wrong_answers = set()
        self.questions_order = [i for i in range(len(self.questions))]
        self.shuffle_questions()

    def init_game_manager(self):
        if self.state == 0:
            with self.condition_gameManager:
                self.condition_gameManager.wait()
        while self.players_alive > 1:
            with self.condition_gameManager:
                self.condition_gameManager.wait()
            with (self.lock):

                if self.players_alive == len(self.wrong_answers):
                    self.handle_question_statistics()
                    self.roundCounter += 1
                    self.report_end_of_round()
                    for sock in self.wrong_answers:
                        players[sock]["status"] = True
                    self.wrong_answers.clear()
                    self.answers = 0
                    self.question_index += 1

                    if self.question_index == len(self.questions):
                        self.shuffle_questions()
                        self.question_index = 0

                    with self.condition:
                        self.condition.notify_all()

                elif self.players_alive == self.answers:
                    self.players_alive = len(self.correct_answers)
                    self.answers = 0
                    self.question_index += 1

                    if self.question_index == len(self.questions):
                        self.shuffle_questions()
                        self.question_index = 0
                    if self.players_alive == 1:
                        self.state = 2
                        self.handle_question_statistics()
                        self.roundCounter += 1
                        self.report_winner()
                        time.sleep(0.1)
                    else:
                        self.handle_question_statistics()
                        self.roundCounter += 1
                        self.report_end_of_round()
                    self.correct_answers.clear()
                    self.wrong_answers.clear()
                    with self.condition:
                        self.condition.notify_all()
        # print("End Game manager\n\n")
        return

    def report_winner(self):
        winner = ""
        for val in players.values():
            if val["status"]:
                # remove the last character which is a newline
                winner = val["name"][:-1]
                break
        self.handle_winner_statistic(winner)
        self.handle_round_statistic(winner)
        self.handle_strike_winner_statistic(winner)
        if winner == "Max Verstappen" or winner == "BOT_Max Verstappen":
            # message = "https://youtu.be/cvj5OA1iQ8s?si=qxiH7WyQzxHf4y-T&t=14"
            pygame.mixer.init()
            pygame.mixer.music.load("du_du_du.mp3")
            pygame.mixer.music.set_volume(0.07) # James Bond
            pygame.mixer.music.play()

        message = ""
        for sock in self.correct_answers.union(self.wrong_answers):
            message += players[sock]["name"][:-1] + (
                " is correct!\n" if players[sock]["status"] else " is incorrect!\n")
        message += "Game over!\nCongratulations to the winner: " + winner

        for sock in players.keys():
            self.send_message_to_client(message, sock)
        time.sleep(0.5)

        for sock in players.keys():
            self.send_message_to_client(self.random_statistics(), sock)
        time.sleep(0.5)

        for sock in players.keys():  # close all sockets
            sock.close()
        print("Game over, sending out offer requests...")

    def report_end_of_round(self):
        message = ""
        for sock in self.correct_answers.union(self.wrong_answers):
            message += (players[sock]["name"][:-1] +
                        (" is correct!\n" if players[sock]["status"] else " is incorrect!\n"))

        message += "\nNext round is played by "

        if self.players_alive == len(self.wrong_answers):
            # Everyone answered wrong
            for sock in players.keys():
                message += players[sock]["name"][:-1] + ", "
        else:
            # At least one player answered correctly
            for sock in players.keys():
                if players[sock]["status"]:
                    message += players[sock]["name"][:-1] + ", "

        message = message[:-2] + "\n"

        for sock in players.keys():
            self.send_message_to_client(message, sock)

    def shuffle_questions(self):
        random.shuffle(self.questions_order)

    def init_protocol_part_UDP(self):

        message = create_message(self.server_name, self.port)
        # create a thread for the UDP server
        self.UDP_thread = threading.Thread(target=self.send_UDP_message, args=(message,))
        self.UDP_thread.start()
        host_ip, _ = self.UDP_socket.getsockname()  # for some reason host_ip is always 0.0.0.0, so it's not relevant
        print("Server started, listening for TCP requests...")

    def send_UDP_message(self, message):
        while self.state == 0:
            self.UDP_socket.sendto(message, ('<broadcast>', 13117))
            time.sleep(1)

    def init_protocol_part_TCP(self):

        self.TCP_socket.listen(1)
        self.TCP_socket.settimeout(1)
        # accept connection from client
        self.TCP_thread = threading.Thread(target=self.handle_TCP_accept)
        self.TCP_thread.start()

    def handle_TCP_accept(self):
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
            client_thread = threading.Thread(target=self.handle_client_interaction, args=(client_socket,))
            self.players_alive += 1
            client_thread.start()

        if self.players_alive < 2:
            print("Not enough players, restarting...")
            self.reset_game()

        else:
            print("Starting game...")
            self.state = 1

        with self.condition_gameManager:
            self.condition_gameManager.notify_all()

        with self.condition:
            self.condition.notify_all()

    def handle_client_interaction(self, client_socket):
        # first receive is name
        while client_socket in players and players[client_socket]["name"] is None:
            try:
                data = client_socket.recv(1024)
                logging.info("Received: " + data.decode())
                players[client_socket]["name"] = data.decode()
                print("Client name: ", players[client_socket]["name"], end="\n\n")
            except:
                print("timeout")
        intro_msg = "Welcome to the \"" + self.server_name + ("\" server, where we are answering trivia questions "
                                                              "about Pizza!") + "\n"

        # sleep on state until notify
        try:
            with self.condition:
                self.condition.wait()
            client_socket.send("\0".encode())
        except ConnectionError:
            self.handle_socket_crash(client_socket)
            self.players_alive -= 1
            self.answers -= 1
            return

        client_socket.settimeout(10)

        for ind,sock in enumerate(players.keys()):
            intro_msg += "Player " + str(ind+1) + ": " + players[sock]["name"]
        intro_msg += "\n"

        self.send_message_to_client(intro_msg, client_socket)
        while self.state == 1:

            question = str(list(self.questions.keys())[self.questions_order[self.question_index]])
            self.send_message_to_client("True or False: " + question, client_socket)
            # receive answer
            # with self.lock:
            if client_socket not in players:
                return
            elif not players[client_socket]["status"]:
                with self.condition:
                    self.condition.wait()
                    continue

            data = self.receive_data_from_client(client_socket)
            if data == "":
                break

            answer = data in ['Y', 'T', '1','y','t']
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

    def receive_data_from_client(self, sock):
        while True:
            try:
                data = sock.recv(1024)
                logging.info("Received: " + data.decode())
                data = data.decode('utf-8').strip()#.split('\x00')[0]
                #trim data


                if data not in ['Y', 'T', '1','y','t','F','f','N','n','0']:
                    return "timeout"
                return data
            except ConnectionError:
                print("Connection closed")
                self.handle_socket_crash(sock)
                return ""
            except timeout:
                return "timeout"

    def send_message_to_client(self, message, sock):
        try:
            sock.send(message.encode())
            print(message)
            logging.info("Sent: " + message)
        # catch exception
        except ConnectionError:
            self.handle_socket_crash(sock)

    def handle_socket_crash(self, sock):
        with self.lock:
            self.answers += 1
            # if exist
            if sock in players:
                print("Player ", players[sock]["name"], " has left the game.")
                players.pop(sock)

        with self.condition_gameManager:
            self.condition_gameManager.notify_all()


server = Server()
server.main_loop()
