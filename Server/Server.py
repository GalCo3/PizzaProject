import socket


class Server:
    def __init__(self,port):
        self.port = port
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind(('localhost', self.port))
        self.server.listen(5)

    def start(self):
        while True:
            client, addr = self.server.accept()
            print("Connection from: " + str(addr))
            client.send("Hello".encode())
            client.close()

    def close(self):
        self.server.close()
