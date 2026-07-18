"""Domain exceptions for the node app."""


class NodeError(Exception):
    """Base exception for node domain errors."""


class NodeNotFoundError(NodeError):
    """Node or organization context could not be resolved."""


class TaskError(NodeError):
    """Runtime task lifecycle error."""


class AgentTaskNotFoundError(TaskError):
    """``NodeTask`` row not found."""


class AgentTaskTimeoutError(TaskError):
    """Synchronous wait exceeded without a terminal task outcome."""


class EnrollmentError(NodeError):
    """Enrollment or artifact auth error."""


class AgentUpgradeError(NodeError):
    """Remote agent upgrade rejected before dispatch."""

    def __init__(self, message: str, *, code: str = "upgrade_rejected") -> None:
        super().__init__(message)
        self.code = code


class NodeLifecycleError(NodeError):
    """Node lifecycle operation rejected or failed."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "lifecycle_rejected",
        blockers: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.blockers = blockers or []
