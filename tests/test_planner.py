"""Tests de ``MovePlanner``: la estrategia de movimiento (v1 a v7)."""

import unittest

from bot.board import Board
from bot.constants import DIRS, MULTIPLIER_ACCUMULATION_CAP
from bot.planner import MovePlanner, Side, manhattan, opposite
from tests.helpers import choose, empty, planner_for

CAP = MULTIPLIER_ACCUMULATION_CAP
TAIL_A, TAIL_B = 'Ⓐ', 'Ⓑ'


class TestSide(unittest.TestCase):
    """Caracteres asociados a cada serpiente."""

    def test_from_letter(self):
        side = Side.from_letter('A')
        self.assertEqual((side.head, side.body), ('A', 'a'))

    def test_tail_food_per_side(self):
        self.assertEqual(Side.from_letter('A').tail, TAIL_A)
        self.assertEqual(Side.from_letter('B').tail, TAIL_B)
        self.assertIsNone(Side.from_letter('Z').tail)

    def test_opposite_and_manhattan(self):
        self.assertEqual((opposite('A'), opposite('B')), ('B', 'A'))
        self.assertEqual(manhattan((0, 0), (2, 3)), 5)


class TestBasicRouting(unittest.TestCase):
    """Ir al dígito correcto esquivando obstáculos."""

    def test_goes_toward_nearest_food(self):
        grid = empty(15, 15)
        for col in (0, 1):
            grid[1][col] = 'a'
        grid[1][2] = 'A'
        grid[0][4] = '1'
        grid[13][12] = 'B'
        self.assertEqual(choose(grid), ('up', (0, 4)))

    def test_multistep_lookahead_catches_corner_trap(self):
        # La comida está en la esquina, pasando nuestra cola: un chequeo
        # de un solo paso la creería segura.
        grid = empty(5, 15)
        grid[0][0] = '1'
        grid[1][0] = grid[1][1] = 'a'
        grid[1][2] = 'A'
        direction, target = choose(grid)
        self.assertIsNone(target)
        self.assertIn(direction, DIRS)

    def test_targets_correct_digit_and_ignores_others(self):
        grid = empty(5, 10)
        grid[2][0] = 'A'
        grid[1][2] = '7'
        grid[2][6] = '1'
        self.assertEqual(choose(grid), ('right', (2, 6)))

    def test_routes_around_wrong_digit(self):
        grid = empty(5, 5)
        grid[2][0] = 'A'
        grid[2][1] = '9'
        grid[2][2] = '1'
        self.assertNotEqual(choose(grid)[0], 'right')

    def test_avoids_dead_end_pocket(self):
        grid = empty(6, 8)
        for pos in ((2, 2), (2, 1), (2, 0), (1, 0), (0, 0)):
            grid[pos[0]][pos[1]] = 'a'
        grid[2][3] = 'A'
        for pos in ((1, 4), (1, 5), (3, 4), (3, 5), (2, 6)):
            grid[pos[0]][pos[1]] = 'b'
        grid[2][5] = '1'
        self.assertNotEqual(choose(grid)[0], 'right')

    def test_target_adjacent(self):
        grid = empty(3, 5)
        grid[1][1] = 'A'
        grid[1][2] = '1'
        self.assertEqual(choose(grid), ('right', (1, 2)))

    def test_no_target_on_board_still_moves(self):
        grid = [list('#####'), list('#A  #'), list('#    '), list('#####')]
        direction, target = choose(grid)
        self.assertIn(direction, DIRS)
        self.assertIsNone(target)

    def test_no_rival_uses_area_fallback(self):
        grid = empty(3, 5)
        grid[1][1] = 'A'
        direction, target = choose(grid)
        self.assertIsNotNone(direction)
        self.assertIsNone(target)

    def test_side_b_perspective(self):
        grid = empty(3, 7)
        grid[1][1] = 'B'
        grid[1][4] = '1'
        self.assertEqual(choose(grid, side='B'), ('right', (1, 4)))


class TestRaceAndRisk(unittest.TestCase):
    """Carreras contra el rival y choques de frente."""

    def test_pursues_contested_digit_if_only_option(self):
        grid = empty(5, 15)
        grid[2][0] = 'A'
        grid[2][12] = 'B'
        grid[2][13] = 'b'
        grid[2][10] = '1'
        self.assertEqual(choose(grid), ('right', (2, 10)))

    def test_pursues_digit_when_not_contested(self):
        grid = empty(5, 15)
        grid[2][0] = 'A'
        grid[2][3] = '1'
        grid[2][13] = 'B'
        grid[2][14] = 'b'
        self.assertEqual(choose(grid), ('right', (2, 3)))

    def test_avoids_losing_head_to_head(self):
        grid = [list('#########'), list('#  A B  #'), list('#  a b  #'),
                list('#  a b  #'), list('#        '), list('#1      #'),
                list('#########')]
        self.assertNotEqual(choose(grid)[0], 'right')

    def test_risky_head_on_is_skipped_in_candidates(self):
        grid = empty(5, 7)
        grid[2][1] = 'A'
        grid[2][4] = '1'
        grid[1][3] = 'B'
        for pos in ((0, 4), (0, 5), (0, 6), (1, 4), (1, 5)):
            grid[pos[0]][pos[1]] = 'b'
        self.assertIsNotNone(choose(grid)[0])

    def test_risky_cells_skipped_by_territory_fallback(self):
        grid = empty(3, 5)
        grid[1][1] = 'A'
        grid[1][3] = 'B'
        grid[0] = list('bbbbb')
        self.assertIsNotNone(choose(grid)[0])

    def test_no_rival_means_no_risk(self):
        planner = planner_for(self._grid_without_rival())
        self.assertFalse(planner.risky_head_on((0, 0)))
        self.assertIsNone(planner.opp_distance_to((0, 0)))

    @staticmethod
    def _grid_without_rival():
        grid = empty(3, 3)
        grid[1][1] = 'A'
        return grid

    def test_boxed_in_returns_none(self):
        grid = [list('aba'), list('bAb'), list('aba')]
        self.assertEqual(choose(grid), (None, None))

    def test_last_resort_into_rival_head(self):
        grid = [list('bbb'), list('aAB'), list('bbb')]
        self.assertEqual(choose(grid)[0], 'right')


class TestMultiplierX(unittest.TestCase):
    """v4: pickups de ``X`` y fase de acumulación."""

    def test_x_is_not_blocked_by_itself(self):
        grid = empty(3, 7)
        grid[1][0] = 'A'
        grid[1][2] = 'X'
        grid[1][4] = '1'
        self.assertEqual(choose(grid, own_multiplier=CAP)[0], 'right')

    def test_goes_for_x_when_digit_not_reachable(self):
        grid = empty(3, 7)
        grid[1][0] = 'A'
        grid[1][4] = 'X'
        self.assertEqual(choose(grid), ('right', (1, 4)))

    def test_accumulation_prefers_x_while_multiplier_low(self):
        grid = empty(3, 7)
        grid[1][3] = 'A'
        grid[1][2] = 'X'
        grid[1][5] = '1'
        self.assertEqual(choose(grid, own_multiplier=1)[0], 'left')

    def test_prefers_digit_when_multiplier_high(self):
        grid = empty(3, 7)
        grid[1][3] = 'A'
        grid[1][2] = 'X'
        grid[1][5] = '1'
        self.assertEqual(choose(grid, own_multiplier=CAP)[0], 'right')

    def test_x_fallback_after_accumulation(self):
        grid = empty(3, 7)
        grid[1][0] = 'A'
        grid[1][4] = 'X'
        self.assertEqual(
            choose(grid, own_multiplier=CAP), ('right', (1, 4)))

    def test_late_game_skips_accumulation(self):
        grid = empty(3, 7)
        grid[1][3] = 'A'
        grid[1][2] = 'X'
        grid[1][5] = '1'
        direction, _ = choose(grid, own_multiplier=1, remaining_moves=10)
        self.assertEqual(direction, 'right')

    def test_contested_x_is_rejected(self):
        grid = empty(3, 9)
        grid[1][0] = 'A'
        grid[1][6] = 'X'
        grid[1][5] = 'B'
        self.assertNotEqual(choose(grid)[1], (1, 6))


class TestV5Wall(unittest.TestCase):
    """v5: la pared ``#`` es un obstáculo duro."""

    def test_walks_around_wall(self):
        grid = empty(5, 9)
        grid[2][0] = 'A'
        grid[2][6] = '1'
        for row in (1, 2, 3):
            grid[row][3] = '#'
        direction, target = choose(grid)
        self.assertIn(direction, ('up', 'down'))
        self.assertEqual(target, (2, 6))

    def test_wall_not_chosen_when_alternative_exists(self):
        grid = empty(3, 5)
        grid[1][1] = 'A'
        grid[1][2] = '#'
        self.assertNotEqual(choose(grid)[0], 'right')

    def test_rival_path_estimate_treats_wall_as_obstacle(self):
        grid = empty(3, 7)
        grid[1][0] = 'A'
        grid[1][4] = '1'
        grid[1][6] = 'B'
        for row in range(3):
            grid[row][5] = '#'
        self.assertEqual(choose(grid), ('right', (1, 4)))

    def test_last_resort_prefers_non_wall(self):
        grid = [['#', 'b', ' '], ['A', 'B', ' '], ['b', ' ', ' ']]
        self.assertEqual(choose(grid)[0], 'right')

    def test_last_resort_uses_wall_if_nothing_else(self):
        grid = [list('b#a'), list('bAa'), list('baa')]
        self.assertEqual(choose(grid)[0], 'up')


class TestV6Copies(unittest.TestCase):
    """v6: varias copias de cada dígito."""

    def test_goes_to_nearest_copy(self):
        grid = empty(3, 15)
        grid[1][7] = 'A'
        grid[1][3] = '1'
        grid[1][9] = '1'
        grid[0][0] = '2'
        self.assertEqual(choose(grid), ('right', (1, 9)))

    def test_wrong_digit_copies_are_obstacles(self):
        grid = empty(3, 7)
        grid[1][0] = 'A'
        grid[1][1] = '2'
        grid[1][5] = '1'
        self.assertNotEqual(choose(grid)[0], 'right')


class TestV7TailFood(unittest.TestCase):
    """v7: comida de cola ``Ⓐ``/``Ⓑ``."""

    def test_grabs_adjacent_own_tail_over_far_digit(self):
        grid = empty(3, 9)
        grid[1][3] = 'A'
        grid[1][4] = TAIL_A
        grid[1][7] = '1'
        grid[1][0] = 'X'
        self.assertEqual(
            choose(grid, own_multiplier=CAP), ('right', (1, 4)))

    def test_far_tail_does_not_distract(self):
        grid = empty(3, 15)
        grid[1][5] = 'A'
        grid[1][6] = '1'
        grid[1][0] = TAIL_A
        self.assertEqual(
            choose(grid, own_multiplier=CAP), ('right', (1, 6)))

    def test_goes_for_far_tail_when_no_digit(self):
        grid = empty(3, 9)
        grid[1][0] = 'A'
        grid[1][6] = TAIL_A
        self.assertEqual(
            choose(grid, own_multiplier=CAP), ('right', (1, 6)))

    def test_rival_letter_tail_is_passable_not_a_target(self):
        grid = empty(3, 7)
        grid[1][0] = 'A'
        grid[1][2] = TAIL_B
        grid[1][5] = '1'
        self.assertEqual(choose(grid), ('right', (1, 5)))

    def test_side_b_uses_its_own_letter(self):
        grid = empty(3, 7)
        grid[1][1] = 'B'
        grid[1][2] = TAIL_B
        self.assertEqual(
            choose(grid, side='B', own_multiplier=CAP), ('right', (1, 2)))

    def test_side_without_tail_food(self):
        grid = empty(3, 5)
        grid[1][1] = 'Z'
        board = Board(grid)
        planner = MovePlanner(board, (1, 1), Side('Z', 'z'),
                              Side.from_letter('A'), 1)
        self.assertIsNotNone(planner.choose()[0])


class TestPlannerPieces(unittest.TestCase):
    """Métodos internos con casos de borde."""

    def test_opp_distance_counts_steps(self):
        grid = empty(1, 6)
        grid[0][0] = 'A'
        grid[0][5] = 'B'
        self.assertEqual(planner_for(grid).opp_distance_to((0, 2)), 3)

    def test_safe_path_single_step(self):
        grid = empty(3, 3)
        grid[1][1] = 'A'
        self.assertTrue(planner_for(grid).is_safe_path(['up']))

    def test_empty_path_counts_the_head_as_occupied(self):
        grid = empty(3, 3)
        grid[1][1] = 'A'
        self.assertFalse(planner_for(grid).is_safe_path([]))

    def test_step_area_and_territory(self):
        grid = empty(3, 5)
        grid[1][0] = 'A'
        grid[1][4] = 'B'
        planner = planner_for(grid)
        self.assertGreater(planner.step_area((0, 0)), 0)
        self.assertGreater(planner.step_territory((1, 1)), 0)


if __name__ == '__main__':
    unittest.main()
