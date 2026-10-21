"""Tests de ``SnakeBot`` y del envío de mensajes."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.constants import DIRS
from bot.logger import GameLogger
from bot.protocol import send
from bot.snake_bot import SnakeBot
from tests.helpers import board_str, quiet, turn


def fake_socket():
    """WebSocket falso que registra lo enviado."""
    websocket = MagicMock()
    websocket.send = AsyncMock()
    return websocket


class TestSend(unittest.TestCase):
    """Serialización de acciones."""

    def test_send_serializes(self):
        websocket = fake_socket()
        with quiet():
            asyncio.run(send(websocket, 'move', {'direction': 'up'}))
        sent = json.loads(websocket.send.call_args[0][0])
        self.assertEqual(sent, {'action': 'move',
                                'data': {'direction': 'up'}})


class TestSnakeBot(unittest.TestCase):
    """Un turno completo: del mensaje a la dirección enviada."""

    def setUp(self):
        self.logger = GameLogger()
        self.bot = SnakeBot(self.logger)

    def _play(self, request):
        websocket = fake_socket()
        with quiet():
            asyncio.run(self.bot.handle_turn(websocket, request))
        return json.loads(websocket.send.call_args[0][0])

    def test_sends_valid_move_for_side_a(self):
        message = self._play(turn('A'))
        self.assertEqual(message['action'], 'move')
        self.assertEqual(message['data']['direction'], 'right')
        self.assertEqual(message['data']['game_id'], 'g')

    def test_side_b_reads_multiplier_2(self):
        board = board_str(["B  1 ", "     ", "    A"])
        message = self._play(turn('B', board=board, multiplier_2=20))
        self.assertIn(message['data']['direction'], DIRS)

    def test_multipliers_by_side(self):
        data = {'side': 'A', 'multiplier_1': 3, 'multiplier_2': 5}
        self.assertEqual(SnakeBot.multipliers(data), (3, 5))
        data['side'] = 'B'
        self.assertEqual(SnakeBot.multipliers(data), (5, 3))

    def test_without_multiplier_fields(self):
        request = turn('A')
        del request['data']['multiplier_1'], request['data']['multiplier_2']
        self.assertIn(self._play(request)['data']['direction'], DIRS)

    def test_no_digits_on_board_uses_default_target(self):
        board = board_str(["A    ", "     ", "    B"])
        message = self._play(turn('A', board=board))
        self.assertIn(message['data']['direction'], DIRS)

    def test_no_head_falls_back_to_random(self):
        board = board_str(["     ", "     ", "    B"])
        message = self._play(turn('A', board=board))
        self.assertIn(message['data']['direction'], DIRS)

    def test_planner_error_falls_back_to_random(self):
        with patch('bot.snake_bot.Board.from_string',
                   side_effect=ValueError('tablero raro')):
            message = self._play(turn('A'))
        self.assertEqual(message['action'], 'move')
        self.assertIn(message['data']['direction'], DIRS)

    def test_free_food_on_board_is_played_normally(self):
        board = board_str(["     ", " A * ", "     "])
        message = self._play(turn('A', board=board))
        self.assertEqual(message['data']['direction'], 'right')

    def test_boxed_in_falls_back_to_random(self):
        board = board_str(["aba", "bAb", "aba"])
        message = self._play(turn('A', board=board))
        self.assertIn(message['data']['direction'], DIRS)

    def test_does_not_walk_into_a_bomb_zone(self):
        # La bomba chica explota a 1 celda: ir a la derecha dejaría la
        # cabeza dentro del cuadrado de 3x3, aunque el dígito esté ahí.
        rows = ["A    ", "  \U0001F9E8  ", "     "]
        board = board_str(rows).replace("A    ", "A 1  ", 1)
        direction = self._play(turn('A', board=board))['data']['direction']
        self.assertNotEqual(direction, 'right')
        self.assertIn(direction, DIRS)

    def test_big_bomb_blocks_a_diagonal_approach(self):
        rows = ["A      ", "       ", "   \U0001F4A3   ", "       ",
                "      B"]
        board = board_str(rows)
        direction = self._play(turn('A', board=board))['data']['direction']
        self.assertIn(direction, DIRS)

    def test_logs_action(self):
        self._play(turn('A'))
        self.assertTrue(self.logger.history['g'][-1].startswith('> '))

    def test_random_direction_is_valid(self):
        with patch('bot.snake_bot.choice', return_value='up'):
            self.assertEqual(SnakeBot.random_direction(), 'up')


if __name__ == '__main__':
    unittest.main()
