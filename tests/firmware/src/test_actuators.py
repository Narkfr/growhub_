import json
import sys
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

sys.modules["machine"] = MagicMock()
from firmware.src.actuators import Actuator, ManualButton, load_config  # noqa: E402


class TestActuator:
    @pytest.fixture
    def mock_pin(self):
        return Mock()

    @pytest.fixture
    def actuator(self, mock_pin):
        with patch("firmware.src.actuators.Pin", return_value=mock_pin):
            return Actuator(pin_number=5, actuator_id="pump_1")

    def test_actuator_initialization(self, actuator, mock_pin):
        assert actuator.id == "pump_1"
        assert actuator.pin == mock_pin
        mock_pin.value.assert_called_with(0)

    def test_actuator_on(self, actuator, mock_pin):
        actuator.on()
        mock_pin.value.assert_called_with(1)

    def test_actuator_off(self, actuator, mock_pin):
        actuator.off()
        mock_pin.value.assert_called_with(0)

    def test_actuator_toggle_from_off(self, actuator, mock_pin):
        mock_pin.value.return_value = 0
        actuator.toggle()
        mock_pin.value.assert_called_with(True)

    def test_actuator_toggle_from_on(self, actuator, mock_pin):
        mock_pin.value.return_value = 1
        actuator.toggle()
        mock_pin.value.assert_called_with(False)

    def test_actuator_is_on(self, actuator, mock_pin):
        mock_pin.value.return_value = 1
        assert actuator.is_on() is True

        mock_pin.value.return_value = 0
        assert actuator.is_on() is False


class TestManualButton:
    @pytest.fixture
    def mock_pin(self):
        return Mock()

    @pytest.fixture
    def button(self, mock_pin):
        with patch("firmware.src.actuators.Pin", return_value=mock_pin):
            return ManualButton(pin_number=12, button_id="btn_1", target_id="pump_1")

    def test_button_initialization(self, button, mock_pin):
        assert button.id == "btn_1"
        assert button.target_id == "pump_1"
        assert button.pin == mock_pin

    def test_button_is_pressed_true(self, button, mock_pin):
        mock_pin.value.return_value = 0
        assert button.is_pressed() is True

    def test_button_is_pressed_false(self, button, mock_pin):
        mock_pin.value.return_value = 1
        assert button.is_pressed() is False


class TestLoadConfig:
    def test_load_config_valid_json(self):
        config_data = {"actuators": [{"id": "pump_1", "pin": 5}]}
        with patch("builtins.open", mock_open(read_data=json.dumps(config_data))):
            result = load_config("config.json")
            assert result == config_data

    def test_load_config_file_not_found(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                load_config("nonexistent.json")

    def test_load_config_invalid_json(self):
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with pytest.raises(json.JSONDecodeError):
                load_config("config.json")
