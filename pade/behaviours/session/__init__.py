from functools import wraps
from typing import Iterable
from collections.abc import Generator

from pade.behaviours.protocols import Behaviour
from pade.acl.messages import ACLMessage

from .exceptions import *


class GenericFipaProtocol(Behaviour):
    def __init__(self, agent):
        super().__init__(agent)
        agent.behaviours.append(self)

        self.open_sessions = {}

    def send_not_understood(self, message: ACLMessage):

        message.set_performative(ACLMessage.NOT_UNDERSTOOD)

        # Send message to all receivers
        self.agent.send(message)

        return AgentSession(self, message)

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
            AgentSession.run(generator, continuation=True)


class AgentSession():

    def __init__(self, protocol: GenericFipaProtocol, message: ACLMessage):
        self.protocol = protocol
        self.message = message

    def register(self, generator: Generator):
        """Register session in the interaction protocol"""
        return self.protocol.register_session(self.message, generator)

    @staticmethod
    def session(async_f):
        """Converts a generator function into a callable function
        that will resume the generator when a message is received."""
        @wraps(async_f)
        def synchronized(*args, **kwargs):
            return AgentSession.run(async_f(*args, **kwargs))
        return synchronized

    @staticmethod
    def run(generator: Generator, continuation=False) -> None:
        """Start or Resume a generator, saving the returned session
        into the referred protocol."""

        try:
            if continuation:
                # Signal last protocol completion
                session = generator.throw(FipaProtocolComplete)
            else:
                session = next(generator)

            session.register(generator)

        except TypeError:
            pass
        except (StopIteration, FipaProtocolComplete):
            pass

    @staticmethod
    def gather(*generators):
        return MultiSession(generators)


class MultiSession():

    @staticmethod
    def generate_queue(dest_generator, size):
        # Gather responses into a list
        results_list = []
        for _ in range(size):
            result = yield
            results_list.append(result)
        try:
            # Send responses back to caller
            dest_generator.send(results_list)
        except StopIteration:
            pass

    @staticmethod
    def generate_send_to_queue(generator, queue):
        # Modify generator to send result to queue
        result = yield from generator
        try:
            queue.send(result)
        except StopIteration:
            pass

    def __init__(self, generators: Iterable[Generator]):
        # dict AgentSession -> generator
        self.generators = list(generators)

    def register(self, outside_generator: Generator):
        """Register session in the interaction protocol"""

        response_queue = MultiSession.generate_queue(
            outside_generator, size=len(self.generators)
        )
        next(response_queue)

        for generator in self.generators:
            # Save modified generators into their respective Protocols
            modified = MultiSession.generate_send_to_queue(
                generator, queue=response_queue
            )
            session = next(modified)
            session.register(modified)
