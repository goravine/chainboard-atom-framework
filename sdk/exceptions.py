"""Framework exception hierarchy.

All layers raise subclasses of `FrameworkError`. Higher layers can catch
either the specific subclass or the base class. Add domain-specific
exceptions in your project's own SDK file rather than expanding this one.
"""


class FrameworkError(Exception):
    """Base for all framework-raised errors."""


class FrameworkConfigError(FrameworkError):
    """Configuration is missing, malformed, or contradictory."""


class FrameworkAuthError(FrameworkError):
    """Authentication or authorization failed."""


class FrameworkChainError(FrameworkError):
    """A ChainResult step failed and was required."""


class FrameworkStorageError(FrameworkError):
    """A storage / persistence layer failure."""
