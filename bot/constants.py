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

# Comida libre '*' (v9): celdas de una snake cortada por un disparo; la
# puede comer cualquiera de las dos y vale +100 * multiplicador.
FREE_FOOD_CHAR = '*'

# Se desvía por la comida de cola propia solo si está a esta distancia.
TAIL_FOOD_DETOUR_MAX = 2

# Se prioriza juntar 'X' mientras el multiplicador propio sea menor.
MULTIPLIER_ACCUMULATION_CAP = 16

# Qué tan lejos vale la pena ir por una 'X': el presupuesto de pasos es
# movimientos propios restantes * este factor / multiplicador. Con 1 es
# el punto de equilibrio teórico; más alto busca multiplicadores más seguido.
MULTIPLIER_BUDGET_FACTOR = 2

# Con menos movimientos restantes que estos, ya no se acumula 'X'.
MIN_REMAINING_MOVES_FOR_ACCUMULATION = 30

# Cantidad de celdas recientes del camino que se consideran ocupadas por
# el cuerpo al evaluar si un camino termina en un callejón sin salida.
PATH_SAFETY_DEPTH = 3

# v8 (14 oct 2026): bombas de proximidad. Explotan cuando la cabeza
# termina un movimiento a distancia Chebyshev (max(|dfila|, |dcol|)) menor
# o igual al radio. La explosión deja el puntaje en 0 (o -500 si ya era
# <= 0) pero el movimiento se hace igual. Son un carácter cada una
# (fuera del BMP, por eso se separan las filas por code point).
BOMB_RADII = {'\U0001F4A3': 2, '\U0001F9E8': 1}

# Marca interna (no existe en el juego) para las celdas dentro de la
# zona de explosión de alguna bomba: el bot las trata como prohibidas.
DANGER_CHAR = '\ue000'

# Al moverse por territorio (sin comida alcanzable) se aceptan los pasos
# con al menos esta fracción del mejor territorio, y entre ellos se elige
# el que queda más cerca del dígito objetivo.
TERRITORY_TOLERANCE = 0.9

# Estimación para decidir entre una 'X' y el dígito objetivo: cada 'X'
# suma +50 y un punto de multiplicador, que vale (dígito promedio * 100)
# en cada comida futura.
MULTIPLIER_PICKUP_POINTS = 50
EXPECTED_DIGIT = 5

# Carpeta donde se guardan los logs de cada partida (se crea sola).
LOG_DIR = 'partidas'

# Agresividad: el dígito objetivo se prefiere a una 'X' aunque rinda hasta
# esta cantidad de veces menos puntos por paso. Con 1 es neutral; más alto
# come antes y junta menos multiplicadores.
DIGIT_PRIORITY = 1

# Entre varias copias del dígito objetivo se prefiere la que deja más cerca
# al dígito siguiente: costo = pasos + este peso * distancia al siguiente.
FOLLOW_UP_WEIGHT = 0.5

# Pasos por comida que se suponen como mínimo al estimar cuántas comidas
# alcanza a hacer una 'X'. Medido en las partidas contra el mejor rival:
# comía cada ~12 movimientos propios (200 / 17 comidas).
MIN_MOVES_PER_EAT = 12

# --- v9: disparos --------------------------------------------------------
# Interruptor general: en False el bot nunca dispara.
SHOOTING_ENABLED = True

# Cada disparo cuesta esto, pegue o no (y hace falta tenerlo para disparar).
SHOT_COST = 5000

# Máximo de disparos por partida: se dispara solo si hace falta.
MAX_SHOTS_PER_GAME = 1

# Puntaje mínimo que tiene que quedar después de pagar el disparo.
SHOT_MIN_SCORE_LEFT = 5000

# Con menos movimientos propios que estos ya no da tiempo a comer la comida.
SHOT_MIN_OWN_MOVES_LEFT = 40

# Lo que se espera recuperar tiene que ser al menos esta cantidad de veces
# el costo del disparo (margen por si la estimación es optimista).
SHOT_MIN_RETURN = 1.5

# Si el rival nos lleva más que esto, se juega más agresivo: se permiten
# más disparos y se exige menos retorno esperado (hay que descontar).
SHOT_BEHIND_GAP = 15000
MAX_SHOTS_WHEN_BEHIND = 2
SHOT_MIN_RETURN_WHEN_BEHIND = 1.0

# Si ya ganamos por más que esto, no se gasta un disparo.
SHOT_LEAD_LIMIT = 20000

# Comida libre que dejan las celdas cortadas (v9).

# Lo que cuesta pisar una pared '#' o un dígito incorrecto (el movimiento
# de pared no se hace, el de dígito sí). Sirve para comparar con un choque.
WRONG_STEP_COST = 500

# Desvío máximo (pasos de más) para levantar una X yendo hacia el dígito.
VIA_X_MAX_DETOUR = 2
