class PBACApplicationError(Exception):
    """Base class for expected application errors to catch them."""

class ConfigurationError(PBACApplicationError):
    """Raised when required application configuration is absent or invalid."""

class JSONConfigurationError(PBACApplicationError):
    """Raised when a JSON configuration file cannot be loaded or validated."""