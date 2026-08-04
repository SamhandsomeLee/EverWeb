"""Competition-layer errors for unresolved template semantics."""


class PendingTemplateError(RuntimeError):
    """Raised when a competition template capability is still unresolved."""
