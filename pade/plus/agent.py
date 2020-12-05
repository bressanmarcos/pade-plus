from pade.core.agent import Agent


class ImprovedAgent(Agent):
    def send(self, message, tries=10, interval=2.0):
        """
            Send message once all receivers addresses are
            available in agents table.
        """
        if tries == 0:
            return

        if hasattr(self, 'agentInstance') and \
                all(receiver.localname == 'ams' or \
                    receiver.name in self.agentInstance.table \
                        for receiver in message.receivers):
            super().send(message)
        else:
            self.call_later(interval, self.send,
                            message, tries-1, interval)
