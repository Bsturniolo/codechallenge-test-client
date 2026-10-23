"""Tests del modelo de carreras por los próximos dígitos."""

import unittest
from unittest.mock import patch

from bot.board import Board
from bot.planner import Side
from bot.race import INF, RaceModel
from tests.helpers import empty

A, B = Side.from_letter('A'), Side.from_letter('B')


def model(grid, target=1, moves=None):
    board = Board(grid)
    return RaceModel(board, board.find('A'), board.find('B'), A, B, target,
                     moves)


def row(width=20, **cells):
    """Tablero de 3 filas; ``cNN=carácter`` lo pone en la fila del medio."""
    grid = empty(3, width)
    for col, char in cells.items():
        grid[1][int(col[1:])] = char
    return grid


class TestDistances(unittest.TestCase):
    """Distancias, llegadas y lista de dígitos."""

    def test_digits_stop_at_the_first_missing_one(self):
        grid = row(c0='1', c3='2', c5='4', c8='A', c9='B')
        self.assertEqual(model(grid).digits, [1, 2])

    def test_digits_wrap_from_nine_to_one(self):
        grid = row(c0='9', c3='1', c8='A', c9='B')
        self.assertEqual(model(grid, target=9).digits, [9, 1])

    def test_distances_to_every_copy(self):
        grid = row(c0='1', c6='1', c3='A', c9='B')
        self.assertEqual(model(grid).distances('us', (1, 3), 1),
                         {(1, 0): 3, (1, 6): 3})

    def test_unreachable_copies_are_left_out(self):
        grid = row(c0='1', c4='A', c9='B')
        for line in grid:
            line[2] = '#'
        self.assertEqual(model(grid).distances('us', (1, 4), 1), {})

    def test_arrival_waits_until_the_digit_is_the_target(self):
        grid = row(c0='1', c3='A', c9='B')
        times = model(grid).arrivals('us', ((1, 3), 0), 1, 10)
        self.assertEqual(times, {(1, 0): 11})

    def test_fastest_of_nothing(self):
        self.assertEqual(RaceModel.fastest({}), (INF, None))
        self.assertEqual(RaceModel.fastest({'a': 3, 'b': 2}), (2, 'b'))


class TestValue(unittest.TestCase):
    """Quién gana cada carrera y cuántos puntos vale."""

    def test_closer_player_wins_the_first_digits(self):
        grid = row(c0='1', c1='2', c4='A', c15='B')
        self.assertGreater(model(grid).value('any'), 0)

    def test_rival_wins_when_closer(self):
        grid = row(c0='1', c1='2', c15='A', c4='B')
        self.assertLess(model(grid).value('any'), 0)

    def test_ties_go_to_the_rival(self):
        grid = row(c6='1', c4='A', c8='B')
        self.assertLess(model(grid).value('any'), 0)

    def test_skipping_lets_the_rival_eat_it(self):
        grid = row(c0='1', c10='A', c2='B')
        self.assertEqual(model(grid).value(None), -100)

    def test_a_lost_chase_leaves_us_far_from_the_next_digit(self):
        grid = row(c0='1', c19='2', c10='A', c2='B')
        m = model(grid)
        self.assertEqual(m.value(None), 60)
        self.assertEqual(m.value((1, 0)), -260)

    def test_races_beyond_our_moves_are_ignored(self):
        grid = row(c0='1', c1='2', c4='A', c15='B')
        self.assertEqual(model(grid, moves=1).value('any'), 0)

    def test_chasing_a_copy_we_cannot_reach_changes_nothing(self):
        grid = row(c0='1', c10='A', c2='B')
        m = model(grid)
        self.assertEqual(m._wasted_chase((1, 99), ((1, 10), 0)),
                         ((1, 10), 0))


class TestBest(unittest.TestCase):
    """La decisión: disputar una copia o dejar el dígito."""

    def test_chases_when_we_are_closer(self):
        grid = row(c0='1', c1='2', c4='A', c15='B')
        self.assertEqual(model(grid).best(), ('chase', (1, 0)))

    def test_prefers_the_copy_that_leaves_us_better_placed(self):
        grid = row(c4='1', c10='1', c11='2', c6='A', c19='B')
        self.assertEqual(model(grid).best(), ('chase', (1, 10)))

    def test_skips_a_lost_race_to_get_ready_for_the_next_digit(self):
        grid = row(c0='1', c19='2', c10='A', c2='B')
        self.assertEqual(model(grid).best(), ('skip', None))

    def test_skips_a_won_digit_when_it_costs_the_next_one(self):
        grid = row(c0='1', c19='2', c4='A', c15='B')
        self.assertEqual(model(grid).best(), ('skip', None))

    def test_nothing_without_digits(self):
        self.assertIsNone(model(row(c3='A', c9='B')).best())

    def test_value_is_computed_for_every_option(self):
        grid = row(c0='1', c6='1', c3='A', c9='B')
        with patch.object(RaceModel, 'value', return_value=0.0) as value:
            model(grid).best()
        self.assertEqual(value.call_count, 3)
