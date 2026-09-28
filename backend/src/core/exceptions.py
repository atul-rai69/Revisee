class ApplicationError(Exception):
    status_code = 500
    detail = "An unexpected application error occurred"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail or self.detail)
        self.detail = detail or self.detail


class AuthenticationError(ApplicationError):
    status_code = 401
    detail = "Invalid or expired authentication credentials"

    def __init__(
        self,
        detail: str | None = None,
        *,
        auth_code: str = "invalid_authentication",
        clear_refresh_cookie: bool = False,
    ) -> None:
        super().__init__(detail)
        self.auth_code = auth_code
        self.clear_refresh_cookie = clear_refresh_cookie


class CsrfError(ApplicationError):
    status_code = 403
    detail = "Request origin could not be verified"


class ResourceNotFoundError(ApplicationError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(ApplicationError):
    status_code = 400
    detail = "Resource already exists"


class DuplicateQuestionError(ApplicationError):
    status_code = 409
    detail = "An equivalent question already exists for this learning item"


class DomainValidationError(ApplicationError):
    status_code = 422
    detail = "Invalid request"


class ProviderUnavailableError(ApplicationError):
    status_code = 502
    detail = "External provider is unavailable"


class ProviderOutageError(ProviderUnavailableError):
    status_code = 503


class ProviderOutputError(ApplicationError):
    status_code = 502
    detail = "External provider returned invalid data"


class CredentialConfigurationError(ApplicationError):
    status_code = 503
    detail = "Personal AI credentials are not configured on this server"


class InvalidProviderCredentialError(ApplicationError):
    status_code = 422
    detail = "The Gemini credential is invalid or has been revoked"


class ProviderQuotaError(ApplicationError):
    status_code = 429
    detail = "The Gemini project quota is exhausted or temporarily rate limited"


class ProviderBusyError(ApplicationError):
    status_code = 429
    detail = "Too many generation requests are currently running"
