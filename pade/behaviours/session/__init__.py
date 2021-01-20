from functools import wraps

from pade.behaviours.protocols import Behaviour
from pade.acl.messages import ACLMessage

from .exceptions import *


class FipaSession():
    @staticmethod
    def session(async_f):
        """Converts generator function into a callable function"""
        @wraps(async_f)
        def synchronized(*args, **kwargs):
            return FipaSession.run(async_f(*args, **kwargs))
        return synchronized

    @staticmethod
    def run(generator, continuation=False) -> None:
        """Register generator before sending message."""

        try:
            if continuation:
                # Signal last protocol completion
                protocol, message = generator.throw(FipaProtocolComplete)
            else:
                protocol, message = next(generator)

            protocol.register_session(message, generator)

        except TypeError:
            pass
        except (StopIteration, FipaProtocolComplete):
            pass


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
            FipaSession.run(generator, continuation=True)