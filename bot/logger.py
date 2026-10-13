"""Registro por partida de eventos recibidos y acciones enviadas."""

import json


class GameLogger:
    """Guarda ``game_<id>.log`` con los eventos (``<``) y acciones (``>``)."""

    def __init__(self):
        """Crea un registro vacío."""
        self.history = {}

    def _append(self, game_id, prefix, message):
        """Agrega una línea al historial de la partida."""
        line = prefix + json.dumps(message)
        self.history.setdefault(game_id, []).append(line)

    def log_event(self, game_id, message):
        """Registra un evento recibido del servidor."""
        self._append(game_id, '< ', message)

    def log_action(self, game_id, message):
        """Registra una acción enviada al servidor."""
        self._append(game_id, '> ', message)

    def write(self, game_id):
        """Escribe el historial de la partida en ``game_<id>.log``."""
        try:
            with open("game_{}.log".format(game_id), "w") as handle:
                lines = self.history.get(game_id, [])
                handle.write("\n".join(lines) + "\n")
            print("saved game_{}.log".format(game_id))
        except OSError as error:
            print("could not write game log: {}".format(error))
