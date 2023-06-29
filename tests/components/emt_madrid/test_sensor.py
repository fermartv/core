"""The tests for the EMT Madrid sensor platform."""
from unittest.mock import patch

import pytest
import requests
import requests_mock

from homeassistant.components.emt_madrid.sensor import APIEMT


class TestAPIEMT:
    """Test for APIEMT class."""

    @pytest.fixture
    def api_emt(self):
        """Fixture for creating an APIEMT instance."""
        return APIEMT("user", "password")

    def test_authenticate_valid_credentials(
        self, requests_mock: requests_mock.Mocker, api_emt
    ) -> None:
        """Test authentication with valid credentials."""
        requests_mock.get(
            "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/",
            json={
                "code": "01",
                "description": "Token 3bd5855a-ed3d-41d5-8b4b-182726f86031 extend into control-cache Data recovered OK",
                "datetime": "2023-06-29T19:50:08.307475",
                "data": [
                    {
                        "accessToken": "3bd5855a-ed3d-41d5-8b4b-182726f86031",
                    }
                ],
            },
        )

        token = api_emt.authenticate()

        assert token == "3bd5855a-ed3d-41d5-8b4b-182726f86031"

    def test_authenticate_invalid_password(
        self, requests_mock: requests_mock.Mocker, api_emt
    ) -> None:
        """Test authentication with invalid password."""
        requests_mock.get(
            "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/",
            json={
                "code": "89",
                "description": "Error: Invalid user or Password (lapsed: 415 millsecs)",
                "datetime": "2023-06-29T20:02:41.901955",
                "data": [],
            },
            status_code=200,
        )

        with pytest.raises(ConnectionError):
            api_emt.authenticate()

    def test_authenticate_invalid_user(
        self, requests_mock: requests_mock.Mocker, api_emt
    ) -> None:
        """Test authentication with invalid user."""
        requests_mock.get(
            "https://openapi.emtmadrid.es/v1/mobilitylabs/user/login/",
            json={
                "code": "92",
                "description": "Error: User not found (lapsed: 776 millsecs)",
                "datetime": "2023-06-29T20:01:09.441986",
                "data": [],
            },
            status_code=200,
        )

        with pytest.raises(ConnectionError):
            api_emt.authenticate()

    @patch.object(requests, "post")
    def test_update_arrival_times(self, mock_post, api_emt) -> None:
        """Test updating arrival times for a stop and line."""
        response_data = {
            "code": "00",
            "description": "Data recovered OK (lapsed: 1155 millsecs)",
            "datetime": "2023-06-29T18:50:13.968932",
            "data": [
                {
                    "Arrive": [
                        {
                            "line": "27",
                            "stop": "72",
                            "isHead": "False",
                            "destination": "PLAZA CASTILLA",
                            "deviation": 0,
                            "bus": 528,
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-3.69295437941713, 40.41338567959594],
                            },
                            "estimateArrive": 233,
                            "DistanceBus": 674,
                            "positionTypeBus": "0",
                        },
                        {
                            "line": "27",
                            "stop": "72",
                            "isHead": "False",
                            "destination": "PLAZA CASTILLA",
                            "deviation": 0,
                            "bus": 515,
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-3.6950488592789865, 40.40415447211869],
                            },
                            "estimateArrive": 556,
                            "DistanceBus": 1777,
                            "positionTypeBus": "0",
                        },
                    ],
                    "StopInfo": [],
                    "ExtraInfo": [],
                    "Incident": {},
                }
            ],
        }

        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: response_data
        mock_post.return_value = mock_response

        api_emt.update_arrival_times(72, "27")

        expected_arrival_time = {"27": {"arrival": 3, "next_arrival": 9}}

        assert api_emt._arrival_time == expected_arrival_time

    @patch.object(requests, "post")
    def test_update_arrival_times_no_next_bus(self, mock_post, api_emt) -> None:
        """Test updating arrival times when there is no next bus."""
        response_data = {
            "code": "00",
            "description": "Data recovered OK (lapsed: 1155 millsecs)",
            "datetime": "2023-06-29T18:50:13.968932",
            "data": [
                {
                    "Arrive": [
                        {
                            "line": "27",
                            "stop": "72",
                            "isHead": "False",
                            "destination": "PLAZA CASTILLA",
                            "deviation": 0,
                            "bus": 528,
                            "geometry": {
                                "type": "Point",
                                "coordinates": [-3.69295437941713, 40.41338567959594],
                            },
                            "estimateArrive": 233,
                            "DistanceBus": 674,
                            "positionTypeBus": "0",
                        },
                    ],
                    "StopInfo": [],
                    "ExtraInfo": [],
                    "Incident": {},
                }
            ],
        }

        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: response_data
        mock_post.return_value = mock_response

        api_emt.update_arrival_times(72, "27")

        expected_arrival_time = {"27": {"arrival": 3, "next_arrival": "-"}}

        assert api_emt._arrival_time == expected_arrival_time

    @patch.object(requests, "post")
    def test_update_arrival_times_stop_not_exists(self, mock_post, api_emt) -> None:
        """Test updating arrival times when the stop does not exist."""
        response_data = {
            "code": "80",
            "description": [
                {"ES": "Parada no disponible actualmente o inexistente"},
                {"EN": "Bus Stop disabled or not exists"},
            ],
            "datetime": "2023-06-29T21:34:48.886037",
            "data": [{"Arrive": [], "StopInfo": [], "ExtraInfo": [], "Incident": {}}],
        }

        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: response_data
        mock_post.return_value = mock_response

        api_emt.update_arrival_times(72, "27")

        expected_arrival_time = {"27": {"arrival": "-", "next_arrival": "-"}}

        assert api_emt._arrival_time == expected_arrival_time

    @patch.object(requests, "post")
    def test_update_arrival_times_line_not_found(self, mock_post, api_emt):
        """Test updating arrival times when the line is not found."""
        response_data = {
            "code": "01",
            "description": "No estimations found (lapsed: 123 millsecs)",
            "datetime": "2023-06-29T21:31:44.799862",
            "data": [{"Arrive": [], "StopInfo": [], "ExtraInfo": [], "Incident": {}}],
        }

        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response.json = lambda: response_data
        mock_post.return_value = mock_response

        api_emt.update_arrival_times(72, "27")

        expected_arrival_time = {"27": {"arrival": "-", "next_arrival": "-"}}

        assert api_emt._arrival_time == expected_arrival_time
