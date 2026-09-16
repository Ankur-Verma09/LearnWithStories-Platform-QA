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
    pass


class HealthCheckTimeout(HealthCheckError):
    pass


class RollbackError(ReleaseError):
    pass

