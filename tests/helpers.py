"""Utilidades compartidas por los tests."""

import contextlib
import io
import os

from bot.board import Board
from bot.planner import MovePlanner, Side, opposite

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


def quiet():
    """Silencia los ``print`` del bot durante un test."""
    return contextlib.redirect_stdout(io.StringIO())


def board_str(rows):
    """Arma el string del servidor (filas entre ``|``)."""
    return "\n".join("|" + row + "|" for row in rows) + "\n"


def empty(height, width):
    """Grilla vacía de ``height`` x ``width``."""
    return [[' '] * width for _ in range(height)]


def planner_for(grid, side='A', target_digit=1, **kwargs):
    """``MovePlanner`` para ``side`` sobre una grilla de caracteres."""
    board = Board(grid)
    own = Side.from_letter(side)
    opp = Side.from_letter(opposite(side))
    return MovePlanner(board, board.find(own.head), own, opp,
                       target_digit, **kwargs)


def choose(grid, side='A', target_digit=1, **kwargs):
    """Atajo: ``(direccion, destino)`` que elige el bot sobre ``grid``."""
    return planner_for(grid, side, target_digit, **kwargs).choose()


def turn(side='A', board=None, **extra):
    """Mensaje ``your_turn`` de ejemplo."""
    data = {
        'board': board or board_str(["A  1 ", "     ", "    B"]),
        'side': side, 'game_id': 'g', 'turn_token': 't',
        'remaining_moves': 300, 'multiplier_1': 1, 'multiplier_2': 1,
    }
    data.update(extra)
    return {'event': 'your_turn', 'data': data}
