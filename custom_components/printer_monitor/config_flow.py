"""Config flow for printer_monitor integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import logging
from aiohttp import ClientError
import async_timeout
import voluptuous as vol

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .prusaconnector import PrusaConnection
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.data_entry_flow import FlowResult
import asyncio
from time import sleep

# from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST, CONF_API_KEY, CONF_NAME

# from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    #    SchemaFlowFormStep,
    #    SchemaFlowMenuStep,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
        #        vol.Required(CONF_ENTITY_ID): str,
    }
)

# CONFIG_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
#     "user": SchemaFlowFormStep(CONFIG_SCHEMA)
# }

# OPTIONS_FLOW: dict[str, SchemaFlowFormStep | SchemaFlowMenuStep] = {
#     "init": SchemaFlowFormStep(OPTIONS_SCHEMA)
# }


async def validate_input(hass: HomeAssistant, data: dict[str, str]) -> dict[str, str]:
    """Validate user input"""

    if data[CONF_HOST] == "" or data[CONF_API_KEY] == "":
        raise CannotConnect

    api = PrusaConnection(
        async_get_clientsession(hass), data[CONF_HOST], data[CONF_API_KEY]
    )
    try:
        async with async_timeout.timeout(5):
            version = await api.get_version()

    except (asyncio.TimeoutError, ClientError) as err:
        _LOGGER.error("Could not connect to PrusaLink: %s", err)
        raise CannotConnect from err

    return {"title": version["hostname"]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config or options flow for printer_monitor."""

    VERSION = 1

    # def async_config_entry_title(self, options: Mapping[str, Any]) -> str:
    #    """Return config entry title."""
    # x    return cast(str, options["name"]) if "name" in options else ""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        host = user_input[CONF_HOST].rstrip("/")
        if not host.startswith(("http://", "https://")):
            host = f"http://{host}"

        data = {
            "host": host,
            "api_key": user_input[CONF_API_KEY],
            "name": user_input[CONF_NAME],
        }
        errors = {}

        try:
            info = await validate_input(self.hass, data)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except NotSupported:
            errors["base"] = "not_supported"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=data)

        return await self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error we cannot connect"""


class NotSupported(HomeAssistantError):
    """Error not supported"""
