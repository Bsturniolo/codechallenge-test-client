"""
Tests offline para run.py (el bot de snake).

No se conecta al servidor -- prueba directamente las funciones que
deciden el movimiento (parse_board, choose_direction, etc.) contra
tableros armados a mano, para detectar bugs de estrategia antes de
jugar una partida real.

Uso:
    Poné este archivo en la MISMA carpeta que run.py y corré:

        python3 test_run.py

    Si todo pasa, vas a ver "OK" al final. Si algo falla, te va a
    mostrar exactamente qué test y por qué.
"""

import sys
import types
import unittest

# run.py hace "import websockets" al principio. Para poder testear la
# lógica del bot sin tener que instalar esa dependencia (o sin
# conectarnos a nada), le metemos un módulo falso antes de importar.
if 'websockets' not in sys.modules:
    sys.modules['websockets'] = types.ModuleType('websockets')

import run  # noqa: E402  (import después del stub, a propósito)


class TestParsing(unittest.TestCase):
    def test_parse_board_strips_walls(self):
        board = "|*  |\n|aA  |\n"
        grid = run.parse_board(board)
        self.assertEqual(grid, [list('*  '), list('aA  ')])

    def test_find_char(self):
        grid = run.parse_board("|*  |\n|aA  |\n")
        self.assertEqual(run.find_char(grid, 'A'), (1, 1))
        self.assertEqual(run.find_char(grid, 'Z'), None)

    def test_count_char(self):
        grid = run.parse_board("|*  |\n|aA  |\n")
        self.assertEqual(run.count_char(grid, 'a'), 1)


class TestFloodFill(unittest.TestCase):
    def test_open_area_is_large(self):
        grid = run.parse_board("|     |\n|     |\n|     |\n")
        rows, cols = len(grid), len(grid[0])
        area = run.flood_fill_area(grid, rows, cols, (0, 0), blocked=set(), cap=999)
        self.assertEqual(area, rows * cols)

    def test_small_pocket_is_detected(self):
        grid = [
            list('bbbbb'),
            list('bA  b'),
            list('bbbbb'),
        ]
        area = run.flood_fill_area(grid, 3, 5, (1, 1), blocked={'b'}, cap=999)
        self.assertEqual(area, 3)  # las 3 celdas libres de la fila del medio


class TestChooseDirection(unittest.TestCase):
    def test_goes_toward_nearest_food(self):
        # Tablero real sacado de un log de partida: la comida más
        # cercana a la cabeza (fila 1, col 2) está arriba a la izquierda.
        board = (
            "|*              |\n"
            "|aaA            |\n"
            "|               |\n"
            "|               |\n"
            "|            *  |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|          * Bbb|\n"
            "|               |\n"
        )
        grid = run.parse_board(board)
        head = run.find_char(grid, 'A')
        direction = run.choose_direction(grid, 15, 15, head, 'A', 'a', 'B', 'b')
        self.assertEqual(direction, 'up')

    def test_avoids_dead_end_pocket(self):
        # A la derecha de la cabeza hay una comida, pero está sellada en
        # un pozo de 2 celdas por el cuerpo del rival (b). A la
        # izquierda hay un área grande y abierta, sin comida. El bot no
        # debería meterse en el pozo (es más chico que su propio largo).
        H, W = 6, 8
        grid = [[' '] * W for _ in range(H)]
        grid[2][3] = 'A'
        grid[2][2] = 'a'
        grid[2][1] = 'a'
        grid[2][0] = 'a'
        grid[1][0] = 'a'
        grid[0][0] = 'a'  # own_length = 6

        grid[1][4] = 'b'
        grid[1][5] = 'b'
        grid[3][4] = 'b'
        grid[3][5] = 'b'
        grid[2][6] = 'b'
        grid[2][5] = '*'  # comida sellada en el pozo

        head = run.find_char(grid, 'A')
        direction = run.choose_direction(grid, H, W, head, 'A', 'a', 'B', 'b')
        self.assertNotEqual(direction, 'right')  # 'right' es la entrada al pozo

    def test_avoids_losing_head_to_head(self):
        # El rival (B) es igual de largo y está justo al lado de una de
        # las celdas a las que podríamos ir -- no debería arriesgarse.
        board = [
            list('#########'),
            list('#  A B  #'),
            list('#  a b  #'),
            list('#  a b  #'),
            list('#        '),
            list('#*      #'),
            list('#########'),
        ]
        head = run.find_char(board, 'A')
        direction = run.choose_direction(
            board, len(board), len(board[0]), head, 'A', 'a', 'B', 'b'
        )
        self.assertNotEqual(direction, 'right')

    def test_prefers_open_territory_over_walled_food(self):
        # La comida está prácticamente encerrada por el cuerpo del
        # rival -- conviene priorizar el espacio abierto en vez de
        # meterse en esa zona.
        board = [
            list('##########'),
            list('#A       #'),
            list('#a       #'),
            list('#a bbbbb #'),
            list('#a b   b #'),
            list('#  b*  b #'),
            list('#  bbbbb #'),
            list('#        #'),
            list('#        #'),
            list('##########'),
        ]
        head = run.find_char(board, 'A')
        direction = run.choose_direction(
            board, len(board), len(board[0]), head, 'A', 'a', 'B', 'b'
        )
        self.assertNotEqual(direction, 'down')  # 'down' apunta directo a la trampa

    def test_returns_some_move_even_with_no_food_on_board(self):
        # Tablero sin comida -- el bot igual tiene que devolver una
        # dirección válida (no None, no crashear).
        board = [
            list('#####'),
            list('#A  #'),
            list('#    '),
            list('#####'),
        ]
        head = run.find_char(board, 'A')
        direction = run.choose_direction(
            board, len(board), len(board[0]), head, 'A', 'a', 'B', 'b'
        )
        self.assertIn(direction, run.DIRS.keys())


if __name__ == '__main__':
    unittest.main(verbosity=2)