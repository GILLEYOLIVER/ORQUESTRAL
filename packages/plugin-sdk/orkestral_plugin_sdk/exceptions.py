class PluginSDKError(RuntimeError):
    """Base segura para erros que podem atravessar a fronteira do plugin."""


class PluginNotFoundError(PluginSDKError):
    pass


class PluginValidationError(PluginSDKError):
    pass


class PluginExecutionError(PluginSDKError):
    pass
