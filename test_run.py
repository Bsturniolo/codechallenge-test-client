"""
Tests offline para run.py (el bot de snake).

No se conecta al servidor -- prueba directamente las funciones que
deciden el movimiento (parse_board, choose_direction, etc.) contra
tableros armados a mano, para detectar bugs de estrategia antes de
jugar una partida real.

Cubre las reglas v1 (tablero fijo), v2 (tablero de tamaño variable) y
v3 (comida = secuencia de dígitos ascendente cíclica).

Uso:
    Poné este archivo en la MISMA carpeta que run.py y corré:

        python3 test_run.py

    Si todo pasa, vas a ver "OK" al final. Si algo falla, te va a
    mostrar exactamente qué test y por qué.
"""

import json
import os
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

    def test_board_size_derived_from_grid_not_fields(self):
        # v2: board size now varies per match. We don't trust any
        # particular field name for rows/cols -- we derive it from the
        # parsed board itself, so this has to work for a non-square,
        # arbitrary-sized board too.
        board = "|1      |\n|  A    |\n|       |\n|       |\n|       |\n"
        grid = run.parse_board(board)
        rows, cols = len(grid), len(grid[0])
        self.assertEqual((rows, cols), (5, 7))


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


class TestDigitState(unittest.TestCase):
    """v3: la comida es una secuencia de dígitos 1-9 en orden ascendente
    cíclico -- y es GLOBAL, compartida entre los dos jugadores (esto lo
    confirmamos con un log real: cuando el rival come el dígito
    correcto, la secuencia avanza igual que si lo hubiéramos comido
    nosotros). Por eso el tracker mira score_1 Y score_2 cada turno."""

    def test_new_game_starts_expecting_starting_digit(self):
        state = run.get_digit_state('un_game_id_nuevo_' + str(id(object())))
        self.assertEqual(state['expected'], run.STARTING_DIGIT)

    def test_advances_when_we_eat_correctly(self):
        state = {'expected': 1, 'last_score_1': 50, 'last_score_2': 20}
        run.sync_expected_digit(state, score_1=50, score_2=120)  # we ate digit 1 (+100)
        self.assertEqual(state['expected'], 2)

    def test_advances_when_rival_eats_correctly(self):
        # This is the key fix: the rival eating the right digit ALSO
        # advances what WE should aim for next.
        state = {'expected': 3, 'last_score_1': 200, 'last_score_2': 300}
        run.sync_expected_digit(state, score_1=500, score_2=300)  # rival ate digit 3 (+300)
        self.assertEqual(state['expected'], 4)

    def test_wrong_catch_does_not_change_expected(self):
        state = {'expected': 5, 'last_score_1': 100, 'last_score_2': 300}
        run.sync_expected_digit(state, score_1=100, score_2=-200)  # we ate a wrong digit (-500)
        self.assertEqual(state['expected'], 5)

    def test_plain_survival_does_not_change_expected(self):
        state = {'expected': 5, 'last_score_1': 100, 'last_score_2': 300}
        run.sync_expected_digit(state, score_1=101, score_2=301)  # just +1 each, no food eaten
        self.assertEqual(state['expected'], 5)

    def test_wraps_from_nine_to_one(self):
        state = {'expected': 9, 'last_score_1': 0, 'last_score_2': 0}
        run.sync_expected_digit(state, score_1=0, score_2=900)  # ate digit 9
        self.assertEqual(state['expected'], 1)

    def test_first_turn_just_records_baseline_without_crashing(self):
        state = run.get_digit_state('brand_new_game')
        run.sync_expected_digit(state, score_1=0, score_2=0)
        self.assertEqual(state['expected'], run.STARTING_DIGIT)
        self.assertEqual(state['last_score_1'], 0)
        self.assertEqual(state['last_score_2'], 0)

    def test_replays_real_match_log_and_tracks_correctly(self):
        # Regression test built from an actual tournament match where our
        # bot's OLD (per-player) tracking got out of sync with the rival
        # and took five -500 penalties in a row. This replays the real
        # score_1/score_2 sequence from that match and checks our
        # tracker lands on the actually-correct digit every time a real
        # catch (by either player) happened.
        match_path = os.path.join(os.path.dirname(__file__), 'match_fixed.json')
        if not os.path.exists(match_path):
            self.skipTest('match_fixed.json not present -- skipping real-match replay')

        with open(match_path) as f:
            data = json.load(f)
        our_turns = [
            e['turn_data'] for e in data
            if 'turn_data' in e and e['turn_data']['side'] == 'B'
        ]
        state = {'expected': run.STARTING_DIGIT, 'last_score_1': None, 'last_score_2': None}
        # These are the (remaining_moves, correct_digit) checkpoints we
        # independently reconstructed from the full match: the digit our
        # tracker SHOULD be aiming for right before each of those turns.
        checkpoints = {283: 1, 267: 2, 163: 8, 133: 9, 109: 1, 81: 3, 13: 5}
        seen = 0
        for td in our_turns:
            if td['remaining_moves'] in checkpoints:
                self.assertEqual(
                    state['expected'], checkpoints[td['remaining_moves']],
                    'wrong target digit at remaining={}'.format(td['remaining_moves'])
                )
                seen += 1
            run.sync_expected_digit(state, td['score_1'], td['score_2'])
        self.assertEqual(seen, len(checkpoints))  # make sure we actually checked all of them


class TestChooseDirection(unittest.TestCase):
    def test_goes_toward_nearest_food_v1_style(self):
        # Tablero real (v1, con '*') sacado de un log de partida vieja.
        # choose_direction ahora espera un dígito objetivo -- lo probamos
        # igual apuntando a un dígito presente para chequear que el
        # pathing en sí sigue funcionando bien.
        board = (
            "|    1          |\n"
            "|aaA            |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
            "|            Bbb|\n"
            "|               |\n"
        )
        grid = run.parse_board(board)
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, len(grid), len(grid[0]), head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'up')
        self.assertEqual(target, (0, 4))

    def test_multistep_lookahead_catches_trap_a_single_step_check_would_miss(self):
        # The food sits right in a board corner, just past our own short
        # tail. A single-step check would see a huge connected open area
        # from the very first cell (most of the board is empty) and
        # judge it perfectly safe. Only checking a few steps INTO the
        # path -- where our own body has followed us -- reveals that the
        # corner itself leaves no room to turn around. The bot should
        # recognize this isn't safely reachable and NOT commit to it
        # (falls back to open space instead).
        board = (
            "|1              |\n"  # food in the literal corner
            "|aaA            |\n"
            "|               |\n"
            "|               |\n"
            "|               |\n"
        )
        grid = run.parse_board(board)
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, len(grid), len(grid[0]), head, 'A', 'a', 'B', 'b', target_digit=1
        )
        # It should NOT have locked onto the corner food as a safe target.
        self.assertIsNone(target)
        self.assertIn(direction, run.DIRS.keys())

    def test_targets_correct_digit_and_ignores_others(self):
        # Hay un '7' (incorrecto) cerca y un '1' (correcto, el esperado)
        # más lejos -- el bot tiene que ir por el '1', no por el más
        # cercano nomás porque sea comida.
        H, W = 5, 10
        grid = [[' '] * W for _ in range(H)]
        grid[2][0] = 'A'
        grid[1][2] = '7'   # más cerca, pero incorrecto
        grid[2][6] = '1'   # más lejos, pero es el correcto
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'right')
        self.assertEqual(target, (2, 6))

    def test_routes_around_wrong_digit_blocking_the_path(self):
        # El único camino directo pasa justo por encima de un dígito
        # incorrecto -- el bot NO debería pisarlo, tiene que rodearlo.
        H, W = 5, 5
        grid = [[' '] * W for _ in range(H)]
        grid[2][0] = 'A'
        grid[2][1] = '9'  # incorrecto, bloquea el camino directo
        grid[2][2] = '1'  # correcto, justo detrás
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertNotEqual(direction, 'right')  # 'right' pisaría el 9

    def test_avoids_dead_end_pocket(self):
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
        grid[2][5] = '1'  # target, sellado en el pozo

        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertNotEqual(direction, 'right')  # 'right' es la entrada al pozo

    def test_avoids_losing_head_to_head(self):
        board = [
            list('#########'),
            list('#  A B  #'),
            list('#  a b  #'),
            list('#  a b  #'),
            list('#        '),
            list('#1      #'),
            list('#########'),
        ]
        head = run.find_char(board, 'A')
        direction, target = run.choose_direction(
            board, len(board), len(board[0]), head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertNotEqual(direction, 'right')

    def test_returns_some_move_even_with_no_target_digit_on_board(self):
        # El dígito que estamos esperando todavía no apareció en el
        # tablero -- el bot igual tiene que devolver una dirección
        # válida (no None, no crashear), jugando seguro mientras tanto.
        board = [
            list('#####'),
            list('#A  #'),
            list('#    '),
            list('#####'),
        ]
        head = run.find_char(board, 'A')
        direction, target = run.choose_direction(
            board, len(board), len(board[0]), head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertIn(direction, run.DIRS.keys())
        self.assertIsNone(target)

    def test_x_is_not_blocked_even_when_it_sits_in_the_way(self):
        # v4: 'X' (multiplicador) es siempre segura para pisar. Si el
        # camino más corto al dígito correcto pasa justo por una 'X', no
        # debería rodearla como hace con los dígitos incorrectos.
        H, W = 3, 5
        grid = [[' '] * W for _ in range(H)]
        grid[1][0] = 'A'
        grid[1][2] = 'X'
        grid[1][4] = '1'
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'right')  # va derecho, sin rodear la X

    def test_goes_for_x_when_target_digit_not_safely_reachable(self):
        # v4: si el dígito correcto no está en el tablero todavía (o no
        # es alcanzable con seguridad), conviene ir a buscar la X en vez
        # de solo maximizar territorio -- es ganancia gratis.
        H, W = 3, 7
        grid = [[' '] * W for _ in range(H)]
        grid[1][0] = 'A'
        grid[1][4] = 'X'
        # no hay ningún dígito '1' en el tablero
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'right')
        self.assertEqual(target, (1, 4))

    def test_prefers_reachable_digit_over_x(self):
        # Si el dígito correcto SÍ es alcanzable de forma segura, hay que
        # ir por él primero (vale mucho más que los +50 fijos de la X),
        # no desviarse a buscar la X aunque esté más cerca.
        H, W = 3, 7
        grid = [[' '] * W for _ in range(H)]
        grid[1][3] = 'A'
        grid[1][2] = 'X'   # más cerca, a la izquierda
        grid[1][5] = '1'   # el objetivo correcto, un poco más lejos
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'right')  # va por el dígito, no por la X


if __name__ == '__main__':
    unittest.main(verbosity=2)