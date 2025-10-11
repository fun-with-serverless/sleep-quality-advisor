import base64
import contextlib
from typing import Any, cast

import requests  # type: ignore[import-untyped]

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities import parameters

from . import config  # noqa: F401  # ensure env vars loaded early

logger = Logger()


class FitbitClient:
    """Encapsulates Fitbit Web API calls used by the service.

    This client reads client id and secret via AWS Parameters/Secrets names provided
    at construction time. It logs Fitbit response headers for observability.
    """

    TOKEN_URL = "https://api.fitbit.com/oauth2/token"
    BASE_URL = "https://api.fitbit.com"

    def __init__(self, client_id_param_name: str, client_secret_name: str) -> None:
        self.client_id_param_name = client_id_param_name
        self.client_secret_name = client_secret_name

    def _get_client_credentials(self) -> tuple[str, str]:
        client_id = parameters.get_parameter(self.client_id_param_name)
        client_secret = parameters.get_secret(self.client_secret_name)
        return client_id, client_secret

    @staticmethod
    def _basic_auth_header(client_id: str, client_secret: str) -> str:
        token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        return f"Basic {token}"

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        """Exchange refresh_token for access_token (and possibly a new refresh_token).

        Returns (access_token, new_refresh_token).
        """
        client_id, client_secret = self._get_client_credentials()
        headers = {
            "Authorization": self._basic_auth_header(client_id, client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        resp = requests.post(self.TOKEN_URL, headers=headers, data=data, timeout=10)
        # Log response headers for rate limits and diagnostics
        logger.info("fitbit_token_headers", headers=dict(resp.headers))
        if resp.status_code >= 400:
            raise RuntimeError(f"Fitbit token refresh failed: {resp.status_code}")
        payload: dict[str, Any] = resp.json()
        access_token = str(payload.get("access_token", ""))
        new_refresh = str(payload.get("refresh_token", refresh_token))
        if not access_token:
            raise RuntimeError("Fitbit token refresh missing access_token")
        return access_token, new_refresh

    def get_sleep_by_date(self, date_str: str, access_token: str) -> dict[str, Any]:
        url = f"{self.BASE_URL}/1.2/user/-/sleep/date/{date_str}.json"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=15)
        # Log response headers for rate limits and diagnostics
        logger.info("fitbit_sleep_headers", headers=dict(resp.headers))
        if resp.status_code >= 400:
            raise RuntimeError(f"Fitbit sleep fetch failed: {resp.status_code}")
        payload: dict[str, Any] = cast(dict[str, Any], resp.json())
        return payload
