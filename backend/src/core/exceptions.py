class ApplicationError(Exception):
    status_code = 500
    detail = "An unexpected application error occurred"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail


class AuthenticationError(ApplicationError):
    status_code = 401
    detail = "Invalid or expired authentication credentials"


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(ApplicationError):
    status_code = 400
    detail = "Resource already exists"


class DomainValidationError(ApplicationError):
    status_code = 422
    detail = "Invalid request"


class ProviderUnavailableError(ApplicationError):
    status_code = 502
    detail = "External provider is unavailable"


class ProviderOutputError(ApplicationError):
    status_code = 502
    detail = "External provider returned invalid data"
