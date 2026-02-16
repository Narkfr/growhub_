import sys
from unittest.mock import MagicMock

import pytest  # type: ignore

mock_machine = MagicMock()
sys.modules["machine"] = mock_machine
from firmware.src.sensors.soil_sensor import SoilSensor  # noqa: E402

# Setup the mock behavior for ADC
# We want read_u16 to return a specific value when we decide
mock_adc_instance = mock_machine.ADC.return_value
dry = 50000
wet = 20000


@pytest.fixture()
def sensor():
    mock_machine.reset_mock()
    return SoilSensor(
        pin_number=26, calibration={"dry": dry, "wet": wet}, sensor_id="SoilSensor"
    )


class TestSoilSensor:
    def test_init_create_sensor(self, sensor):
        mock_machine.Pin.assert_called_with(26)
        assert sensor.dry_value == dry
        assert sensor.wet_value == wet

    @pytest.mark.parametrize(
        "expected_16bit",
        [(wet), (dry)],
    )
    def test_adc_bit_scaling(self, expected_16bit, sensor):
        mock_adc_instance.read_u16.return_value = expected_16bit
        result = sensor.read_raw()
        assert result == expected_16bit
        assert result <= 65535
        assert result >= 0

    def test_read_wet(self, sensor):
        # Test Case: Wet value (100%)
        mock_adc_instance.read_u16.return_value = wet
        assert sensor.read() == {"moisture": {"unit": "percent", "value": 100.0}}

    def test_read_mid_point(self, sensor):
        # Test Case: Midpoint value (50%)
        midpoint = (dry + wet) // 2
        mock_adc_instance.read_u16.return_value = midpoint
        assert sensor.read() == {"moisture": {"unit": "percent", "value": 50.0}}

    def test_read_dry(self, sensor):
        # Test Case: Dry value (0%)
        mock_adc_instance.read_u16.return_value = dry
        assert sensor.read() == {"moisture": {"unit": "percent", "value": 0.0}}

    def test_read_clamped_above_max(self, sensor):
        # Test Case: Value above dry (clamped to 0%)
        mock_adc_instance.read_u16.return_value = dry + 1
        with pytest.raises(
            ValueError, match=rf"Raw value {dry + 1} is outside calibration range"
        ):
            sensor.read()

    def test_read_clamped_below_min(self, sensor):
        # Test Case: Value below wet (clamped to 100%)
        mock_adc_instance.read_u16.return_value = wet - 1
        with pytest.raises(
            ValueError, match=rf"Raw value {wet - 1} is outside calibration range"
        ):
            sensor.read()

    def test_get_percentage_invalid_type_string(self, sensor):
        # Test Case: Non-numeric type (string)
        with pytest.raises(
            TypeError, match="raw_value must be numeric, got <class 'str'>"
        ):
            sensor.get_percentage_from_raw("invalid")

    def test_get_percentage_invalid_type_list(self, sensor):
        # Test Case: Non-numeric type (list)
        with pytest.raises(
            TypeError, match="raw_value must be numeric, got <class 'list'>"
        ):
            sensor.get_percentage_from_raw([100])

    def test_get_percentage_invalid_type_none(self, sensor):
        # Test Case: Non-numeric type (None)
        with pytest.raises(
            TypeError, match="raw_value must be numeric, got <class 'NoneType'>"
        ):
            sensor.get_percentage_from_raw(None)

    def test_equal_calibrations(self, sensor):
        # Test Case: Dry and wet values are equal
        bad_sensor = SoilSensor(
            pin_number=26, calibration={"dry": dry, "wet": dry}, sensor_id="SoilSensor"
        )
        with pytest.raises(
            ValueError,
            match="Calibration error: dry and wet cannot be equal",
        ):
            bad_sensor.get_percentage_from_raw(35000)
