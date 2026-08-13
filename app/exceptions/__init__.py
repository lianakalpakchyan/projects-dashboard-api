class AppError(Exception):
    """Base class for domain errors, translated to HTTP in the router layer."""


class UserAlreadyExistsError(AppError):
    pass


class InvalidCredentialsError(AppError):
    pass


class NotFoundError(AppError):
    pass


class PermissionDeniedError(AppError):
    pass
