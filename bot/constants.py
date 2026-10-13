"""Constantes del juego y de la estrategia del bot.

Cada regla nueva de la cátedra suele agregar una constante acá (por
ejemplo ``WALL_CHAR`` en v5 o ``TAIL_FOOD`` en v7).
"""

SERVER_URI = "wss://server.codechallenge.net.ar/ws?token={}"
RECONNECT_DELAY_SECONDS = 3

# Direcciones que acepta el servidor y su desplazamiento (fila, columna).
DIRS = {
    'up': (-1, 0),
    'down': (1, 0),
    'left': (0, -1),
    'right': (0, 1),
}

# v3: comida numérica. Solo el dígito objetivo suma, el resto resta 500.
DIGIT_CHARS = set('123456789')
STARTING_DIGIT = 1

# v4: la 'X' da +50 y sube el multiplicador permanente del jugador.
MULTIPLIER_CHAR = 'X'

# v5: pared. Chocarla cuesta -500 y la serpiente no se mueve.
WALL_CHAR = '#'

# v7: comida de cola (letra encerrada en un círculo). Solo la puede
# comer la serpiente de esa letra: Ⓐ (U+24B6) la A y Ⓑ (U+24B7) la B.
TAIL_FOOD = {'A': 'Ⓐ', 'B': 'Ⓑ'}

# Se desvía por la comida de cola propia solo si está a esta distancia.
TAIL_FOOD_DETOUR_MAX = 2

# Se prioriza juntar 'X' mientras el multiplicador propio sea menor.
MULTIPLIER_ACCUMULATION_CAP = 11

# Con menos movimientos restantes que estos, ya no se acumula 'X'.
MIN_REMAINING_MOVES_FOR_ACCUMULATION = 30

# Cantidad de celdas recientes del camino que se consideran ocupadas por
# el cuerpo al evaluar si un camino termina en un callejón sin salida.
PATH_SAFETY_DEPTH = 3
