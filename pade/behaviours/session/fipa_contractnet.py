from typing import Any, Callable

from pade.acl.messages import ACLMessage
from pade.core.agent import Agent

from . import GenericFipaProtocol
from . import AgentSession
from .exceptions import *


class FipaContractNetProtocolInitiator(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)

        # Denote each open request. It is possible to have multiple
        # sessions with a same party.
        # The pair (conversation_id) represents a unique session.
        self.session_params = {}

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_CONTRACT_NET_PROTOCOL:
            return

        # Filter for session_id (conversation_id)
        session_id = message.conversation_id
        if session_id not in self.open_sessions:
            return

        generator = self.open_sessions[session_id]
        params = self.session_params[session_id]

        # CFP Phase
        if params['cfp_phase']:
            handlers = {
                ACLMessage.PROPOSE: lambda: generator.send(message),
                ACLMessage.REFUSE: lambda: generator.throw(
                    FipaRefuseHandler, message)
            }

        # Result phase
        else:
            handlers = {
                ACLMessage.INFORM: lambda: generator.send(message),
                ACLMessage.FAILURE: lambda: generator.throw(
                    FipaFailureHandler, message)
            }

        # Resume generator
        try:
            handlers[message.performative]()
        except StopIteration:
            pass
        except KeyError:
            return

        params['receivers'][message.sender].add(message.performative)

        # First phase: CFP
        if params['cfp_phase']:

            if all(
                receiver_msgs & {
                    ACLMessage.PROPOSE, ACLMessage.REFUSE}
                for receiver_msgs in params['receivers'].values()
            ):
                # End of CFP
                self.end_cfp(session_id)

        # Second phase: Result
        else:

            if all(
                receiver_msgs & {
                    ACLMessage.INFORM, ACLMessage.FAILURE}
                for receiver_msgs in params['receivers'].values()
                if receiver_msgs & {ACLMessage.ACCEPT_PROPOSAL}
            ):
                self.delete_session(session_id)

    def end_cfp(self, session_id):
        """Terminate cfp phase"""

        try:
            generator = self.open_sessions[session_id]
            params = self.session_params[session_id]
        except KeyError:
            pass
        else:
            # Signal cfp completion
            if params['cfp_phase']:
                params['cfp_phase'] = False

                try:
                    generator.throw(FipaCfpComplete)
                except (StopIteration, FipaCfpComplete):
                    pass

    def send_cfp(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.CFP)

        response = yield AgentSession(self, message)
        return response

    def send_accept_proposal(self, message: ACLMessage):

        session_id = message.conversation_id
        receiver = message.receivers[0]
        receiver_msgs = self.session_params[session_id]['receivers'][receiver]

        if not receiver_msgs & {ACLMessage.ACCEPT_PROPOSAL, ACLMessage.REJECT_PROPOSAL}:

            receiver_msgs.add(ACLMessage.ACCEPT_PROPOSAL)

            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            message.set_performative(ACLMessage.ACCEPT_PROPOSAL)

            # Send message to all receivers
            self.agent.send(message)

        response = yield
        return response

    def send_reject_proposal(self, message: ACLMessage):

        session_id = message.conversation_id
        receiver = message.receivers[0]
        receiver_msgs = self.session_params[session_id]['receivers'][receiver]

        if not receiver_msgs & {ACLMessage.ACCEPT_PROPOSAL, ACLMessage.REJECT_PROPOSAL}:

            receiver_msgs.add(ACLMessage.REJECT_PROPOSAL)

            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            message.set_performative(ACLMessage.REJECT_PROPOSAL)

            # Send message to all receivers
            self.agent.send(message)

    def register_session(self, message, generator) -> None:

        receivers = message.receivers
        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator
        self.session_params[session_id] = {
            'cfp_phase': True,
            'receivers': {r: set() for r in receivers}
        }

        # Send cfp message now
        self.agent.send(message)

        # Set timeout to CFP
        self.agent.call_later(30, self.end_cfp, session_id)
        # The session expires in 1 minute by default
        self.agent.call_later(60, self.delete_session, session_id)

    def delete_session(self, session_id):

        try:
            params = self.session_params.pop(session_id)
        except KeyError:
            pass

        super().delete_session(session_id)


class FipaContractNetProtocolParticipant(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)
        self.callback = None

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_CONTRACT_NET_PROTOCOL:
            return

        if message.performative == ACLMessage.CFP:
            self.callback(message)
            return

        # Filter for session_id (conversation_id)
        session_id = message.conversation_id
        if session_id not in self.open_sessions:
            return

        # Resume generator
        generator = self.open_sessions[session_id]
        handlers = {
            ACLMessage.ACCEPT_PROPOSAL: lambda: generator.send(message),
            ACLMessage.REJECT_PROPOSAL: lambda: generator.throw(
                FipaRejectProposalHandler, message)
        }
        try:
            handlers[message.performative]()
        except StopIteration:
            pass
        except KeyError:
            return

        # Clear session
        self.delete_session(session_id)

    def set_cfp_handler(self, callback: Callable[[ACLMessage], Any]):
        """Add function to be called on cfp"""

        self.callback = callback

    def send_propose(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.PROPOSE)

        response = yield AgentSession(self, message)
        return response

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

    def send_inform(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.INFORM)

        # Send message to all receivers
        self.agent.send(message)

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)

        # Send message to all receivers
        self.agent.send(message)

    def register_session(self, message, generator) -> None:

        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator

        # Send propose message now
        self.agent.send(message)

        # The session expires in 1 minute by default
        self.agent.call_later(60, self.delete_session, session_id)


def FipaContractNetProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaContractNetProtocolInitiator(agent)
    else:
        return FipaContractNetProtocolParticipant(agent)
