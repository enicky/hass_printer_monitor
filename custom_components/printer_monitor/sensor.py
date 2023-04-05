"""Sensor platform for printer_monitor integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID, UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import StateType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from . import (
    DOMAIN,
    PrusaPrinterUpdateCoordinator,
    PrusaLinkEntity,
)  # , PrusaLinkEntity, PrusaLinkUpdateCoordinator

from .prusaconnector import JobInfo, PrinterInfo

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generic, TypeVar, cast

T = TypeVar("T", PrinterInfo, JobInfo)


@dataclass
class PrusaLinkSensorEntityDescriptionMixin(Generic[T]):
    """Mixin for required keys."""

    value_fn: Callable[[T], datetime | StateType]


@dataclass
class PrusaLinkSensorEntityDescription(
    SensorEntityDescription, PrusaLinkSensorEntityDescriptionMixin[T], Generic[T]
):
    """Describes PrusaLink sensor entity."""

    available_fn: Callable[[T], bool] = lambda _: True


SENSORS: dict[str, tuple[PrusaLinkSensorEntityDescription, ...]] = {
    "printer": (
        PrusaLinkSensorEntityDescription[PrinterInfo](
            key="printer.state",
            icon="mdi:printer-3d",
            value_fn=lambda data: (
                "pausing"
                if (flags := data["state"]["flags"])["pausing"]
                else "cancelling"
                if flags["cancelling"]
                else "paused"
                if flags["paused"]
                else "printing"
                if flags["printing"]
                else "idle"
            ),
            device_class=SensorDeviceClass.ENUM,
            options=["cancelling", "idle", "paused", "pausing", "printing"],
            translation_key="printer_state",
        ),
        PrusaLinkSensorEntityDescription[PrinterInfo](
            key="printer.telemetry.temp-bed",
            name="Heatbed",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["telemetry"]["temp-bed"]),
            # value_fn=lambda data: cast(float, 0),
            entity_registry_enabled_default=False,
        ),
        PrusaLinkSensorEntityDescription[PrinterInfo](
            key="printer.telemetry.temp-nozzle",
            name="Nozzle Temperature",
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data: cast(float, data["telemetry"]["temp-nozzle"]),
            # value_fn=lambda data: cast(float, 0),
            entity_registry_enabled_default=False,
        ),
    ),
    "job": (
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.progress",
            name="Progress",
            icon="mdi:progress-clock",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(float, data["progress"]["completion"]) * 100,
            available_fn=lambda data: data.get("progress") is not None,
        ),
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.filename",
            name="Filename",
            icon="mdi:file-image-outline",
            value_fn=lambda data: cast(str, data["job"]["file"]["display"]),
            available_fn=lambda data: data.get("job") is not None,
        ),
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.start",
            name="Print Start",
            device_class=SensorDeviceClass.TIMESTAMP,
            icon="mdi:clock-start",
            value_fn=ignore_variance(
                lambda data: (
                    utcnow() - timedelta(seconds=data["progress"]["printTime"])
                ),
                timedelta(minutes=2),
            ),
            available_fn=lambda data: data.get("progress") is not None,
        ),
        PrusaLinkSensorEntityDescription[JobInfo](
            key="job.finish",
            name="Print Finish",
            icon="mdi:clock-end",
            device_class=SensorDeviceClass.TIMESTAMP,
            value_fn=ignore_variance(
                lambda data: (
                    utcnow() + timedelta(seconds=data["progress"]["printTimeLeft"])
                ),
                timedelta(minutes=2),
            ),
            available_fn=lambda data: data.get("progress") is not None,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize printer_monitor config entry."""
    coordinators: dict[str, PrusaPrinterUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    entities: list[PrusaLinkEntity] = []

    for coordinator_type, sensors in SENSORS.items():
        coordinator = coordinators[coordinator_type]
        entities.extend(
            PrusaLinkSensorEntity(coordinator, sensor_description)
            for sensor_description in sensors
        )

    async_add_entities(entities)

    # registry = er.async_get(hass)
    # # Validate + resolve entity registry id to entity_id
    # entity_id = er.async_validate_entity_id(
    #     registry, config_entry.options[CONF_ENTITY_ID]
    # )
    # # TODO Optionally validate config entry options before creating entity
    # name = config_entry.title
    # unique_id = config_entry.entry_id

    # async_add_entities([printer_monitorSensorEntity(unique_id, name, entity_id)])


# class printer_monitorSensorEntity(SensorEntity):
#     """printer_monitor Sensor."""

#     def __init__(self, unique_id: str, name: str, wrapped_entity_id: str) -> None:
#         """Initialize printer_monitor Sensor."""
#         super().__init__()
#         self._wrapped_entity_id = wrapped_entity_id
#         self._attr_name = name
#         self._attr_unique_id = unique_id


class PrusaLinkSensorEntity(PrusaLinkEntity, SensorEntity):
    """Defines a PrusaLink sensor."""

    entity_description: PrusaLinkSensorEntityDescription

    def __init__(
        self,
        coordinator: PrusaPrinterUpdateCoordinator,
        description: PrusaLinkSensorEntityDescription,
    ) -> None:
        """Initialize a PrusaLink sensor entity."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )
