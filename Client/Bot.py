from Client import *
from colorama import init as colorama_init

colorama_init()


class Bot(Client):

    def __init__(self, portListen):
        super().__init__(portListen)
        self.name = "BOT_" + self.name
        self.send = False
        self.condition = threading.Condition()

    def receive_message_from_server(self):
        # Receives messages from the server.
        while not self.done:
            try:
                data = self.TCP_Socket.recv(1024)
                # Check if socket is closed
                if not data:
                    raise ConnectionError
                logging.info("Received: " + data.decode('utf-8'))
                data = data.decode('utf-8')
                print("\n", data)
                with self.condition:
                    self.condition.notify_all()
            # Handles timeout error
            except timeout:
                print(random.choice(self.colors) + "Connection timed out")
                continue
            except ConnectionError or ConnectionResetError:
                print(random.choice(self.colors) + "Connection closed")
                if not self.done:
                    self.done = True
                    with self.condition:
                        self.condition.notify_all()
                break

    def send_data_to_server(self):
        # Sends data to the server.
        while not self.done:
            try:
                # Input timeout for 5 seconds
                message = random.choice(["Y", "N"])
                self.TCP_Socket.send(message.encode())
                logging.info("Sent: " + message)
                print(random.choice(self.colors) + "Sent: " + message)
                with self.condition:
                    self.condition.wait()
                time.sleep(1)
            except ConnectionError:
                print(random.choice(self.colors) + "Connection closed")
                self.done = True
                break



if __name__ == "__main__":
    bot = Bot(13117)
    bot.main_loop()
