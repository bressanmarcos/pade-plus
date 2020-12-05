import time
from random import randint
from functools import reduce

from pade.acl.aid import AID
from pade.acl.messages import ACLMessage
from pade.misc.utility import display_message, start_loop
from pade.misc.utility import defer_to_thread, call_in_thread

from pade.behaviours.highlevel import *
from pade.behaviours.highlevel import FipaContractNetProtocol
from pade.plus.agent import ImprovedAgent

class Manager(ImprovedAgent):

    def __init__(self, aid, recipients_aid):
        super().__init__(aid=aid, debug=False)
        self.contract_net = FipaContractNetProtocol(self,
                                                    is_initiator=True)
        self.call_later(5.0, lambda: self.call_proposals(recipients_aid))

    def call_proposals(self, recipients_aid):

        @self.contract_net.synchronize
        def async_cfp():
            # Message to send
            message = ACLMessage()
            message.set_content('Send me proposals, please!')
            for r in recipients_aid:
                message.add_receiver(r)

            self.contract_net.send_cfp(message)
            proposals_received = []

            while True:
                try:
                    # Expecting PROPOSAL by default
                    proposal = yield message
                    display_message(
                        self.aid.name,
                        f'I received PROPOSE: {proposal.content} from {proposal.sender.name}'
                    )
                    proposals_received.append(proposal)
                except FipaRefuseHandler as h:
                    refusal = h.message
                    display_message(
                        self.aid.name,
                        f'I received REFUSE: {refusal.content} from {refusal.sender.name}'
                    )
                except FipaCfpComplete:
                    break

            try:
                best_value = max(int(m.content) for m in proposals_received)
            except ValueError:
                display_message(
                    self.aid.name,
                    f'No proposals!'
                )
                return

            best_proposal = next(m for m in proposals_received if int(m.content) == best_value)

            # Reject message
            for message in filter(lambda m: m != best_proposal, proposals_received):
                reply = message.create_reply()
                reply.set_content('Rejected, sorry!')
                # It does not create a session
                self.contract_net.send_reject_proposal(reply)

            # Accept message
            reply = best_proposal.create_reply()
            reply.set_content('Accepted!')
            # It creates a session
            self.contract_net.send_accept_proposal(reply)

            try:
                # Expects INFORM by default
                inform = yield reply
                content = inform.content
                display_message(
                    self.aid.name,
                    f'I received INFORM: {content} from {inform.sender.name}'
                )
            except FipaFailureHandler as h:
                failure = h.message


        async_cfp()

class Contractor(ImprovedAgent):
    def __init__(self, aid):
        super().__init__(aid=aid, debug=False)
        self.contract_net = FipaContractNetProtocol(self,
                                                    is_initiator=False)
        self.contract_net.add_cfp_handler(self.on_cfp)

    def on_cfp(self, message):
        display_message(
            self.aid.name,
            f'I received CFP: {message.content} from {message.sender.name}'
        )
        reply = message.create_reply()

        if randint(0, 1000) > 750:
            # Refuse
            self.contract_net.send_refuse(reply)
            return

        # Propose
        reply.set_content(str(randint(0, 1000)))

        @self.contract_net.synchronize
        def async_propose():
            self.contract_net.send_propose(reply)
            # Wait for response
            try:
                accept_proposal = yield reply
                display_message(
                    self.aid.name,
                    f'I received ACCEPT-PROPOSAL: {accept_proposal.content} from {accept_proposal.sender.name}'
                )
                # I'mma do some job in another thread
                def job():
                    display_message(
                        self.aid.name,
                        f"I'mma do my job"
                    )
                    time.sleep(5)
                    return 10*int(reply.content)

                def job_callback(value):
                    inform_message = accept_proposal.create_reply()
                    inform_message.set_content(value)
                    # Use reactor thread to send final results
                    self.contract_net.send_inform(inform_message)

                defer_to_thread(job, job_callback)

            except FipaRejectProposalHandler as h:
                reject_proposal = h.message
                display_message(
                    self.aid.name,
                    f'I received REJECT-PROPOSAL: {reject_proposal.content} from {reject_proposal.sender.name}'
                )
        
        async_propose()

if __name__ == "__main__":
    agents = list()

    # Contractors
    for i in range(20):
        contractor = Contractor(AID(f"contractor{i}@localhost:{60000+i}"))
        agents.append(contractor)

    # Sender
    sender_agent = Manager(
        AID("manager@localhost:50000"),
        [a.aid for a in agents]
    )
    agents.append(sender_agent)

    start_loop(agents)
