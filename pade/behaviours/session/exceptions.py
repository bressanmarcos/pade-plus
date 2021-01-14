
class FipaProtocolComplete(Exception):
    """General handler to signal protocol completion"""


class FipaCfpComplete(FipaProtocolComplete):
    """Handler to signal CFP phase completion"""


class FipaMessageHandler(Exception):
    """General handler for FIPA messages"""

    def __init__(self, message):
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
