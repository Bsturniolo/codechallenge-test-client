"""Replays de partidas reales de torneo como tests de regresión."""

import json
import os
import unittest

from bot.board import Board
from tests.helpers import DATA_DIR

# remaining_moves -> dígito correcto, reconstruido a partir de los
# puntajes reales de ambos jugadores en esa partida.
CHECKPOINTS = {283: 1, 267: 2, 163: 8, 133: 9, 109: 2, 81: 3, 13: 5}


def our_turns(filename):
    """Turnos del lado B de una partida guardada en ``tests/data``."""
    with open(os.path.join(DATA_DIR, filename)) as handle:
        data = json.load(handle)
    return [e['turn_data'] for e in data
            if 'turn_data' in e and e['turn_data']['side'] == 'B']


class TestRealMatches(unittest.TestCase):
    """La lectura del dígito objetivo coincide con partidas reales."""

    def test_target_digit_matches_ground_truth(self):
        seen = 0
        for turn_data in our_turns('match_fixed.json'):
            expected = CHECKPOINTS.get(turn_data['remaining_moves'])
            if expected is not None:
                board = Board.from_string(turn_data['board'])
                self.assertEqual(board.target_digit(), expected)
                seen += 1
        self.assertEqual(seen, len(CHECKPOINTS))

    def test_high_multiplier_match_always_has_a_target(self):
        turns = our_turns('match4_fixed.json')
        self.assertGreater(len(turns), 0)
        for turn_data in turns:
            board = Board.from_string(turn_data['board'])
            self.assertIn(board.target_digit(), range(1, 10))


if __name__ == '__main__':
    unittest.main()
