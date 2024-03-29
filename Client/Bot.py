from Client import *


class Bot(Client):

    def __init__(self, portListen):
        super().__init__(portListen)
        self.name = "BOT_" + self.name
        

    
    def TCP_client(self):
        
        # set the timeout to 20 seconds
        self.TCP_Socket.settimeout(20)
        
        while not self.done:
            try:
                data = self.TCP_Socket.recv(1024)
                # check if socket is closed
                if not data:
                    raise ConnectionError
                
                answer = random.choice(["Y", "N"])
                
                time.sleep(random.random() * 4 + 1)
                self.TCP_Socket.send(answer.encode())
                print("Sent: " + answer)
                
            except ConnectionError:
                self.done = True
                self.TCP_Socket.close()
                break

            except timeout:
                continue


if __name__ == "__main__":
    bot = Bot(13117)
    bot.main_loop()
