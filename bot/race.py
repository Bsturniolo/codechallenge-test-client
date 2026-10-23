"""Modelo de carreras por los próximos dígitos.

El tablero muestra a la vez cinco dígitos consecutivos, cada uno con
varias copias. Cuando alguien come una copia del dígito objetivo se van
todas y el siguiente pasa a ser el objetivo, así que la partida es una
sucesión de carreras: gana cada dígito quien llega primero a alguna copia.
Quien gana queda parado en esa copia y el otro, mientras tanto, pudo
acercarse al dígito que sigue.

``RaceModel`` simula esa sucesión con distancias reales del tablero y
decide si conviene disputar el dígito actual (y por qué copia) o dejarlo
y posicionarse para el que sigue.
"""

from bot.constants import (
    DANGER_CHAR, DIGIT_CHARS, RACE_DISCOUNT, RACE_HORIZON, WALL_CHAR)

INF = float('inf')


class RaceModel:
    """Simulación de las próximas carreras entre nosotros y el rival."""

    def __init__(self, board, head, opp_head, own, opp, target_digit,
                 own_moves_left=None):
        """Guarda posiciones y arma la lista de dígitos a simular."""
        self.board = board
        self.start = {'us': head, 'rival': opp_head}
        self.limit = INF if own_moves_left is None else own_moves_left
        self.blocked = {
            'us': {own.body, opp.body, opp.head, WALL_CHAR, DANGER_CHAR},
            'rival': {own.body, own.head, opp.body, WALL_CHAR, DANGER_CHAR},
        }
        self.digits = self._digits(int(target_digit))
        self.copies = {d: board.positions(str(d)) for d in self.digits}
        self.cache = {}

    def _digits(self, first):
        """Dígitos consecutivos a simular que están en el tablero."""
        found = []
        for step in range(RACE_HORIZON):
            digit = (first - 1 + step) % 9 + 1
            if not self.board.positions(str(digit)):
                break
            found.append(digit)
        return found

    def distances(self, who, source, digit):
        """``{copia: pasos}`` de ``source`` a cada copia de ``digit``."""
        key = (who, source, digit)
        if key not in self.cache:
            blocked = self.blocked[who] | (DIGIT_CHARS - {str(digit)})
            reach = self.board.distances(source, blocked)
            self.cache[key] = {copy: reach[copy]
                               for copy in self.copies[digit] if copy in reach}
        return self.cache[key]

    def arrivals(self, who, state, digit, free_at):
        """``{copia: instante de llegada}`` de un jugador a cada copia.

        No se puede pisar el dígito antes de que sea el objetivo: hay que
        llegar al menos un paso después de ``free_at``.
        """
        cell, since = state
        steps = self.distances(who, cell, digit)
        return {copy: max(since + n, free_at + 1) for copy, n in steps.items()}

    @staticmethod
    def fastest(times):
        """``(instante, copia)`` más temprano de ``{copia: instante}``."""
        if not times:
            return INF, None
        copy = min(times, key=times.get)
        return times[copy], copy

    def _our_times(self, state, index, free_at, first_copy):
        """Llegadas nuestras; en el primer dígito, solo a ``first_copy``."""
        ours = self.arrivals('us', state, self.digits[index], free_at)
        if index == 0 and first_copy != 'any':
            ours = {c: t for c, t in ours.items() if c == first_copy}
        return ours

    def _contest(self, index, states, free_at, first_copy):
        """Resuelve una carrera: ``(ganador, instante, copia)`` o ``None``."""
        mine = self.fastest(
            self._our_times(states['us'], index, free_at, first_copy))
        theirs = self.fastest(self.arrivals(
            'rival', states['rival'], self.digits[index], free_at))
        if min(mine[0], theirs[0]) > self.limit:
            return None
        return ('us',) + mine if mine[0] < theirs[0] else ('rival',) + theirs

    def _wasted_chase(self, copy, state):
        """Dónde quedamos si seguimos hacia ``copy`` y el rival la comió."""
        cell, since = state
        steps = self.distances('us', cell, self.digits[0]).get(copy, INF)
        return (copy, since + steps) if steps < INF else state

    def _settle(self, index, states, free_at, first_copy):
        """Resuelve una carrera y actualiza ``states``: ``(ganador, t)``."""
        result = self._contest(index, states, free_at, first_copy)
        if result is None:
            return None
        who, instant, copy = result
        chased = index == 0 and first_copy not in (None, 'any')
        if who == 'rival' and chased:
            states['us'] = self._wasted_chase(first_copy, states['us'])
        states[who] = (copy, instant)
        return who, instant

    def value(self, first_copy='any'):
        """Puntos esperados (nuestros menos del rival) en las carreras.

        ``first_copy`` es la copia del dígito actual que disputamos;
        ``None`` es no disputarlo y ``'any'`` la mejor que alcancemos.
        """
        states = {who: (cell, 0) for who, cell in self.start.items()}
        free_at, total, weight = 0, 0.0, 1.0
        for index, digit in enumerate(self.digits):
            result = self._settle(index, states, free_at, first_copy)
            if result is None:
                break
            who, free_at = result
            total += (1 if who == 'us' else -1) * weight * digit * 100
            weight *= RACE_DISCOUNT
        return total

    def best(self):
        """``('chase', copia)``, ``('skip', None)`` o ``None`` si no hay datos.

        Compara disputar cada copia alcanzable contra dejar el dígito. Con
        el mismo valor se prefiere disputar la copia más cercana.
        """
        if not self.digits:
            return None
        reach = self.distances('us', self.start['us'], self.digits[0])
        options = [(self.value(copy), -steps, ('chase', copy))
                   for copy, steps in reach.items()]
        options.append((self.value(None), -INF, ('skip', None)))
        return max(options, key=lambda o: o[:2])[2]
