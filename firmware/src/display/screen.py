"""Contenu de l'écran : des champs déclarés dans le manifeste.

``app.py`` ne sait pas ce qui s'affiche : il décrit un instantané —

    {"sensors": {"ClimateSensor": {"temperature": {"value": 21.5, "unit": "celsius"}}},
     "actuators": {"WaterPump": "ON"}}

— et ce module en fait des lignes. Changer ce que montre l'écran (une autre
mesure, un autre ordre, un libellé différent) ne touche donc que le manifeste.
"""

# Le boîtier n'a pas de `dataclasses` : classes simples, comme le reste du
# firmware.
UNIT_LABELS = {
    "celsius": "°C",
    "percent": "%",
    "lux": "lux",
}

# Un champ actionneur publie "ON"/"OFF" : on l'écrit en clair.
ACTUATOR_LABELS = {"ON": "Allumé", "OFF": "Éteint"}

# Quand le manifeste ne déclare pas de champs : le comportement historique
# (température et humidité du premier capteur qui les publie). C'est une donnée
# de configuration, pas une règle dispersée dans le contrôleur.
DEFAULT_FIELDS = (
    {"source": "auto", "metric": "temperature", "label": "Temp", "decimals": 1},
    {"source": "auto", "metric": "humidity", "label": "Hum", "decimals": 0},
)

DEFAULT_TITLE = "BOURGEON"


def _format_number(value, decimals):
    """Arrondit et complète les zéros sans dépendre des f-strings à précision
    dynamique, dont le support varie d'une version de MicroPython à l'autre."""
    if decimals <= 0:
        return str(int(round(value)))
    text = str(round(value, decimals))
    if "." not in text:
        text += "." + "0" * decimals
    return text


class ScreenField:
    """Une ligne : une mesure nommée, et comment l'écrire."""

    DEFAULT_DECIMALS = 1

    def __init__(
        self, source, metric=None, label=None, unit=None, decimals=None, kind="sensor"
    ):
        self.source = source
        self.metric = metric
        self.label = label or metric or source
        self.unit = unit
        self.decimals = self.DEFAULT_DECIMALS if decimals is None else int(decimals)
        self.kind = kind

    @classmethod
    def from_dict(cls, spec):
        source = spec.get("source")
        if not source:
            raise ValueError("champ d'écran sans 'source'")
        return cls(
            source=source,
            metric=spec.get("metric"),
            label=spec.get("label"),
            unit=spec.get("unit"),
            decimals=spec.get("decimals"),
            kind=spec.get("kind", "sensor"),
        )

    def _resolved_source(self, snapshot):
        """``auto`` : le premier capteur de l'instantané qui publie la métrique."""
        if self.source != "auto":
            return self.source
        for sensor_id, readings in snapshot.get("sensors", {}).items():
            if isinstance(readings, dict) and self.metric in readings:
                return sensor_id
        return None

    def raw(self, snapshot):
        """``(valeur, unité)`` de la mesure, ou ``(None, None)`` si absente."""
        source = self._resolved_source(snapshot)
        if source is None:
            return None, None

        if self.kind == "actuator":
            state = snapshot.get("actuators", {}).get(source)
            return state, None

        if self.metric is None:
            return None, None
        component = snapshot.get("sensors", {}).get(source)
        if not isinstance(component, dict):
            return None, None
        metric = component.get(self.metric)
        if isinstance(metric, dict):
            return metric.get("value"), metric.get("unit")
        if isinstance(metric, (int, float)):
            return metric, None  # métrique publiée en clair
        return None, None

    def text(self, snapshot):
        value, unit = self.raw(snapshot)
        if value is None:
            return f"{self.label}: --"
        if isinstance(value, str):
            return f"{self.label}: {ACTUATOR_LABELS.get(value, value)}"
        unit = self.unit or UNIT_LABELS.get(unit, unit) or ""
        number = _format_number(value, self.decimals)
        return f"{self.label}: {number} {unit}".rstrip()


class ScreenLayout:
    """Ce que l'écran montre : un titre, des champs, paginés si nécessaire."""

    def __init__(self, title, fields, height=64, line_height=20, first_line_y=20):
        self.title = title
        self.fields = fields
        self.line_height = line_height
        self.first_line_y = first_line_y
        # Nombre de lignes lisibles sous le titre : 2 sur un 128x64.
        self.per_page = max(1, (height - first_line_y) // line_height)
        self._page = 0

    @classmethod
    def from_manifest(cls, config):
        fields = []
        for spec in config.get("fields", DEFAULT_FIELDS):
            try:
                fields.append(ScreenField.from_dict(spec))
            except ValueError as error:
                # Un champ mal écrit ne doit pas priver de tout l'écran.
                print(f"Champ d'écran ignoré : {error}")
        return cls(
            title=config.get("title", DEFAULT_TITLE),
            fields=fields,
            height=config.get("height", 64),
        )

    def page_count(self):
        return max(1, -(-len(self.fields) // self.per_page))  # arrondi au-dessus

    def lines(self, snapshot):
        """Les lignes de la page courante."""
        start = self._page * self.per_page
        return [
            field.text(snapshot) for field in self.fields[start : start + self.per_page]
        ]

    def advance(self):
        self._page = (self._page + 1) % self.page_count()

    def draw(self, display, snapshot):
        """Dessine la page courante, puis passe à la suivante."""
        display.clear()
        display.text(self.title, 0, 0)
        y = self.first_line_y
        for text in self.lines(snapshot):
            display.text(text, 0, y)
            y += self.line_height
        if self.page_count() > 1:
            display.text(f"{self._page + 1}/{self.page_count()}", 100, 0)
        display.show()
        self.advance()

    def draw_pairing(self, display, device_id, code):
        """Écran d'appairage : le code à saisir dans l'application."""
        display.clear()
        display.text(self.title, 0, 0)
        display.text(f"Code : {code or '----'}", 0, 20)
        display.text(device_id, 0, 40)
        display.show()
