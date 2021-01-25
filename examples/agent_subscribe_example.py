import time
from random import randint
from functools import reduce

from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.highlevel import *
from pade.behaviours.highlevel import FipaSubscribeProtocol
from pade.plus.agent import ImprovedAgent
from pade.misc.utility import display_message, start_loop
from pade.misc.utility import defer_to_thread, call_in_thread


class Subscriber(ImprovedAgent):

    def __init__(self, aid, publisher_aid):
        super().__init__(aid=aid, debug=False)
        self.subscribe = FipaSubscribeProtocol(self,
                                               is_initiator=True)
        self.call_later(5.0, lambda: self.call_subscribe(publisher_aid))

    @AgentSession.session
    def call_subscribe(self, publisher_aid):
        # Message to send
        message = ACLMessage()
        message.set_content('Subscribe me, please!')
        message.add_receiver(publisher_aid)

        while True:
            try:
                # Expecting INFORM by default
                inform = yield self.subscribe.send_subscribe(message)
                display_message(
                    self.aid.name,
                    f'I received INFORM: {inform.content} from {inform.sender.name}'
                )
            except FipaAgreeHandler as h:
                agree = h.message
                display_message(
                    self.aid.name,
                    f'I received AGREE: {agree.content} from {agree.sender.name}'
                )
            except FipaRefuseHandler as h:
                refusal = h.message
                display_message(
                    self.aid.name,
                    f'I received REFUSE: {refusal.content} from {refusal.sender.name}'
                )
            except FipaFailureHandler as h:
                failure = h.message
                display_message(
                    self.aid.name,
                    f'I received FAILURE: {failure.content} from {failure.sender.name}'
                )
            except FipaProtocolComplete:
                break


class Publisher(ImprovedAgent):
    def __init__(self, aid):
        super().__init__(aid=aid, debug=False)
        self.subscribe = FipaSubscribeProtocol(self,
                                               is_initiator=False)
        self.subscribe.set_subscribe_handler(self.on_subscribe)

        # informer
        def informer():
            inform = ACLMessage()
            inform.set_content(str(randint(0, 1000)))
            self.subscribe.send_inform(inform)

            self.call_later(5.0, informer)
        informer()

    def on_subscribe(self, message):
        display_message(
            self.aid.name,
            f'I received SUBSCRIBE: {message.content} from {message.sender.name}'
        )
        reply = message.create_reply()

        if randint(0, 1000) > 750:
            # Refuse
            self.subscribe.send_refuse(reply)
            return

        # AGREE
        self.subscribe.send_agree(reply)
        self.subscribe.subscribe(message)

if __name__ == "__main__":
    agents = list()

    # Sender
    publisher = Publisher(
        AID("publisher@localhost:50000")
    )
    agents.append(publisher)

    # Contractors
    for i in range(3):
        subscriber = Subscriber(
            AID(f"subscriber{i}@localhost:{60000+i}"), publisher.aid)
        agents.append(subscriber)


    start_loop(agents)
