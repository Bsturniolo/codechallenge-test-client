"""Tests de ``Board``: parseo, búsquedas, flood fill y territorio."""

import unittest

from bot.board import Board
from bot.constants import DANGER_CHAR
from tests.helpers import board_str, empty


class TestParsing(unittest.TestCase):
    """Lectura del string del servidor."""

    def test_parse_board_strips_walls(self):
        board = Board.from_string("|*  |\n|aA  |\n")
        self.assertEqual(board.grid, [list('*  '), list('aA  ')])

    def test_line_without_pipes_is_kept(self):
        self.assertEqual(Board.from_string("*A \n").grid, [list('*A ')])

    def test_find_and_count(self):
        board = Board.from_string("|*  |\n|aA  |\n")
        self.assertEqual(board.find('A'), (1, 1))
        self.assertIsNone(board.find('Z'))
        self.assertEqual(board.count('a'), 1)

    def test_size_is_derived_from_the_grid(self):
        # v2: el tamaño varía por partida y no es necesariamente cuadrado.
        board = Board.from_string(
            board_str(["1      ", "  A    ", "       ", "       ",
                       "       "]))
        self.assertEqual((board.rows, board.cols), (5, 7))

    def test_empty_grid(self):
        board = Board([])
        self.assertEqual((board.rows, board.cols), (0, 0))

    def test_in_bounds(self):
        board = Board(empty(3, 4))
        self.assertTrue(board.in_bounds((2, 3)))
        self.assertFalse(board.in_bounds((3, 0)))
        self.assertFalse(board.in_bounds((0, -1)))

    def test_tail_food_is_one_cell_each(self):
        board = Board.from_string(board_str([" ⒶⒷ "]))
        self.assertEqual(board.grid, [[' ', 'Ⓐ', 'Ⓑ', ' ']])


class TestTargetDigit(unittest.TestCase):
    """v3/v6: el dígito correcto se lee directo del tablero."""

    @staticmethod
    def _target(rows):
        return Board.from_string(board_str(rows)).target_digit()

    def test_starting_sequence(self):
        rows = ["  1   2 3 4  5  ", "       A        "]
        self.assertEqual(self._target(rows), 1)

    def test_mid_sequence(self):
        rows = ["  2   3 4 5  6  ", "       A        "]
        self.assertEqual(self._target(rows), 2)

    def test_wraps_near_nine(self):
        rows = ["  7   8 9 1  2  ", "       A        "]
        self.assertEqual(self._target(rows), 7)

    def test_no_digits_returns_none(self):
        rows = ["                ", "       A        "]
        self.assertIsNone(self._target(rows))

    def test_ignores_x_and_snakes(self):
        rows = ["  3 X 4 5  6  7", "  a  b  A  B    "]
        self.assertEqual(self._target(rows), 3)

    def test_many_copies_of_each_digit(self):
        # v6: de 3 a 5 copias por dígito.
        rows = ["666777888999", "111           "]
        self.assertEqual(self._target(rows), 6)

    def test_full_ring_falls_back_to_smallest(self):
        self.assertEqual(self._target(["123456789"]), 1)


class TestSearch(unittest.TestCase):
    """Caminos más cortos, flood fill y territorio."""

    def test_flood_fill_open_area(self):
        board = Board(empty(3, 5))
        self.assertEqual(board.flood_fill((0, 0), set(), cap=999), 15)

    def test_flood_fill_pocket(self):
        board = Board([list('bbbbb'), list('bA  b'), list('bbbbb')])
        self.assertEqual(board.flood_fill((1, 1), {'b'}, cap=999), 3)

    def test_flood_fill_respects_cap(self):
        board = Board(empty(5, 5))
        self.assertEqual(board.flood_fill((0, 0), set(), cap=4), 4)

    def test_flood_fill_blocked_start_is_zero(self):
        board = Board([list('b ')])
        self.assertEqual(board.flood_fill((0, 0), {'b'}, cap=9), 0)
        self.assertEqual(board.flood_fill((0, 1), set(), 9, {(0, 1)}), 0)

    def test_extra_coordinates_are_blocked(self):
        board = Board(empty(1, 5))
        self.assertEqual(board.flood_fill((0, 0), set(), 99, {(0, 2)}), 2)

    def test_path_to_cell(self):
        board = Board(empty(1, 5))
        self.assertEqual(board.path_to_cell((0, 0), set(), (0, 3)),
                         ['right'] * 3)
        self.assertEqual(board.path_to_cell((0, 1), set(), (0, 1)), [])

    def test_path_to_cell_unreachable(self):
        board = Board([list(' b ')])
        self.assertIsNone(board.path_to_cell((0, 0), {'b'}, (0, 2)))

    def test_path_to_char_avoids_blocked_and_finds_none(self):
        board = Board([list('A9 1')])
        self.assertIsNone(board.path_to_char((0, 0), {'9'}, '1'))
        self.assertEqual(board.path_to_char((0, 0), set(), '9'), ['right'])

    def test_walk(self):
        board = Board(empty(3, 3))
        self.assertEqual(board.walk((0, 0), ['down', 'right']),
                         [(1, 0), (1, 1)])

    def test_territory_splits_open_space(self):
        board = Board(empty(1, 7))
        self.assertEqual(board.territory((0, 1), (0, 5), set()), 3)

    def test_territory_without_rival(self):
        board = Board(empty(2, 3))
        self.assertEqual(board.territory((0, 0), None, set()), 6)

    def test_distances(self):
        board = Board(empty(1, 3))
        self.assertEqual(board.distances((0, 0), set()),
                         {(0, 0): 0, (0, 1): 1, (0, 2): 2})


BIG, SMALL = '\U0001F4A3', '\U0001F9E8'


class TestBombs(unittest.TestCase):
    """v8: zonas de explosión de las bombas."""

    def test_bombs_are_one_cell_each(self):
        board = Board.from_string(board_str([" " + BIG + SMALL + " "]))
        self.assertEqual(board.grid, [[' ', BIG, SMALL, ' ']])

    def test_big_bomb_zone_is_5x5(self):
        grid = empty(9, 9)
        grid[4][4] = BIG
        zone = Board(grid).danger_zone()
        self.assertEqual(len(zone), 25)
        self.assertIn((2, 2), zone)   # diagonal a distancia 2
        self.assertNotIn((1, 4), zone)

    def test_small_bomb_zone_is_3x3(self):
        grid = empty(9, 9)
        grid[4][4] = SMALL
        zone = Board(grid).danger_zone()
        self.assertEqual(len(zone), 9)
        self.assertIn((3, 3), zone)
        self.assertNotIn((2, 4), zone)

    def test_zone_is_clipped_to_the_board(self):
        grid = empty(5, 5)
        grid[0][0] = BIG
        self.assertEqual(len(Board(grid).danger_zone()), 9)

    def test_overlapping_zones_count_once(self):
        grid = empty(5, 9)
        grid[2][2] = SMALL
        grid[2][3] = SMALL
        self.assertEqual(len(Board(grid).danger_zone()), 12)

    def test_no_bombs_no_zone(self):
        self.assertEqual(Board(empty(3, 3)).danger_zone(), set())

    def test_mark_danger_keeps_snakes_and_walls(self):
        grid = empty(5, 5)
        grid[2][2] = SMALL
        grid[2][1] = 'b'
        grid[1][1] = '#'
        marked = Board(grid).mark_danger({'b', '#'})
        self.assertEqual(marked.char_at((2, 1)), 'b')
        self.assertEqual(marked.char_at((1, 1)), '#')
        self.assertEqual(marked.char_at((2, 2)), DANGER_CHAR)
        self.assertEqual(marked.char_at((3, 3)), DANGER_CHAR)
        self.assertEqual(marked.char_at((0, 0)), ' ')
        self.assertEqual(grid[2][2], SMALL)   # no modifica el original


if __name__ == '__main__':
    unittest.main()
