import sys
import pytest

from unittest.mock import MagicMock

mock_machine = MagicMock()
mock_dht = MagicMock()
sys.modules["dht"] = mock_dht
sys.modules["machine"] = mock_machine
from firmware.sensors.climate_sensor import ClimateSensor


@pytest.fixture
def sensor():
    mock_dht.reset_mock()
    mock_machine.reset_mock()
    return ClimateSensor(pin_number=4)


class TestClimateSensor:
    def test_init_creates_sensor(self, sensor):
        mock_machine.Pin.assert_called_with(4)

    def test_read_data_success(self, sensor):
        mock_dht.DHT11.return_value.measure.return_value = None
        mock_dht.DHT11.return_value.temperature.return_value = 25
        mock_dht.DHT11.return_value.humidity.return_value = 60

        temp, hum = sensor.read_data()
        assert temp == 25
        assert hum == 60

    def test_read_data_invalid_temperature(self, sensor):
        mock_dht.DHT11.return_value.measure.return_value = None
        mock_dht.DHT11.return_value.temperature.return_value = "NaN"
        mock_dht.DHT11.return_value.humidity.return_value = 60

        temp, hum = sensor.read_data()
        assert temp is None
        assert hum is None

    def test_read_data_invalid_humidity(self, sensor):
        mock_dht.DHT11.return_value.measure.return_value = None
        mock_dht.DHT11.return_value.temperature.return_value = 25
        mock_dht.DHT11.return_value.humidity.return_value = 150

        temp, hum = sensor.read_data()
        assert temp is None
        assert hum is None

    def test_read_data_timeout(self, sensor):
        mock_dht.DHT11.return_value.measure.side_effect = OSError(110)

        temp, hum = sensor.read_data(retries=2)
        assert temp is None
        assert hum is None
