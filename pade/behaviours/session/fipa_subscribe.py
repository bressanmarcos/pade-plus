from typing import Any, Callable

from pade.acl.messages import ACLMessage
from pade.core.agent import Agent

from . import GenericFipaProtocol
from .exceptions import *


class FipaSubscribeProtocolInitiator(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_SUBSCRIBE_PROTOCOL:
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
        if message.performative in (ACLMessage.REFUSE, ACLMessage.FAILURE):
            self.delete_session(session_id)

    def send_subscribe(self, message: ACLMessage):

        if message.conversation_id not in self.open_sessions:
            """Ensures that a message is only sent when there is no open
            session for it"""
            message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
            message.set_performative(ACLMessage.SUBSCRIBE)

            # Send message to all receivers
            self.agent.send(message)

            return self, message

    def register_session(self, message, generator) -> None:
        """Register generator to receive response."""

        session_id = message.conversation_id
        self.open_sessions[session_id] = generator


class FipaSubscribeProtocolParticipant(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)
        self.callback = None
        self._subscribers = set()

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_SUBSCRIBE_PROTOCOL:
            return

        # Filter for performative
        if not message.performative == ACLMessage.SUBSCRIBE:
            return

        self.callback(message)

    def subscribe(self, subscribe_message: ACLMessage):
        """Add new subscriber by registering its subscribe message"""
        self._subscribers.add(subscribe_message)

    def unsubscribe(self, aid):
        """Remove subscriber"""
        subscribe_message = next(
            subscribe_message for subscribe_message in self._subscribers
            if subscribe_message.sender == aid)
        self._subscribers.remove(subscribe_message)

    def set_subscribe_handler(self, callback: Callable[[ACLMessage], Any]):
        """Add function to be called on subscribe"""
        self.callback = callback

    def send_inform(self, message: ACLMessage):

        for subscribe_message in self._subscribers:
            inform = subscribe_message.create_reply()
            inform.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
            inform.set_performative(ACLMessage.INFORM)
            inform.set_content(message.content)
            inform.set_language(message.language)
            inform.set_ontology(message.ontology)
            inform.set_encoding(message.encoding)

            # Send message to subscriber
            self.agent.send(inform)

        return self, message

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)
        for subscriber in self._subscribers:
            message.add_receiver(subscriber)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def send_agree(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.AGREE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message


def FipaSubscribeProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaSubscribeProtocolInitiator(agent)
    else:
        return FipaSubscribeProtocolParticipant(agent)
