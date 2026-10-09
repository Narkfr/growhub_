"""Contenu de l'écran : les champs, leur formatage et leur pagination.

Le `ScreenLayout` est chargé par chemin (comme dans `conftest.py`) pour ne pas
importer le paquet `src.display`, qui tirerait `lib.ssd1306` et `machine`.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_FIRMWARE = Path(__file__).resolve().parents[3] / "firmware"
if str(_FIRMWARE) not in sys.path:
    sys.path.insert(0, str(_FIRMWARE))

_spec = importlib.util.spec_from_file_location(
    "growhub_screen", _FIRMWARE / "src" / "display" / "screen.py"
)
assert _spec is not None and _spec.loader is not None
screen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(screen)

ScreenField = screen.ScreenField
ScreenLayout = screen.ScreenLayout

SNAPSHOT = {
    "sensors": {
        "ClimateSensor": {
            "temperature": {"value": 21.53, "unit": "celsius"},
            "humidity": {"value": 55.0, "unit": "percent"},
        },
        "SoilSensor": {"moisture": {"value": 42.4, "unit": "percent"}},
    },
    "actuators": {"WaterPump": "ON", "GrowLamp": "OFF"},
}


def layout(**display):
    return ScreenLayout.from_manifest(display)


# --- champs ------------------------------------------------------------------


def test_default_fields_are_temperature_and_humidity():
    """Sans `fields` dans le manifeste, on garde le comportement historique."""
    assert layout().lines(SNAPSHOT) == ["Temp: 21.5 °C", "Hum: 55 %"]


def test_default_fields_pick_the_first_sensor_that_publishes_the_metric():
    snapshot = {
        "sensors": {
            "SoilSensor": {"moisture": {"value": 42.4, "unit": "percent"}},
            "ClimateSensor": {"temperature": {"value": 19.0, "unit": "celsius"}},
        }
    }
    assert layout().lines(snapshot) == ["Temp: 19.0 °C", "Hum: --"]


def test_a_silent_sensor_only_costs_its_own_line():
    assert layout().lines({"sensors": {}, "actuators": {}}) == ["Temp: --", "Hum: --"]


def test_explicit_fields_are_rendered_in_order():
    screen_layout = layout(
        fields=[
            {
                "source": "SoilSensor",
                "metric": "moisture",
                "label": "Sol",
                "decimals": 0,
            },
            {
                "source": "ClimateSensor",
                "metric": "temperature",
                "label": "Air",
                "decimals": 2,
            },
        ]
    )
    assert screen_layout.lines(SNAPSHOT) == ["Sol: 42 %", "Air: 21.53 °C"]


def test_label_defaults_to_the_metric_name():
    screen_layout = layout(fields=[{"source": "ClimateSensor", "metric": "humidity"}])
    assert screen_layout.lines(SNAPSHOT) == ["humidity: 55.0 %"]


def test_an_explicit_unit_wins_over_the_published_one():
    screen_layout = layout(
        fields=[
            {
                "source": "ClimateSensor",
                "metric": "temperature",
                "label": "Air",
                "unit": "degrés",
            }
        ]
    )
    assert screen_layout.lines(SNAPSHOT) == ["Air: 21.5 degrés"]


def test_an_unknown_unit_is_shown_as_published():
    snapshot = {"sensors": {"LuxSensor": {"lux": {"value": 2.5, "unit": "lux"}}}}
    screen_layout = layout(
        fields=[{"source": "LuxSensor", "metric": "lux", "label": "Lux"}]
    )
    assert screen_layout.lines(snapshot) == ["Lux: 2.5 lux"]


def test_a_bare_number_metric_is_accepted():
    snapshot = {"sensors": {"SoilSensor": {"moisture": 40}}}
    screen_layout = layout(
        fields=[
            {
                "source": "SoilSensor",
                "metric": "moisture",
                "label": "Sol",
                "decimals": 0,
            }
        ]
    )
    assert screen_layout.lines(snapshot) == ["Sol: 40"]


def test_actuator_fields_are_written_in_plain_french():
    screen_layout = layout(
        fields=[
            {"kind": "actuator", "source": "WaterPump", "label": "Pompe"},
            {"kind": "actuator", "source": "GrowLamp", "label": "Lampe"},
        ]
    )
    assert screen_layout.lines(SNAPSHOT) == ["Pompe: Allumé", "Lampe: Éteint"]


def test_an_unknown_actuator_shows_a_dash():
    screen_layout = layout(
        fields=[{"kind": "actuator", "source": "Absent", "label": "Rien"}]
    )
    assert screen_layout.lines(SNAPSHOT) == ["Rien: --"]


def test_a_field_without_source_is_rejected_at_parse_time():
    try:
        ScreenField.from_dict({"metric": "temperature"})
    except ValueError as error:
        assert "source" in str(error)
    else:
        raise AssertionError("un champ sans source doit être refusé")


def test_a_malformed_field_is_ignored_without_losing_the_screen(capsys):
    screen_layout = layout(
        fields=[
            {"metric": "temperature"},
            {"source": "ClimateSensor", "metric": "temperature", "label": "Temp"},
        ]
    )
    assert screen_layout.lines(SNAPSHOT) == ["Temp: 21.5 °C"]
    assert "Champ d'écran ignoré" in capsys.readouterr().out


def test_number_formatting_keeps_the_requested_decimals():
    assert screen._format_number(21.5, 1) == "21.5"
    assert screen._format_number(21.5, 0) == "22"
    assert screen._format_number(20, 2) == "20.00"
    assert screen._format_number(-3.456, 1) == "-3.5"


# --- pagination --------------------------------------------------------------


def many_fields(count):
    return [
        {"source": "SoilSensor", "metric": "moisture", "label": f"M{i}"}
        for i in range(count)
    ]


def test_two_lines_fit_under_the_title_on_a_128x64_screen():
    assert layout().per_page == 2


def test_extra_fields_are_paginated_and_cycle():
    screen_layout = layout(fields=many_fields(4))
    assert screen_layout.page_count() == 2
    assert screen_layout.lines(SNAPSHOT) == ["M0: 42.4 %", "M1: 42.4 %"]
    screen_layout.advance()
    assert screen_layout.lines(SNAPSHOT) == ["M2: 42.4 %", "M3: 42.4 %"]
    screen_layout.advance()  # revient à la première page
    assert screen_layout.lines(SNAPSHOT) == ["M0: 42.4 %", "M1: 42.4 %"]


def test_an_empty_field_list_still_yields_one_page():
    screen_layout = layout(fields=[])
    assert screen_layout.page_count() == 1
    assert screen_layout.lines(SNAPSHOT) == []


def test_a_short_screen_shows_one_line_at_a_time():
    assert layout(height=32).per_page == 1


# --- dessin ------------------------------------------------------------------


def test_draw_writes_the_title_then_the_lines_and_pages_on():
    screen_layout = layout(fields=many_fields(4))
    display = MagicMock()

    screen_layout.draw(display, SNAPSHOT)

    display.clear.assert_called_once()
    display.text.assert_any_call("BOURGEON", 0, 0)
    display.text.assert_any_call("M0: 42.4 %", 0, 20)
    display.text.assert_any_call("M1: 42.4 %", 0, 40)
    display.text.assert_any_call("1/2", 100, 0)
    display.show.assert_called_once()
    # Le dessin suivant montre la page 2.
    assert screen_layout.lines(SNAPSHOT) == ["M2: 42.4 %", "M3: 42.4 %"]


def test_draw_omits_the_page_counter_when_there_is_one_page():
    display = MagicMock()
    layout().draw(display, SNAPSHOT)
    assert all("1/1" not in call[0][0] for call in display.text.call_args_list)


def test_draw_pairing_shows_the_code_and_the_device_id():
    display = MagicMock()
    layout().draw_pairing(display, "ghb-3f2a91", "ABC234")

    display.clear.assert_called_once()
    display.text.assert_any_call("BOURGEON", 0, 0)
    display.text.assert_any_call("Code : ABC234", 0, 20)
    display.text.assert_any_call("ghb-3f2a91", 0, 40)
    display.show.assert_called_once()


def test_draw_pairing_without_a_code_keeps_the_line_readable():
    display = MagicMock()
    layout().draw_pairing(display, "ghb-3f2a91", None)
    display.text.assert_any_call("Code : ----", 0, 20)


def test_a_custom_title_is_used():
    display = MagicMock()
    layout(title="SERRE 2", fields=many_fields(1)).draw(display, SNAPSHOT)
    display.text.assert_any_call("SERRE 2", 0, 0)
