from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import KEY_PREFIX, APIKey

HEADER = "X-API-Key"


class APIKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate requests with an `X-API-Key: dq_<prefix>_<secret>` header.

    The prefix finds the key row; the full key is checked against the stored hash
    with a constant-time comparison. On success `request.auth` is the APIKey.
    """

    def authenticate(self, request):
        raw_key = request.headers.get(HEADER)
        if not raw_key:
            return None  # no credentials: DRF answers 401 via authenticate_header

        parts = raw_key.split("_", 2)
        if len(parts) != 3 or parts[0] != KEY_PREFIX:
            raise exceptions.AuthenticationFailed("Malformed API key.")

        try:
            api_key = APIKey.objects.get(prefix=parts[1])
        except APIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.") from None

        if api_key.revoked or not api_key.matches(raw_key):
            raise exceptions.AuthenticationFailed("Invalid API key.")

        APIKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        # No Django user is involved: the key itself is the principal.
        return (APIKeyUser(api_key), api_key)

    def authenticate_header(self, request):
        return HEADER


class APIKeyUser:
    """Minimal user object so DRF's IsAuthenticated works with key-only auth."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, api_key: APIKey):
        self.api_key = api_key

    def __str__(self) -> str:
        return f"api-key:{self.api_key.prefix}"
