"""Support for EMT Madrid (Empresa Municipal de Transportes de Madrid) to get next departures."""

from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_EMAIL,
    CONF_ICON,
    CONF_NAME,
    CONF_PASSWORD,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .emt_madrid import APIEMT

ATTRIBUTION = "Data provided by EMT Madrid MobilityLabs"

CONF_STOP_ID = "stop"
CONF_BUS_LINES = "lines"

DEFAULT_NAME = "EMT Madrid bus"
DEFAULT_ICON = "mdi:bus"

ATTR_NEXT_UP = "next_bus"
ATTR_STOP_ID = "stop_id"
ATTR_STOP_NAME = "stop_name"
ATTR_STOP_ADDRESS = "stop_address"
ATTR_STOP_LOCATION = "stop_location"
ATTR_LINE = "line"
ATTR_LINE_DESTINATION = "destination"
ATTR_LINE_ORIGIN = "origin"
ATTR_LINE_START_TIME = "start_time"
ATTR_LINE_END_TIME = "end_time"
ATTR_LINE_MAX_FREQ = "max_frequency"
ATTR_LINE_MIN_FREQ = "min_frequency"
ATTR_LINE_DISTANCE = "distance"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_STOP_ID): cv.positive_int,
        vol.Required(CONF_BUS_LINES): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.string,
        # vol.Optional(CONF_BUS_LINES, default=[]): vol.All(cv.ensure_list, [cv.string]),
    }
)


class BusLineSensor(Entity):
    """Implementation of an EMT-Madrid bus line sensor."""

    def __init__(self, api_emt: APIEMT, stop_id, line, name, icon) -> None:
        """Initialize the sensor."""
        self._state = None
        self._api_emt = api_emt
        self._stop_id = stop_id
        self._bus_line = line
        self._icon = icon
        self._name = name

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        arrival_time = self._api_emt.get_arrival_time(self._bus_line)
        return arrival_time[0]

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTime.MINUTES

    @property
    def icon(self) -> str:
        """Return sensor specific icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        arrival_time = self._api_emt.get_arrival_time(self._bus_line)
        stop_info = self._api_emt.get_stop_info()
        lines_info = stop_info.get("lines")
        line = lines_info.get(self._bus_line)
        distance = self._api_emt.get_distance(self._bus_line)

        return {
            ATTR_NEXT_UP: arrival_time[1],
            ATTR_LINE: self._bus_line,
            ATTR_LINE_DISTANCE: distance,
            ATTR_LINE_DESTINATION: line.get("destination"),
            ATTR_LINE_ORIGIN: line.get("origin"),
            ATTR_LINE_START_TIME: line.get("start_time"),
            ATTR_LINE_END_TIME: line.get("end_time"),
            ATTR_LINE_MAX_FREQ: line.get("max_freq"),
            ATTR_LINE_MIN_FREQ: line.get("min_freq"),
            ATTR_STOP_ID: self._stop_id,
            ATTR_STOP_NAME: stop_info.get("bus_stop_name"),
            ATTR_STOP_ADDRESS: stop_info.get("bus_stop_address"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        self._api_emt.update_arrival_times(self._stop_id)


def get_api_emt_instance(config: ConfigType) -> APIEMT:
    """Create an instance of the APIEMT class with the provided configuration."""
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    stop_id = config.get(CONF_STOP_ID)
    api_emt = APIEMT(email, password, stop_id)
    api_emt.authenticate()
    api_emt.update_stop_info(stop_id)
    return api_emt


def create_bus_line_sensor(api_emt: APIEMT, config: ConfigType) -> BusLineSensor:
    """Create a BusLineSensor instance with the provided APIEMT instance and configuration."""
    stop_id = config.get(CONF_STOP_ID)
    line = config.get(CONF_BUS_LINES)
    name = config.get(CONF_NAME, f"{stop_id} - {line}")
    icon = config.get(CONF_ICON)
    api_emt.update_arrival_times(stop_id)
    return BusLineSensor(api_emt, stop_id, line, name, icon)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    api_emt = get_api_emt_instance(config)
    bus_line_sensor = create_bus_line_sensor(api_emt, config)
    add_entities([bus_line_sensor])
