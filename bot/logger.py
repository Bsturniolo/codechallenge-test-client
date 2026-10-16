"""Registro por partida de eventos recibidos y acciones enviadas."""

import json
import os

from bot.constants import LOG_DIR


class GameLogger:
    """Guarda ``<log_dir>/game_<id>.log`` con eventos (``<``) y acciones."""

    def __init__(self, log_dir=LOG_DIR):
        """Crea un registro vacío que escribirá dentro de ``log_dir``."""
        self.history = {}
        self.log_dir = log_dir

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

    def path_for(self, game_id):
        """Ruta del archivo de log de la partida."""
        return os.path.join(self.log_dir, "game_{}.log".format(game_id))

    def write(self, game_id):
        """Escribe el historial de la partida, creando la carpeta."""
        path = self.path_for(game_id)
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            with open(path, "w") as handle:
                lines = self.history.get(game_id, [])
                handle.write("\n".join(lines) + "\n")
            print("saved {}".format(path))
        except OSError as error:
            print("could not write game log: {}".format(error))
