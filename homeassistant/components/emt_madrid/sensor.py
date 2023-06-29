"""Support for EMT Madrid to get next departures."""
from collections.abc import Mapping
import json
import logging
import math
from typing import Any

import requests
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

ATTRIBUTION = "Data provided by EMT Madrid MobilityLabs"

CONF_STOP = "stop"
CONF_LINE = "line"

DEFAULT_NAME = "Next bus"
DEFAULT_ICON = "mdi:bus"

ATTR_NEXT_UP = "later_bus"
ATTR_BUS_STOP = "bus_stop_id"
ATTR_BUS_LINE = "bus_line"

BASE_URL = "https://openapi.emtmadrid.es/"
ENDPOINT_LOGIN = "v1/mobilitylabs/user/login/"
ENDPOINT_ARRIVAL_TIME = "v2/transport/busemtmad/stops/"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_STOP): cv.positive_int,
        vol.Required(CONF_LINE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


class APIEMT:
    """Support for EMT Madrid to get next departures."""

    def __init__(self, user, password) -> None:
        """Initialize an instance of the APIEMT class."""
        self._user = user
        self._password = password
        self._token = None
        self._arrival_time: dict[str, dict[str, int]] = {}

    def authenticate(self):
        """Authenticate the user using the provided credentials."""
        headers = {"email": self._user, "password": self._password}
        url = f"{BASE_URL}{ENDPOINT_LOGIN}"
        response = self._make_request(url, headers=headers, method="GET")
        self._token = self._extract_token(response)
        return self._token

    def update_arrival_times(self, stop, line):
        """Update the arrival times for the specified bus stop and line."""
        url = f"{BASE_URL}{ENDPOINT_ARRIVAL_TIME}{stop}/arrives/{line}/"
        headers = {"accessToken": self._token}
        data = {"stopId": stop, "lineArrive": line, "Text_EstimationsRequired_YN": "Y"}
        response = self._make_request(url, headers=headers, data=data, method="POST")
        self._parse_arrival_times(response, line)

    def get_arrival_time(self, line, bus):
        """Retrieve the arrival time for the specified bus line and bus number."""
        if line in self._arrival_time and bus in self._arrival_time[line]:
            return self._arrival_time[line][bus]
        return None

    def _make_request(self, url, headers=None, data=None, method="POST"):
        """Send an HTTP request to the specified URL."""
        try:
            if method == "POST":
                response = requests.post(
                    url, headers=headers, data=json.dumps(data), timeout=10
                )
            elif method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Invalid HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except (requests.exceptions.RequestException, ValueError) as e:
            raise (f"Request error: {e}")

    def _extract_token(self, response):
        """Extract the access token from the API response."""
        try:
            return response["data"][0]["accessToken"]
        except (KeyError, IndexError) as e:
            raise ConnectionError("Unable to get the token from the API") from e

    def _parse_arrival_times(self, response, target_line):
        """Parse the arrival times from the API response."""
        arrival_data = {}
        try:
            if response["code"] == "80":
                _LOGGER.warning("Bus Stop disabled or does not exist")
            else:
                for bus in response["data"][0]["Arrive"]:
                    estimated_time = math.trunc(bus["estimateArrive"] / 60)
                    estimated_time = min(estimated_time, 30)
                    line = bus["line"]
                    if line not in arrival_data:
                        arrival_data[line] = {"arrival": estimated_time}
                    elif "next_arrival" not in arrival_data[line]:
                        arrival_data[line]["next_arrival"] = estimated_time
        except (KeyError, IndexError) as e:
            raise ValueError("Unable to get the arrival times from the API") from e

        if target_line not in arrival_data:
            arrival_data[target_line] = {"arrival": "-"}
        if "next_arrival" not in arrival_data[target_line]:
            arrival_data[target_line]["next_arrival"] = "-"

        self._arrival_time = arrival_data


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    email = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)
    bus_stop = config.get(CONF_STOP)
    line = config.get(CONF_LINE)
    name = config.get(CONF_NAME)
    icon = config.get(CONF_ICON)
    api_emt = APIEMT(email, password)
    api_emt.authenticate()
    api_emt.update_arrival_times(bus_stop, line)
    add_entities([BusStopSensor(api_emt, bus_stop, line, name, icon)])


class BusStopSensor(Entity):
    """Implementation of an EMT-Madrid bus stop sensor."""

    def __init__(self, api_emt: APIEMT, bus_stop, line, name, icon) -> None:
        """Initialize the sensor."""
        self._state = None
        self._api_emt = api_emt
        self._bus_stop = bus_stop
        self._bus_line = line
        self._icon = icon
        self._name = name
        if self._name == DEFAULT_NAME:
            self._name = f"Next {self._bus_line} at {self._bus_stop}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._api_emt.get_arrival_time(self._bus_line, "arrival")

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return UnitOfTime.MINUTES

    @property
    def icon(self) -> str:
        """Return sensor specific icon."""
        return self._icon

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the device state attributes."""
        return {
            ATTR_NEXT_UP: self._api_emt.get_arrival_time(
                self._bus_line, "next_arrival"
            ),
            ATTR_BUS_STOP: self._bus_stop,
            ATTR_BUS_LINE: self._bus_line,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }

    def update(self) -> None:
        """Fetch new state data for the sensor."""
        self._api_emt.update_arrival_times(self._bus_stop, self._bus_line)
