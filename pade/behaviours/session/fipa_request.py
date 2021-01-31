from typing import Any, Callable

from pade.acl.messages import ACLMessage
from pade.core.agent import Agent

from . import GenericFipaProtocol
from . import AgentSession
from .exceptions import *


class FipaRequestProtocolInitiator(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)

        # Denote each open request. It is possible to have multiple
        # sessions with a same party.
        # The pair (conversation_id) represents a unique session.
        self.open_sessions = {}

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_REQUEST_PROTOCOL:
            return

        # Filter for session_id (conversation_id)
        session_id = message.conversation_id
        if session_id not in self.open_sessions:
            return

        # Resume generator
        generator = self.open_sessions[session_id]
        handlers = {
            ACLMessage.INFORM: lambda: generator.send(message),
            ACLMessage.AGREE: lambda: generator.throw(FipaAgreeHandler, message),
            ACLMessage.REFUSE: lambda: generator.throw(FipaRefuseHandler, message),
            ACLMessage.FAILURE: lambda: generator.throw(
                FipaFailureHandler, message)
        }
        try:
            handlers[message.performative]()
        except StopIteration:
            pass
        except KeyError:
            return

        # Clear session if final message was received
        if message.performative in (ACLMessage.REFUSE, ACLMessage.INFORM, ACLMessage.FAILURE):
            self.delete_session(session_id)

    def send_request(self, message: ACLMessage):
        # Only individual messages
        assert len(message.receivers) == 1

        if message.conversation_id not in self.open_sessions:
            """Ensures that a message is only sent when there is no open
            session for it"""
            message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
            message.set_performative(ACLMessage.REQUEST)

            return AgentSession(self, message)

    def register_session(self, message, generator) -> None:
        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator

        # Send request message now
        self.agent.send(message)

        # The session expires in 1 minute by default
        self.agent.call_later(60, self.delete_session, session_id)


class FipaRequestProtocolParticipant(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)
        self.callback = None

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_REQUEST_PROTOCOL:
            return

        # Filter for performative
        if not message.performative == ACLMessage.REQUEST:
            return

        self.callback(message)

    def set_request_handler(self, callback: Callable[[ACLMessage], Any]):
        """Add function to be called for request"""
        self.callback = callback

    def send_inform(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.INFORM)

        # Send message to all receivers
        self.agent.send(message)

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)

        # Send message to all receivers
        self.agent.send(message)

    def send_agree(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.AGREE)

        # Send message to all receivers
        self.agent.send(message)

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)


def FipaRequestProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaRequestProtocolInitiator(agent)
    else:
        return FipaRequestProtocolParticipant(agent)
