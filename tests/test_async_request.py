from multiprocessing import Queue
from random import randint

from pade.acl.aid import AID
from pade.acl.messages import ACLMessage

from pade.behaviours.highlevel import *
from pade.plus.agent import ImprovedAgent

from conftest import start_loop_test


def test_async_fipa_request(start_runtime):
    queue = Queue()

    class Sender(ImprovedAgent):
        def __init__(self, receiver_aid):
            super().__init__(AID(f'sender@localhost:{randint(9000, 60000)}'), True)
            self.request = FipaRequestProtocol(self, is_initiator=True)
            self.receiver = receiver_aid
            self.call_later(5, self.make_request)

        def make_request(self):
            print('making request')

            @FipaSession.session
            def async_request():
                message = ACLMessage()
                message.set_content('request')
                message.add_receiver(self.receiver)
                while True:
                    try:
                        response = yield self.request.send_request(message)
                        print('informed')

                        queue.put_nowait(response.performative == ACLMessage.INFORM)
                        queue.put_nowait(response.content == 'inform')

                    except FipaAgreeHandler as m:
                        response = m.message
                        print('agreed')

                        queue.put_nowait(response.performative == ACLMessage.AGREE)
                        queue.put_nowait(response.content == 'agree')

                    except FipaProtocolComplete:
                        break


                message = ACLMessage()
                message.set_content('request')
                message.add_receiver(self.receiver)
                while True:
                    try:
                        response = yield self.request.send_request(message)
                        print('informed2')

                        queue.put_nowait(response.performative == ACLMessage.INFORM)
                        queue.put_nowait(response.content == 'inform')

                    except FipaAgreeHandler as m:
                        response = m.message
                        print('agreed2')

                        queue.put_nowait(response.performative == ACLMessage.AGREE)
                        queue.put_nowait(response.content == 'agree')

                    except FipaProtocolComplete:
                        break

                queue.put_nowait(True)

            async_request()

    class Receiver(ImprovedAgent):
        def __init__(self):
            super().__init__(AID(f'receiver@localhost:{randint(9000, 60000)}'), True)
            self.request = FipaRequestProtocol(self, is_initiator=False)
            self.request.set_request_handler(self.on_request)

        def on_request(self, message):
            print('on request')
            queue.put_nowait(message.performative == ACLMessage.REQUEST)
            queue.put_nowait(message.content == 'request')

            response = message.create_reply()
            response.set_content('agree')
            self.request.send_agree(response)

            response = message.create_reply()
            response.set_content('inform')
            self.request.send_inform(response)

    receiver = Receiver()
    sender = Sender(receiver.aid)

    sender.ams = start_runtime
    receiver.ams = start_runtime

    with start_loop_test([sender, receiver]):
        assert all(queue.get(timeout=30) for i in range(13))



