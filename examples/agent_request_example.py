import time
from random import randint

from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.behaviours.highlevel import *
from pade.behaviours.highlevel import FipaRequestProtocol
from pade.plus.agent import ImprovedAgent
from pade.misc.utility import display_message, start_loop
from pade.misc.utility import defer_to_thread, call_in_thread


class Sender(ImprovedAgent):

    def __init__(self, aid, recipients_aid, debug=False):
        super(Sender, self).__init__(aid, debug)
        self.request_behavior = FipaRequestProtocol(self, is_initiator=True)
        self.call_later(15.0, lambda: self.on_time(recipients_aid))

    def on_time(self, recipients_aid):

        @FipaSession.session
        def async_request(receiver):
            # Message to send
            message = ACLMessage()
            message.set_content('Would you do me a favor?')
            message.add_receiver(receiver)
            
            while True:

                try:
                    response_message = yield self.request_behavior.send_request(message)
                    content = response_message.content
                    display_message(self.aid.name, f'I received INFORM: {content} from {response_message.sender.name}')
                
                except FipaAgreeHandler as e:
                    response_message = e.message
                    content = response_message.content
                    display_message(self.aid.name, f'I received AGREE: {content} from {response_message.sender.name}')

                except FipaProtocolComplete as e:
                    display_message(self.aid.name, f'I received all messages from {receiver.name}!')
                    break

        for receiver in recipients_aid:
            async_request(receiver)


class Recipient(ImprovedAgent):
    def __init__(self, aid, calculator_aid, debug=False):
        super(Recipient, self).__init__(aid, debug)
        self.calculator_aid = calculator_aid
        self.inform_behavior = FipaRequestProtocol(self, is_initiator=False)
        self.inform_behavior.set_request_handler(self.on_request)
        self.consult_behavior = FipaRequestProtocol(self, is_initiator=True)

    def on_request(self, message):
        content = message.content
        display_message(self.aid.name, f'I received REQUEST: {content} from {message.sender.name}')

        reply_agree = message.create_reply()
        reply_agree.set_content('OK, I`ll do it, wait for me!')
        self.inform_behavior.send_agree(reply_agree)

        def do_long_job():
            # Massive calculations part I
            display_message(self.aid.name, f'Doing long job')
            time.sleep(1.5)
            question = f'{randint(1, 50)}+{randint(100, 150)}'

            return question

        def do_long_job_callback(question):

            @FipaSession.session
            def async_request():
                request_calc = ACLMessage()
                request_calc.set_content(question)
                request_calc.add_receiver(self.calculator_aid)
                
                while True:
                    try:
                        response_calc = yield self.consult_behavior.send_request(request_calc)
                        display_message(
                            self.aid.name, 
                            f'I received INFORM: {response_calc.content} from {response_calc.sender.name}'
                        )
                    except FipaProtocolComplete:
                        break
                
                def more_long_job():
                    # Massive calculations part II
                    display_message(self.aid.name, f'Doing second long job')
                    time.sleep(1.25)

                    return response_calc.content
                
                def more_long_job_callback(result):
                    # There is still a reference to the incoming request
                    display_message(self.aid.name, f'Calling callback')
                    reply_inform = message.create_reply()
                    reply_inform.set_content(f'The result is: {result}')
                    self.inform_behavior.send_inform(reply_inform)

                # Another blocking method in other thread, this time using callback
                defer_to_thread(more_long_job, more_long_job_callback)

            # Async method using reactor, must be called from reactor thread    
            async_request()

        # Blocking method, must be called from another thread
        defer_to_thread(do_long_job, do_long_job_callback)



class Calculator(ImprovedAgent):
    def __init__(self, aid, debug=False):
        super(Calculator, self).__init__(aid, debug)
        self.calculator_behaviour = FipaRequestProtocol(self, is_initiator=False)
        self.calculator_behaviour.set_request_handler(self.on_request)
        self.behaviours.append(self.calculator_behaviour)

    def on_request(self, message: ACLMessage):
        content = message.content
        display_message(self.aid.name, f'I received REQUEST: {content} from {message.sender.name}')

        reply = message.create_reply()
        reply.set_content(str(eval(content)))
        self.calculator_behaviour.send_inform(reply)

if __name__ == "__main__":
    agents = list()

    # Calculator agent
    calculator_agent = Calculator(AID('calculator@localhost:55000'), debug=True)
    agents.append(calculator_agent)

    # Recipients
    recipient_agent_1 = Recipient(AID("bravo@localhost:52000"), calculator_agent.aid, debug=True)
    agents.append(recipient_agent_1)

    recipient_agent_2 = Recipient(AID("charlie@localhost:50001"), calculator_agent.aid, debug=True)
    agents.append(recipient_agent_2)

    # Sender
    sender_agent = Sender(
        AID("alfa@localhost:61000"), 
        [recipient_agent_1.aid],
        debug=True
    )
    agents.append(sender_agent)

    start_loop(agents)
