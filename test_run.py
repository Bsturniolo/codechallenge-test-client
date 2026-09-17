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
    cíclico -- y es GLOBAL, compartida entre los dos jugadores.

    Según la documentación oficial ("How to play"), el próximo dígito
    correcto se puede leer directo del tablero: es el que está en juego
    cuyo predecesor cíclico (...8, 9, 1...) NO está también en el
    tablero (el tablero siempre tiene 5 dígitos consecutivos en juego a
    la vez). Esto reemplaza un sistema anterior más frágil que trataba
    de inferir la secuencia mirando cómo cambiaba el puntaje turno a
    turno -- funcionaba, pero tenía un punto débil real: con el
    multiplicador de v4, una captura correcta podía valer mucho más de
    lo que ese sistema esperaba y perdía el rastro. Leerlo directo del
    tablero no tiene ningún estado que se pueda desincronizar."""

    def test_reads_the_starting_sequence(self):
        # Al arrancar la partida están los dígitos 1-5 en juego; el
        # correcto es el 1 (su predecesor, el 9, no está en el tablero).
        grid = run.parse_board("|  1   2 3 4  5  |\n|       A        |\n")
        self.assertEqual(run.determine_target_digit(grid), 1)

    def test_reads_a_mid_sequence_run(self):
        # Ya se comió el 1 (correctamente) y apareció el 6 -- quedan
        # 2,3,4,5,6 en juego. El correcto es el 2 (su predecesor, el 1,
        # ya no está en el tablero).
        grid = run.parse_board("|  2   3 4 5  6  |\n|       A        |\n")
        self.assertEqual(run.determine_target_digit(grid), 2)

    def test_wraps_correctly_near_nine(self):
        # Racha que cruza el techo del ciclo: 7,8,9,1,2 en juego. El
        # correcto es el 7 (su predecesor cíclico, el 6, no está).
        grid = run.parse_board("|  7   8 9 1  2  |\n|       A        |\n")
        self.assertEqual(run.determine_target_digit(grid), 7)

    def test_falls_back_gracefully_with_no_digits_on_board(self):
        # No debería pasar según las reglas (siempre hay 5 en juego),
        # pero si pasa, no debería romperse -- devuelve None y
        # process_snake_move usa STARTING_DIGIT como respaldo.
        grid = run.parse_board("|                |\n|       A        |\n")
        self.assertIsNone(run.determine_target_digit(grid))

    def test_ignores_x_and_snake_characters(self):
        # 'X' y las letras de las víboras no son dígitos -- no deberían
        # interferir con la lectura de la secuencia.
        grid = run.parse_board("|  3 X 4 5  6  7|\n|  a  b  A  B    |\n")
        self.assertEqual(run.determine_target_digit(grid), 3)

    def test_replays_real_match_and_matches_ground_truth(self):
        # Regression test con una partida real de torneo. Estos
        # checkpoints (remaining_moves -> dígito correcto) surgen de
        # reconstruir la secuencia completa a partir de los puntajes
        # reales de ambos jugadores en esa partida -- confirman que
        # leer directo del tablero da el mismo resultado que el análisis
        # manual detallado (y de hecho corrigió un error nuestro: a
        # remaining=109 habíamos anotado mal un "1" cuando el tablero ya
        # mostraba que el 1 había sido comido y el correcto era el 2).
        match_path = os.path.join(os.path.dirname(__file__), 'match_fixed.json')
        if not os.path.exists(match_path):
            self.skipTest('match_fixed.json not present -- skipping real-match replay')
        with open(match_path) as f:
            data = json.load(f)
        our_turns = [
            e['turn_data'] for e in data
            if 'turn_data' in e and e['turn_data']['side'] == 'B'
        ]
        checkpoints = {283: 1, 267: 2, 163: 8, 133: 9, 109: 2, 81: 3, 13: 5}
        seen = 0
        for td in our_turns:
            if td['remaining_moves'] in checkpoints:
                grid = run.parse_board(td['board'])
                target = run.determine_target_digit(grid)
                self.assertEqual(
                    target, checkpoints[td['remaining_moves']],
                    'wrong target digit at remaining={}'.format(td['remaining_moves'])
                )
                seen += 1
        self.assertEqual(seen, len(checkpoints))

    def test_replays_real_high_multiplier_match(self):
        # La misma verificación contra la partida con multiplicador
        # x10 que desincronizó el sistema viejo. Leer directo del
        # tablero es inmune a ese bug por diseño: nunca mira el
        # puntaje ni el multiplicador para nada.
        match_path = os.path.join(os.path.dirname(__file__), 'match4_fixed.json')
        if not os.path.exists(match_path):
            self.skipTest('match4_fixed.json not present -- skipping real-match replay')
        with open(match_path) as f:
            data = json.load(f)
        our_turns = [
            e['turn_data'] for e in data
            if 'turn_data' in e and e['turn_data']['side'] == 'B'
        ]
        checked = 0
        for td in our_turns:
            grid = run.parse_board(td['board'])
            target = run.determine_target_digit(grid)
            self.assertIsNotNone(target)
            self.assertIn(target, range(1, 10))
            checked += 1
        self.assertGreater(checked, 0)


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

    def test_still_pursues_a_contested_digit_when_its_the_only_option(self):
        # Basado en una derrota real: el rival está mucho más cerca del
        # dígito que nosotros (nos ganaría la carrera y podría
        # cerrarnos el paso), pero es la ÚNICA comida en el tablero y el
        # único camino disponible -- no quedarse quieto es mejor que la
        # alternativa (no hay alternativa).
        H, W = 5, 15
        grid = [[' '] * W for _ in range(H)]
        grid[2][0] = 'A'
        grid[2][12] = 'B'  # rival mucho más cerca del objetivo
        grid[2][13] = 'b'
        grid[2][10] = '1'
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'right')
        self.assertEqual(target, (2, 10))

    def test_pursues_digit_normally_when_race_is_not_contested(self):
        # Cuando el rival está lejos y no hay riesgo real de carrera, el
        # comportamiento tiene que seguir siendo el de siempre: ir
        # directo por el dígito correcto.
        H, W = 5, 15
        grid = [[' '] * W for _ in range(H)]
        grid[2][0] = 'A'
        grid[2][3] = '1'
        grid[2][13] = 'B'  # rival lejos, sin chance de disputar esta celda
        grid[2][14] = 'b'
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1
        )
        self.assertEqual(direction, 'right')
        self.assertEqual(target, (2, 3))

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

    def test_accumulation_phase_prefers_x_while_multiplier_is_low(self):
        # v4: mientras nuestro propio multiplicador todavía es bajo,
        # conviene ir por la X primero -- compone el valor de TODAS las
        # capturas futuras. Confirmado con una partida real: el rival
        # que hizo esto nos sacó 33432 a 284.
        H, W = 3, 7
        grid = [[' '] * W for _ in range(H)]
        grid[1][3] = 'A'
        grid[1][2] = 'X'   # más cerca, a la izquierda
        grid[1][5] = '1'   # el dígito correcto, un poco más lejos
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1, own_multiplier=1
        )
        self.assertEqual(direction, 'left')  # prioriza la X

    def test_prefers_digit_once_multiplier_is_high_enough(self):
        # Una vez que ya juntamos bastante multiplicador, conviene
        # empezar a cobrar: ir directo por el dígito correcto en vez de
        # seguir sumando X indefinidamente.
        H, W = 3, 7
        grid = [[' '] * W for _ in range(H)]
        grid[1][3] = 'A'
        grid[1][2] = 'X'
        grid[1][5] = '1'
        head = run.find_char(grid, 'A')
        direction, target = run.choose_direction(
            grid, H, W, head, 'A', 'a', 'B', 'b', target_digit=1,
            own_multiplier=run.MULTIPLIER_ACCUMULATION_CAP,
        )
        self.assertEqual(direction, 'right')  # ya no vale la pena seguir juntando X


if __name__ == '__main__':
    unittest.main(verbosity=2)