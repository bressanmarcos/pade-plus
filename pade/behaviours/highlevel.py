from typing import Any, Callable
from functools import wraps

from pade.acl.messages import ACLMessage
from pade.behaviours.protocols import Behaviour
from pade.core.agent import Agent


class FipaProtocolComplete(Exception):
    """General handler to signal protocol completion"""


class FipaCfpComplete(FipaProtocolComplete):
    """Handler to signal CFP phase completion"""


class FipaMessageHandler(Exception):
    """General handler for FIPA messages"""

    def __init__(self, message: ACLMessage):
        self.message = message
        super().__init__(message)


class FipaAgreeHandler(FipaMessageHandler):
    """Exception handler for FIPA-AGREE messages"""


class FipaRefuseHandler(FipaMessageHandler):
    """Exception handler for FIPA-REFUSE messages"""


class FipaProposeHandler(FipaMessageHandler):
    """Exception handler for FIPA-REFUSE messages"""


class FipaInformHandler(FipaMessageHandler):
    """Exception handler for FIPA-INFORM messages"""


class FipaFailureHandler(FipaMessageHandler):
    """Exception handler for FIPA-FAILURE messages"""


class FipaRejectProposalHandler(FipaMessageHandler):
    """Exception handler for FIPA-REJECT-PROPOSAL messages"""


class GenericFipaProtocol(Behaviour):
    def __init__(self, agent):
        super().__init__(agent)
        agent.behaviours.append(self)

    def synchronize(self, async_f):
        @wraps(async_f)
        def synchronized(*args, **kwargs):
            return self.run(async_f(*args, **kwargs))
        return synchronized

    def run(self, generator):
        pass

    def send_not_understood(self, message: ACLMessage):

        message.set_performative(ACLMessage.NOT_UNDERSTOOD)

        # Send message to all receivers
        self.agent.send(message)

        return message


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

    def delete_session(self, session_id):
        """Delete an open session and terminate protocol session"""

        try:
            generator = self.open_sessions.pop(session_id)
        except KeyError:
            pass
        else:
            # Signal protocol completion if it's the last message
            try:
                generator.throw(FipaProtocolComplete)
            except (StopIteration, FipaProtocolComplete):
                pass

    def send_request(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.REQUEST)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def run(self, generator) -> None:
        """Register generator before sending message."""
        message = next(generator)
        # Only individual messages
        assert len(message.receivers) == 1

        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator
        # The session expires in 1 minute by default
        self.agent.call_later(60, lambda: self.delete_session(session_id))


class FipaRequestProtocolParticipant(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)
        self.callbacks = []

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super(FipaRequestProtocolParticipant, self).execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_REQUEST_PROTOCOL:
            return

        # Filter for performative
        if not message.performative == ACLMessage.REQUEST:
            return

        for callback in self.callbacks:
            callback(message)

    def add_request_handler(self, callback: Callable[[ACLMessage], Any]):
        """Add function to be called for request"""
        self.callbacks.append(callback)

    def send_inform(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.INFORM)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_agree(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.AGREE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

        return message


def FipaRequestProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaRequestProtocolInitiator(agent)
    else:
        return FipaRequestProtocolParticipant(agent)


class FipaSubscribeProtocolInitiator(GenericFipaProtocol):

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

    def delete_session(self, session_id):
        """Delete an open session and terminate protocol session"""

        try:
            generator = self.open_sessions.pop(session_id)
        except KeyError:
            pass
        else:
            # Signal protocol completion if it's the last message
            try:
                generator.throw(FipaProtocolComplete)
            except (StopIteration, FipaProtocolComplete):
                pass

    def send_subscribe(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.SUBSCRIBE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def run(self, generator) -> None:
        """Register generator before sending message."""
        message = next(generator)

        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator


class FipaSubscribeProtocolParticipant(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)
        self.callbacks = []
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

        for callback in self.callbacks:
            callback(message)

    def subscribe(self, subscribe_message: ACLMessage):
        """Add new subscriber by registering its subscribe message"""
        self._subscribers.add(subscribe_message)

    def unsubscribe(self, aid):
        """Remove subscriber"""
        subscribe_message = next(
            subscribe_message for subscribe_message in self._subscribers
            if subscribe_message.sender == aid)
        self._subscribers.remove(subscribe_message)

    def add_subscribe_handler(self, callback: Callable[[ACLMessage], Any]):
        """Add function to be called on subscribe"""
        self.callbacks.append(callback)

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

        return message

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)
        for subscriber in self._subscribers:
            message.add_receiver(subscriber)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_agree(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.AGREE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_SUBSCRIBE_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

        return message


def FipaSubscribeProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaSubscribeProtocolInitiator(agent)
    else:
        return FipaSubscribeProtocolParticipant(agent)


class FipaContractNetProtocolInitiator(GenericFipaProtocol):

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
        if not message.protocol == ACLMessage.FIPA_CONTRACT_NET_PROTOCOL:
            return

        # Filter for session_id (conversation_id)
        session_id = message.conversation_id
        if session_id not in self.open_sessions:
            return

        (generator, n_receivers) = self.open_sessions[session_id]

        # CFP Phase
        if n_receivers is not None:

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

        # First phase: CFP
        if n_receivers is not None:
            # Count remaining messages to be received
            n_receivers -= 1

            self.open_sessions[session_id] = (generator, n_receivers)

            if n_receivers == 0:
                # End of CFP
                self.end_cfp(session_id)

        # Second phase: Result
        else:
            self.delete_session(session_id)

    def end_cfp(self, session_id):
        """Terminate cfp phase"""

        try:
            (generator, n_receivers) = self.open_sessions[session_id]
        except KeyError:
            pass
        else:
            # Signal cfp completion, getting 0 n_receivers in case of timeout
            if n_receivers is not None:
                self.open_sessions[session_id] = (generator, None)
                try:
                    generator.throw(FipaCfpComplete)
                except (StopIteration, FipaCfpComplete):
                    pass

    def delete_session(self, session_id):
        """Delete an open session and terminate protocol session"""
        try:
            (generator, n_receivers) = self.open_sessions.pop(session_id)
        except KeyError:
            pass
        else:
            # Signal protocol completion if it's the last message
            try:
                generator.throw(FipaProtocolComplete)
            except (StopIteration, FipaProtocolComplete):
                pass

    def send_cfp(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.CFP)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_accept_proposal(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.ACCEPT_PROPOSAL)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_reject_proposal(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.REJECT_PROPOSAL)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def run(self, generator) -> None:
        """Register generator before sending message."""
        message = next(generator)
        n_receivers = len(message.receivers)
        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = (generator, n_receivers)
        # Set timeout to CFP
        self.agent.call_later(30, lambda: self.end_cfp(session_id))
        # The session expires in 1 minute by default
        self.agent.call_later(60, lambda: self.delete_session(session_id))


class FipaContractNetProtocolParticipant(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)
        self.cfp_handlers = []
        self.open_sessions = {}

    def execute(self, message: ACLMessage):
        """Called whenever the agent receives a message.
        The message was NOT yet filtered in terms of:
        protocol, conversation_id or performative."""
        super().execute(message)

        # Filter for protocol
        if not message.protocol == ACLMessage.FIPA_CONTRACT_NET_PROTOCOL:
            return

        if message.performative == ACLMessage.CFP:
            for cfp_handler in self.cfp_handlers:
                cfp_handler(message)
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

    def delete_session(self, session_id):
        """Delete an open session and terminate protocol session"""
        try:
            del self.open_sessions[session_id]
        except KeyError:
            pass

    def add_cfp_handler(self, callback: Callable[[ACLMessage], Any]):
        """Add function to be called on cfp"""

        self.cfp_handlers.append(callback)

    def send_inform(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.INFORM)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_propose(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.PROPOSE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

        return message

    def run(self, generator) -> None:
        """Register generator before sending message."""
        message = next(generator)
        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator
        # The session expires in 1 minute by default
        self.agent.call_later(60, lambda: self.delete_session(session_id))


def FipaContractNetProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaContractNetProtocolInitiator(agent)
    else:
        return FipaContractNetProtocolParticipant(agent)
