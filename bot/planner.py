"""Estrategia: decide la próxima dirección a partir del tablero."""

from dataclasses import dataclass

from bot.constants import (
    DANGER_CHAR, DIGIT_CHARS, DIRS, MIN_REMAINING_MOVES_FOR_ACCUMULATION,
    MULTIPLIER_ACCUMULATION_CAP, MULTIPLIER_BUDGET_FACTOR,
    MULTIPLIER_CHAR, PATH_SAFETY_DEPTH,
    TAIL_FOOD, TAIL_FOOD_DETOUR_MAX, WALL_CHAR,
)


@dataclass(frozen=True)
class Side:
    """Caracteres de una serpiente: cabeza, cuerpo y su comida de cola."""

    head: str
    body: str

    @classmethod
    def from_letter(cls, letter):
        """Arma el lado a partir de la letra de la cabeza ('A' o 'B')."""
        return cls(letter, letter.lower())

    @property
    def tail(self):
        """Comida de cola que solo puede comer esta serpiente (v7)."""
        return TAIL_FOOD.get(self.head)


def opposite(letter):
    """Letra de la serpiente rival."""
    return 'B' if letter == 'A' else 'A'


def manhattan(first, second):
    """Distancia Manhattan entre dos celdas."""
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


class MovePlanner:
    """Elige la dirección de un turno.

    Prioridades, en orden: ``X`` si el multiplicador es bajo, comida de
    cola propia cercana, dígito correcto, ``X``/cola como alternativa,
    territorio y, como último recurso, cualquier movimiento legal.
    """

    def __init__(self, board, head, own, opp, target_digit,
                 own_multiplier=1, remaining_moves=None):
        """Prepara los conjuntos de celdas bloqueadas y las longitudes."""
        self.board = board
        self.head = head
        self.own = own
        self.opp = opp
        self.target_char = str(target_digit)
        self.own_multiplier = own_multiplier
        self.remaining_moves = remaining_moves
        wrong_digits = DIGIT_CHARS - {self.target_char}
        self.blocked = ({own.body, opp.body, opp.head, WALL_CHAR,
                         DANGER_CHAR} | wrong_digits)
        self.lookahead_blocked = self.blocked | {own.head}
        self.own_length = 1 + board.count(own.body)
        self.opp_length = 1 + board.count(opp.body)
        self.opp_head = board.find(opp.head)

    # --- utilidades -----------------------------------------------------

    def _step_cell(self, name):
        """Celda a la que lleva la dirección ``name`` desde la cabeza."""
        dr, dc = DIRS[name]
        return (self.head[0] + dr, self.head[1] + dc)

    def _passable(self, cell):
        """True si la celda existe y no está bloqueada."""
        inside = self.board.in_bounds(cell)
        return inside and self.board.char_at(cell) not in self.blocked

    def risky_head_on(self, cell):
        """True si pisar ``cell`` arriesga un choque de frente perdido.

        Solo se evita si el rival es estrictamente más largo.
        """
        if not self.opp_head:
            return False
        near = manhattan(cell, self.opp_head) <= 1
        return near and self.opp_length > self.own_length

    def _viable_step(self, name):
        """Celda de la dirección si es transitable y no es riesgosa."""
        cell = self._step_cell(name)
        ok = self._passable(cell) and not self.risky_head_on(cell)
        return cell if ok else None

    def step_area(self, cell):
        """Espacio libre (acotado) alcanzable desde ``cell``."""
        return self.board.flood_fill(
            cell, self.lookahead_blocked, cap=self.own_length + 1)

    def step_territory(self, cell):
        """Territorio que controlaríamos si nos paramos en ``cell``."""
        return self.board.territory(
            cell, self.opp_head, self.lookahead_blocked)

    def opp_distance_to(self, target):
        """Pasos que necesita el rival para llegar a ``target``."""
        if not self.opp_head:
            return None
        blocked = {self.own.body, self.opp.body, self.own.head, WALL_CHAR}
        path = self.board.path_to_cell(self.opp_head, blocked, target)
        return len(path) if path is not None else None

    def is_safe_path(self, path):
        """Chequeo de callejón sin salida mirando varios pasos adelante.

        Evalúa el espacio libre en el destino real del camino, tratando
        como ocupadas las últimas celdas recorridas (nuestro cuerpo).
        """
        trail = self.board.walk(self.head, path)
        end = trail[-1] if trail else self.head
        passed = trail[:-1][-PATH_SAFETY_DEPTH:] if len(trail) > 1 else []
        area = self.board.flood_fill(
            end, self.lookahead_blocked, cap=self.own_length + 1,
            extra=set(passed))
        return area >= self.own_length

    # --- alcanzar una celda con un carácter concreto (X o cola) ---------

    @staticmethod
    def _too_long(path, max_len):
        """True si hay un límite de largo y el camino lo supera."""
        return max_len is not None and len(path) > max_len

    def _reachable_path(self, char, max_len):
        """Camino seguro hacia ``char`` o ``None``."""
        if char is None:
            return None
        path = self.board.path_to_char(self.head, self.blocked, char)
        if not path or self._too_long(path, max_len):
            return None
        return path if self.is_safe_path(path) else None

    def _uncontested(self, path):
        """True si el rival no llega al destino antes o a la par."""
        end = self.board.walk(self.head, path)[-1]
        opp_dist = self.opp_distance_to(end)
        return opp_dist is None or opp_dist > len(path)

    def try_reach_char(self, char, max_len=None):
        """``(direccion, destino)`` hacia ``char`` si es seguro y libre."""
        path = self._reachable_path(char, max_len)
        if path is None:
            return None
        first = self._step_cell(path[0])
        if self.risky_head_on(first) or not self._uncontested(path):
            return None
        return path[0], self.board.walk(self.head, path)[-1]

    # --- pasos de la estrategia ----------------------------------------

    def _accumulating(self):
        """True si todavía conviene juntar multiplicadores."""
        few_x = self.own_multiplier < MULTIPLIER_ACCUMULATION_CAP
        left = self.remaining_moves
        return few_x and (
            left is None or left >= MIN_REMAINING_MOVES_FOR_ACCUMULATION)

    def _accumulate(self):
        """Fase de acumulación: ir por una ``X`` segura (v4)."""
        if self._accumulating():
            return self.try_reach_char(
                MULTIPLIER_CHAR, self._multiplier_budget())
        return None

    def _multiplier_budget(self):
        """Pasos máximos que vale la pena gastar en una ``X``.

        Una ``X`` suma +1 al multiplicador en cada comida futura, pero ir
        a buscarla retrasa las comidas por ``largo * multiplicador``. Si
        el camino es más largo que los movimientos propios que quedan
        dividido el multiplicador, no conviene. ``None`` si no se sabe
        cuántos movimientos quedan.
        """
        if self.remaining_moves is None:
            return None
        own_left = self.remaining_moves // 2
        return max(1, own_left * MULTIPLIER_BUDGET_FACTOR
                   // self.own_multiplier)

    def _grab_tail(self):
        """Comida de cola propia si está prácticamente de paso (v7)."""
        return self.try_reach_char(self.own.tail, TAIL_FOOD_DETOUR_MAX)

    def _opportunistic_bonus(self):
        """``X`` o comida de cola cuando el dígito no es alcanzable."""
        found = self.try_reach_char(MULTIPLIER_CHAR)
        return found or self.try_reach_char(self.own.tail)

    def _sub_path(self, cell):
        """Camino desde ``cell`` al dígito objetivo (``[]`` si es él)."""
        if self.board.char_at(cell) == self.target_char:
            return []
        return self.board.path_to_char(cell, self.blocked, self.target_char)

    def _candidate_entry(self, name):
        """``(largo, direccion, destino)`` hacia el dígito o ``None``."""
        cell = self._viable_step(name)
        if cell is None:
            return None
        sub = self._sub_path(cell)
        if sub is None:
            return None
        full = [name] + sub
        if not self.is_safe_path(full):
            return None
        return len(full), name, self.board.walk(self.head, full)[-1]

    def _is_contested(self, entry):
        """True si el rival llega al destino antes o a la par que nosotros."""
        length, _, end = entry
        opp_dist = self.opp_distance_to(end)
        return opp_dist is not None and opp_dist <= length

    def _split_candidates(self):
        """Separa candidatos entre ganados y disputados con el rival."""
        free, contested = [], []
        for name in DIRS:
            entry = self._candidate_entry(name)
            if entry:
                pool = contested if self._is_contested(entry) else free
                pool.append(entry)
        return free, contested

    def _pursue_digit(self):
        """Ir por el dígito correcto, prefiriendo rutas no disputadas."""
        for pool in self._split_candidates():
            if pool:
                best = min(pool, key=lambda entry: entry[0])
                return best[1], best[2]
        return None

    def _score_step(self, cell):
        """Puntaje de un paso: territorio con rival, área sin rival."""
        if self.opp_head:
            return self.step_territory(cell)
        return self.step_area(cell)

    def _territory_move(self):
        """Mejor paso por territorio cuando no hay comida alcanzable."""
        best_dir, best_score = None, -1
        for name in DIRS:
            cell = self._viable_step(name)
            if cell is None:
                continue
            score = self._score_step(cell)
            if score > best_score:
                best_dir, best_score = name, score
        return (best_dir, None) if best_dir else None

    def _resort_cost(self, char):
        """Costo aproximado de pisar ``char`` (menor es mejor)."""
        fixed = {self.own.body: 5, self.opp.body: 5, WALL_CHAR: 4,
                 self.own.head: 3, self.opp.head: 3, DANGER_CHAR: 2,
                 self.target_char: 0}
        if char in fixed:
            return fixed[char]
        return 1 if char in DIGIT_CHARS else 0

    def _resort_options(self):
        """Pares ``(costo, -espacio, direccion)`` de los pasos legales."""
        options = []
        for name in DIRS:
            cell = self._step_cell(name)
            if not self.board.in_bounds(cell):
                continue
            cost = self._resort_cost(self.board.char_at(cell))
            options.append((cost, -self.step_area(cell), name))
        return options

    def _last_resort(self):
        """Cualquier movimiento legal, del menos al más costoso.

        Celda libre, dígito incorrecto (-500), zona de bomba (v8), cabeza
        rival, pared (v5) y cuerpo. A igual costo gana el paso con más
        espacio libre alrededor, para no encerrarse.
        """
        options = self._resort_options()
        return min(options)[2] if options else None

    def choose(self):
        """Devuelve ``(direccion, celda_objetivo)``.

        La dirección es ``None`` si no existe ningún movimiento posible.
        """
        steps = (self._accumulate, self._grab_tail, self._pursue_digit,
                 self._opportunistic_bonus, self._territory_move)
        for step in steps:
            result = step()
            if result:
                return result
        return self._last_resort(), None
