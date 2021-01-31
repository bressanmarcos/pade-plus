import time
from random import randint

from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.highlevel import *
from pade.behaviours.highlevel import FipaRequestProtocol
from pade.plus.agent import ImprovedAgent
from pade.misc.utility import display_message, start_loop
from pade.misc.utility import call_later

class Client(ImprovedAgent):
    def __init__(self, aid, servers):
        super().__init__(aid)
        self.req = FipaRequestProtocol(self)
        self.servers = servers

    def on_start(self):
        super().on_start()
        self.make_request()

    def one_request(self, receiver):
        message = ACLMessage()
        message.add_receiver(receiver)
        while True:
            try:
                response = yield self.req.send_request(message)
            except FipaMessageHandler as h:
                response = h.message
            except FipaProtocolComplete:
                break
        return response

    @AgentSession.session
    def make_request(self):
        r1, r2 = yield AgentSession.gather(
            *(self.one_request(s) for s in self.servers)
        )
        display_message(self.aid.name, "Final response 1: " + r1.content)
        display_message(self.aid.name, "Final response 2: " + r2.content)


class Server(ImprovedAgent):
    def __init__(self, aid):
        super().__init__(aid)
        self.req = FipaRequestProtocol(self, False)
        self.req.set_request_handler(self.on_request)

    def on_request(self, message: ACLMessage):
        display_message(self.aid.name, "Received a message")
        reply = message.create_reply()
        reply.set_content(f'Take this! {randint(0, 100)}')
        delay = randint(0, 10)
        display_message(self.aid.name, "Starting job")
        print('Job delay:', delay)
        call_later(delay, self.req.send_inform, reply)

if __name__ == "__main__":
    agents = list()

    server1 = Server(AID(f'server1@localhost:{randint(2000, 65000)}'))
    agents.append(server1)

    server2 = Server(AID(f'server2@localhost:{randint(2000, 65000)}'))
    agents.append(server2)

    client = Client(AID(f'client@localhost:{randint(2000, 65000)}')
        , servers = [server1.aid, server2.aid])
    agents.append(client)


    start_loop(agents)
