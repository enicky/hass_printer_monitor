"""The printer_monitor integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from .prusaconnector import (
    InvalidAuth,
    PrusaLinkError,
    PrinterInfo,
    PrusaConnection,
    JobInfo,
)

# from . import InvalidAuth, PrusaLinkError
# from . import PrinterInfo, PrusaConnection, JobInfo
from datetime import timedelta
from time import monotonic
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import async_timeout

from typing import Generic, TypeVar
from abc import ABC, abstractmethod
import logging

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]
_logger = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up printer_monitor from a config entry."""
    # TODO Optionally store an object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = ...
    api = PrusaConnection(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        api_key=entry.data[CONF_API_KEY],
    )

    coordinators = {
        "printer": PrinterUpdateCoordinator(hass, api),
        "job": JobUpdateCoordinator(hass, api),
    }

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


# TODO Remove if the integration does not have an options flow
# async def config_entry_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
#     """Update listener, called when the config entry options are changed."""
#     await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


T = TypeVar("T", PrinterInfo, JobInfo)


class PrusaPrinterUpdateCoordinator(DataUpdateCoordinator, Generic[T], ABC):
    """Update coordinator for the printer."""

    config_entry: ConfigEntry
    expect_change_until = 0.0

    def __init__(self, hass: HomeAssistant, api: PrusaConnection) -> None:
        """Initialize the update coordinator."""
        sStr: str = api.get_tostring()

        _logger.info("api : %s - %s", sStr, type(api))
        self.api = api

        super().__init__(
            hass, _logger, name=DOMAIN, update_interval=self._get_update_interval(None)
        )

    def _get_update_interval(self, data: T) -> timedelta:
        """ "get update interval"""
        if self.expect_change_until > monotonic():
            return timedelta(seconds=5)

        return timedelta(seconds=30)

    async def _async_update_data(self) -> T:
        """Update the data."""
        try:
            async with async_timeout.timeout(5):
                data = await self._fetch_data()
        except InvalidAuth:
            raise UpdateFailed("Invalid authentication") from None
        except PrusaLinkError as err:
            raise UpdateFailed(str(err)) from err

        self.update_interval = self._get_update_interval(data)
        return data

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError

    @callback
    def expect_change(self) -> None:
        """Expect a change."""
        self.expect_change_until = monotonic() + 30


class PrinterUpdateCoordinator(PrusaPrinterUpdateCoordinator[PrinterInfo]):
    """PrinterUpdateCoordinator"""

    async def _fetch_data(self) -> PrinterInfo:
        """Fetch the printer data."""
        _logger.info("Starting to get printer information")
        return await self.api.get_printer()

    def _get_update_interval(self, data: T) -> timedelta:
        """Get new update interval."""
        if data and any(
            data["state"]["flags"][key] for key in ("pausing", "cancelling")
        ):
            return timedelta(seconds=5)

        return super()._get_update_interval(data)


class JobUpdateCoordinator(PrusaPrinterUpdateCoordinator[JobInfo]):
    """Job update coordinator."""

    async def _fetch_data(self) -> JobInfo:
        """Fetch the printer data."""
        _logger.info("Start retrieving job information")
        return await self.api.get_job()


class PrusaLinkEntity(CoordinatorEntity[PrinterUpdateCoordinator]):
    """Defines a base PrusaLink entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PrusaLink device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Prusa",
            configuration_url=self.coordinator.api._host,
        )
