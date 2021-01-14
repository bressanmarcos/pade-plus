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


class FipaNotUnderstoodHandler(FipaMessageHandler):
    """Exception handler for FIPA-NOT-UNDERSTOOD messages"""


class FipaSession():
    @staticmethod
    def session(async_f):
        """Converts generator function into a callable function"""
        @wraps(async_f)
        def synchronized(*args, **kwargs):
            return FipaSession.run(async_f(*args, **kwargs))
        return synchronized

    @staticmethod
    def run(generator) -> None:
        """Register generator before sending message."""
        protocol, message = next(generator)
        protocol.register_session(message, generator)


class GenericFipaProtocol(Behaviour):
    def __init__(self, agent):
        super().__init__(agent)
        agent.behaviours.append(self)
        
        self.open_sessions = {}

    def send_not_understood(self, message: ACLMessage):

        message.set_performative(ACLMessage.NOT_UNDERSTOOD)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def register_session(self, message, generator) -> None:
        """Register generator to receive response."""
        raise NotImplementedError

    def delete_session(self, session_id) -> None:
        """Delete an open session and terminate protocol session"""

        try:
            generator = self.open_sessions.pop(session_id)
        except KeyError:
            pass
        else:
            # Signal protocol completion if it's the last message
            try:
                next_ = generator.throw(FipaProtocolComplete)
            except (StopIteration, FipaProtocolComplete):
                pass
            else:
                try:
                    protocol, message = next_
                    protocol.register_session(message, generator)
                except TypeError:
                    pass


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

        if message.conversation_id not in self.open_sessions:
            """Ensures that a message is only sent when there is no open
            session for it"""
            message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
            message.set_performative(ACLMessage.REQUEST)

            # Only individual messages
            assert len(message.receivers) == 1

            # Send message to all receivers
            self.agent.send(message)

            return self, message

    def register_session(self, message, generator) -> None:
        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator

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
        super(FipaRequestProtocolParticipant, self).execute(message)

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

        return self, message

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def send_agree(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.AGREE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_REQUEST_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message


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


class FipaContractNetProtocolInitiator(GenericFipaProtocol):

    def __init__(self, agent):
        super().__init__(agent)

        # Denote each open request. It is possible to have multiple
        # sessions with a same party.
        # The pair (conversation_id) represents a unique session.
        self.open_sessions = {}
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

        # First phase: CFP
        if params['cfp_phase']:
            params['receivers'][message.sender].add(message.performative)

            if all(
                params['receivers'][r] & {
                    ACLMessage.PROPOSE, ACLMessage.REFUSE}
                for r in params['receivers']
            ):
                # End of CFP
                self.end_cfp(session_id)

        # Second phase: Result
        else:
            if all(
                params['receivers'][r] & {
                    ACLMessage.INFORM, ACLMessage.FAILURE}
                for r in params['receivers']
                if params['receivers'][r] & {ACLMessage.PROPOSE}
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

        if message.conversation_id not in self.open_sessions:
            """Ensures that a message is only sent when there is no open
            session for it"""
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            message.set_performative(ACLMessage.CFP)

            # Send message to all receivers
            self.agent.send(message)

            return self, message

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

        return self, message

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

        return self, message

    def register_session(self, message, generator) -> None:

        receivers = message.receivers
        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator
        self.session_params[session_id] = {
            'cfp_phase': True,
            'receivers': {r: set() for r in receivers}
        }
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

    def send_inform(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.INFORM)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def send_failure(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.FAILURE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def send_propose(self, message: ACLMessage):

        if message.conversation_id not in self.open_sessions:
            """Ensures that a message is only sent when there is no open
            session for it"""
            message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
            message.set_performative(ACLMessage.PROPOSE)

            # Send message to all receivers
            self.agent.send(message)

        return self, message

    def send_refuse(self, message: ACLMessage):

        message.set_protocol(ACLMessage.FIPA_CONTRACT_NET_PROTOCOL)
        message.set_performative(ACLMessage.REFUSE)

        # Send message to all receivers
        self.agent.send(message)

        return self, message

    def register_session(self, message, generator) -> None:

        # Register generator in session
        session_id = message.conversation_id
        self.open_sessions[session_id] = generator
        # The session expires in 1 minute by default
        self.agent.call_later(60, self.delete_session, session_id)


def FipaContractNetProtocol(agent: Agent, is_initiator=True):

    if is_initiator:
        return FipaContractNetProtocolInitiator(agent)
    else:
        return FipaContractNetProtocolParticipant(agent)
