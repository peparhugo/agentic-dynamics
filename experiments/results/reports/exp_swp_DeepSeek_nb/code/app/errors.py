class APIError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message, status_code=None, code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        self.details = details

    def to_dict(self):
        payload = {"error": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


class ValidationError(APIError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(APIError):
    status_code = 401
    code = "authentication_error"


class AuthorizationError(APIError):
    status_code = 403
    code = "authorization_error"


class NotFoundError(APIError):
    status_code = 404
    code = "not_found"


class ConflictError(APIError):
    status_code = 409
    code = "conflict"


class RateLimitError(APIError):
    status_code = 429
    code = "rate_limit_exceeded"
