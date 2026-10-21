"""Tests de los disparos (v9): impacto, celdas cortadas y condiciones."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.board import Board
from bot.constants import SHOT_COST
from bot.logger import GameLogger
from bot.planner import Side
from bot.shooter import Shooter, cut_cells, ray_hit, snake_chain
from bot.snake_bot import SnakeBot
from tests.helpers import board_str, quiet, turn

OPP = Side.from_letter('B')


def rows_with_rival():
    """12x14: nosotros arriba (0, 8); rival horizontal en la fila 5.

    El rival tiene la cabeza en (5, 12) y el cuerpo hasta (5, 3): 10
    celdas. Un disparo hacia abajo desde (0, 8) pega en (5, 8).
    """
    rows = [' ' * 14 for _ in range(12)]
    rows[0] = ' ' * 8 + 'A' + ' ' * 5
    rows[5] = '   ' + 'b' * 9 + 'B' + ' '
    return rows


def board():
    return Board.from_string(board_str(rows_with_rival()))


class TestRay(unittest.TestCase):
    """Hacia dónde llega un disparo."""

    def test_hits_first_rival_cell(self):
        self.assertEqual(ray_hit(board(), (0, 8), 'down', OPP), (5, 8))

    def test_passes_over_own_body_food_and_bombs(self):
        rows = rows_with_rival()
        rows[2] = ' ' * 8 + 'a' + ' ' * 5
        rows[3] = ' ' * 8 + '*' + ' ' * 5
        rows[4] = ' ' * 8 + 'X' + ' ' * 5
        rows[1] = ' ' * 8 + '\U0001F4A3' + ' ' * 5
        hit = ray_hit(Board.from_string(board_str(rows)), (0, 8), 'down', OPP)
        self.assertEqual(hit, (5, 8))

    def test_wall_covers_the_rival(self):
        rows = rows_with_rival()
        rows[3] = ' ' * 8 + '#' + ' ' * 5
        wall = Board.from_string(board_str(rows))
        self.assertIsNone(ray_hit(wall, (0, 8), 'down', OPP))

    def test_misses_at_the_border(self):
        self.assertIsNone(ray_hit(board(), (0, 8), 'up', OPP))
        self.assertIsNone(ray_hit(board(), (0, 8), 'right', OPP))


class TestCut(unittest.TestCase):
    """Cuántas celdas del rival se cortan."""

    def test_chain_goes_from_head_to_tail(self):
        chain = snake_chain(board(), OPP)
        self.assertEqual(chain[0], (5, 12))
        self.assertEqual(chain[-1], (5, 3))
        self.assertEqual(len(chain), 10)

    def test_chain_none_without_rival_head(self):
        rows = rows_with_rival()
        rows[5] = '   ' + 'b' * 9 + ' ' + ' '
        self.assertIsNone(snake_chain(Board.from_string(board_str(rows)), OPP))

    def test_chain_none_when_the_rival_cells_do_not_form_a_path(self):
        rows = [' ' * 6 for _ in range(4)]
        rows[1] = ' B' + 'bb' + ' ' * 2
        rows[0] = 'bb' + ' ' * 4
        odd = Board.from_string(board_str(rows))
        self.assertIsNone(snake_chain(odd, OPP))

    def test_cut_from_middle_to_tail(self):
        self.assertEqual(cut_cells(board(), OPP, (5, 8)), 6)

    def test_cut_at_head_leaves_only_the_head(self):
        self.assertEqual(cut_cells(board(), OPP, (5, 12)), 9)

    def test_cut_zero_for_unknown_cell(self):
        self.assertEqual(cut_cells(board(), OPP, (0, 0)), 0)


def state(**extra):
    base = {'game_id': 'g', 'score': 30000, 'rival_score': 30000,
            'own_moves_left': 100, 'multiplier': 30}
    base.update(extra)
    return base


class TestShooter(unittest.TestCase):
    """Cuándo se dispara."""

    def setUp(self):
        self.shooter = Shooter()

    def decide(self, **extra):
        return self.shooter.decide(board(), (0, 8), OPP, state(**extra))

    def test_shoots_when_it_pays(self):
        self.assertEqual(self.decide(), 'down')

    def test_worth_it_math(self):
        self.assertTrue(Shooter.worth_it(6, 30))
        self.assertFalse(Shooter.worth_it(6, 20))
        self.assertFalse(Shooter.worth_it(10, 10))

    def test_not_worth_with_low_multiplier(self):
        self.assertIsNone(self.decide(multiplier=5))

    def test_needs_score_left_after_paying(self):
        self.assertIsNone(self.decide(score=SHOT_COST + 4999))
        self.assertIsNone(self.decide(score=100))

    def test_not_when_far_ahead(self):
        self.assertIsNone(self.decide(score=60000, rival_score=0))

    def test_not_when_no_time_to_eat(self):
        self.assertIsNone(self.decide(own_moves_left=5))

    def test_only_one_shot_per_game(self):
        self.shooter.record('g')
        self.assertIsNone(self.decide())
        self.assertEqual(
            self.shooter.decide(board(), (0, 8), OPP, state(game_id='h')),
            'down')

    def test_switch_turns_shooting_off(self):
        with patch('bot.shooter.SHOOTING_ENABLED', False):
            self.assertIsNone(self.decide())

    def test_no_line_of_fire(self):
        shooter = Shooter()
        self.assertIsNone(shooter.decide(board(), (11, 0), OPP, state()))


class TestBotShooting(unittest.TestCase):
    """El bot manda ``shoot`` en vez de ``move`` cuando corresponde."""

    def setUp(self):
        self.bot = SnakeBot(GameLogger())

    def play(self, **extra):
        websocket = MagicMock()
        websocket.send = AsyncMock()
        request = turn('A', board=board_str(rows_with_rival()),
                       score_1=30000, score_2=30000, multiplier_1=30,
                       **extra)
        with quiet():
            asyncio.run(self.bot.handle_turn(websocket, request))
        return json.loads(websocket.send.call_args[0][0])

    def test_sends_shoot_with_game_and_turn_token(self):
        message = self.play()
        self.assertEqual(message['action'], 'shoot')
        self.assertEqual(message['data']['direction'], 'down')
        self.assertEqual(message['data']['game_id'], 'g')
        self.assertEqual(message['data']['turn_token'], 't')

    def test_second_turn_moves_instead_of_shooting(self):
        self.assertEqual(self.play()['action'], 'shoot')
        self.assertEqual(self.play()['action'], 'move')

    def test_moves_when_score_is_low(self):
        websocket = MagicMock()
        websocket.send = AsyncMock()
        request = turn('A', board=board_str(rows_with_rival()),
                       score_1=100, score_2=0, multiplier_1=30)
        with quiet():
            asyncio.run(self.bot.handle_turn(websocket, request))
        sent = json.loads(websocket.send.call_args[0][0])
        self.assertEqual(sent['action'], 'move')

    def test_shot_evaluation_errors_mean_no_shot(self):
        with patch('bot.snake_bot.Board.from_string',
                   side_effect=ValueError('raro')):
            with quiet():
                self.assertIsNone(self.bot.shot_direction(
                    turn('A')['data']))

    def test_no_head_means_no_shot(self):
        data = turn('A', board=board_str(["     ", "    B"]))['data']
        with quiet():
            self.assertIsNone(self.bot.shot_direction(data))

    def test_shot_state_for_side_b_reads_second_fields(self):
        data = turn('B', score_1=10, score_2=20, multiplier_2=3)['data']
        info = self.bot.shot_state(data)
        self.assertEqual((info['score'], info['rival_score']), (20, 10))
        self.assertEqual(info['multiplier'], 3)
        self.assertEqual(info['own_moves_left'], 150)


if __name__ == '__main__':
    unittest.main()
