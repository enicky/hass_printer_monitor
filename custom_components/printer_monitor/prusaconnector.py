""""bleh"""
from aiohttp import ClientSession, ClientResponse
from typing import TypedDict

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging

_logger = logging.getLogger(__name__)


class PrusaLinkError(Exception):
    """Base class for PrusaLink errors."""


class InvalidAuth(PrusaLinkError):
    """Error to indicate there is invalid auth."""


class Conflict(PrusaLinkError):
    """Error to indicate the command hit a conflict."""


class VersionInfo(TypedDict):
    """Version information"""

    api: str
    server: str
    txt: str
    hostname: str


class JobInfo(TypedDict):
    """Job data."""

    state: str
    job: dict | None
    progress: dict | None


class PrinterInfo(TypedDict):
    """Printer data."""

    telemetry: dict
    temperature: dict
    state: dict


class PrusaConnection:
    """ "Prusa Connection"""

    def __init__(self, session: ClientSession, host: str, api_key: str) -> None:
        """Initialize PrusaConnection class"""
        _logger.info("[ctor] of PrusaConnection")
        self._host = host
        self._api_key = api_key
        self._session = session

    def get_tostring(self) -> str:
        """getting tostring value"""
        return f"host: {self._host}, api {self._api_key}"

    async def get_version(self) -> VersionInfo:
        """ "get version call to printer"""

        async with self.request("GET", "api/version") as response:
            return await response.json()

    async def get_printer(self) -> PrinterInfo:
        """Getting Printer information"""
        _logger.debug("getting printer ... return default for now")
        async with self.request("GET", "api/printer") as response:
            return await response.json()

    async def get_job(self) -> JobInfo:
        """Return default jobinfo for now"""
        async with self.request("GET", "api/job") as response:
            return await response.json()

    @asynccontextmanager
    async def request(
        self, method: str, path: str, json: dict | None = None
    ) -> AsyncGenerator[ClientResponse, None]:
        """Make a request to the PrusaLink API."""
        url = f"{self._host}/{path}"
        headers = {"X-Api-Key": self._api_key}

        async with self._session.request(
            method, url, headers=headers, json=json
        ) as response:
            if response.status == 401:
                raise InvalidAuth()
            if response.status == 409:
                raise Conflict()

            response.raise_for_status()
            yield response
