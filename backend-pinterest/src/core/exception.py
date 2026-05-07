from fastapi import HTTPException, status


class AppError(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "Internal server error",
    ):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundError(AppError):
    def __init__(self, detail: str = "Not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictError(AppError):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Unauthorized"):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class BadRequestError(AppError):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str = "Forbidden"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ProviderError(AppError):
    def __init__(self, detail: str = "AI provider failed"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


class InvalidAIOutputError(AppError):
    def __init__(self, detail: str = "Invalid AI output"):
        super().__init__(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


class AITimeoutError(AppError):
    def __init__(self, detail: str = "AI request timeout"):
        super().__init__(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=detail)


class RateLimitError(AppError):
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
