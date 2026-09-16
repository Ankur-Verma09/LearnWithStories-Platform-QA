class ReleaseError(RuntimeError):
    pass


class ConfigurationError(ReleaseError):
    pass


class CloudflareApiError(ReleaseError):
    def __init__(self, status: int, message: str):
        self.status = status
        super().__init__(message)


class UploadError(ReleaseError):
    pass


class HealthCheckError(ReleaseError):
    def __init__(self, message: str, status: int | None = None):
        self.status = status
        super().__init__(message)


class HealthCheckTimeout(HealthCheckError):
    pass


class RollbackError(ReleaseError):
    pass


class ConcurrentDeploymentError(ReleaseError):
    pass


def classify_error(error: Exception) -> str:
    if isinstance(error, CloudflareApiError):
        return "client_error" if 400 <= error.status < 500 else "server_error"
    if isinstance(error, HealthCheckError) and error.status is not None:
        return "client_error" if 400 <= error.status < 500 else "server_error"
    if isinstance(error, (ConfigurationError, ConcurrentDeploymentError, UploadError)):
        return "client_error"
    return "server_error"

