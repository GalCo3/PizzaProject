from Client import *


class Bot(Client):

    def __init__(self, portListen):
        super().__init__(portListen)
        self.name = "BOT_" + self.name
        self.send = False
        self.condition = threading.Condition()
        

    
    # def TCP_client(self):
    #
    #     # set the timeout to 20 seconds
    #     self.TCP_Socket.settimeout(20)
    #
    #
    #     while not self.done:
    #         try:
    #             data = self.TCP_Socket.recv(1024)
    #             # check if socket is closed
    #             if not data:
    #                 raise ConnectionError
    #
    #             answer = random.choice(["Y", "N"])
    #
    #             self.TCP_Socket.send(answer.encode())
    #             print("Sent: " + answer)
    #
    #         except ConnectionError:
    #             self.done = True
    #             self.TCP_Socket.close()
    #             break
    #
    #         except timeout:
    #             continue

    def receive_message_from_server(self):
        while not self.done:
            try:
                data = self.TCP_Socket.recv(1024)
                # check if socket is closed
                if not data:
                    raise ConnectionError
                logging.info("Received: " + data.decode('utf-8'))
                data = data.decode('utf-8').split('\x00')[0]
                print("\n", data)
                with self.condition:
                    self.condition.notify_all()
                    # print("Notified")
            # except timeout error
            except timeout:
                print("Connection timed out")
                continue
            except ConnectionError or ConnectionResetError:
                print("Connection closed")
                if not self.done:
                    self.done = True
                    with self.condition:
                        self.condition.notify_all()
                break

    def send_data_to_server(self):
        while not self.done:
            try:
                # input timeout for 5 seconds
                message = random.choice(["Y", "N"])
                self.TCP_Socket.send(message.encode())
                logging.info("Sent: " + message)
                print("Sent: " + message)
                with self.condition:
                    self.condition.wait()
                time.sleep(1)
            except ConnectionError:
                print("Connection closed")
                self.done = True
                break


if __name__ == "__main__":
    bot = Bot(13117)
    bot.main_loop()
