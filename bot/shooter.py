"""Disparos (v9): cuándo vale la pena gastar 5000 puntos en cortar al rival."""

from bot.board import Board
from bot.constants import (
    DIRS, FREE_FOOD_CHAR, MAX_SHOTS_PER_GAME, MAX_SHOTS_WHEN_BEHIND,
    SHOOTING_ENABLED, SHOT_BEHIND_GAP, SHOT_COST, SHOT_LEAD_LIMIT,
    SHOT_MIN_OWN_MOVES_LEFT, SHOT_MIN_RETURN, SHOT_MIN_RETURN_WHEN_BEHIND,
    SHOT_MIN_SCORE_LEFT, WALL_CHAR)

NEVER = float('inf')


def ray_hit(board, head, name, opp):
    """Celda de la serpiente rival que impacta un disparo, o ``None``.

    El disparo sale de ``head`` en línea recta y pasa por encima de todo
    (nuestro cuerpo, comida, ``X``, bombas); se frena en el borde, en un
    muro ``#`` o en la primera celda de la serpiente rival.
    """
    row_step, col_step = DIRS[name]
    cell = (head[0] + row_step, head[1] + col_step)
    while board.in_bounds(cell):
        char = board.char_at(cell)
        if char in (opp.head, opp.body):
            return cell
        if char == WALL_CHAR:
            return None
        cell = (cell[0] + row_step, cell[1] + col_step)
    return None


def _next_cells(board, chain, cells):
    """Celdas del rival vecinas a la última de ``chain`` y sin usar."""
    return [cell for _, cell in board.neighbors(chain[-1])
            if cell in cells and cell not in chain]


def _extend(board, chain, cells):
    """Completa ``chain`` con todas las ``cells``; ``None`` si no se puede."""
    if len(chain) == len(cells):
        return chain
    for nxt in _next_cells(board, chain, cells):
        found = _extend(board, chain + [nxt], cells)
        if found:
            return found
    return None


def snake_chain(board, opp):
    """Celdas del rival ordenadas de la cabeza a la cola, o ``None``."""
    head = board.find(opp.head)
    if head is None:
        return None
    cells = set(board.positions(opp.body)) | {head}
    return _extend(board, [head], cells)


def cut_list(board, opp, hit):
    """Celdas del rival que se cortan si el disparo pega en ``hit``."""
    chain = snake_chain(board, opp)
    if chain is None or hit not in chain:
        return []
    index = chain.index(hit)
    return chain[1:] if index == 0 else chain[index:]


def cut_cells(board, opp, hit):
    """Cuántas celdas del rival se cortan si el disparo pega en ``hit``."""
    return len(cut_list(board, opp, hit))


def _with_food(board, cells):
    """Copia del tablero con las celdas cortadas convertidas en comida."""
    after = Board([list(row) for row in board.grid])
    for row, col in cells:
        after.grid[row][col] = FREE_FOOD_CHAR
    return after


def race_counts(board, head, opp, cells):
    """``(nuestras, del rival)``: celdas cortadas que comería cada uno.

    Las celdas cortadas pasan a ser comida. El rival mueve primero después
    del disparo, así que nosotros solo ganamos las celdas a las que
    llegamos en menos pasos que él; con empate se las lleva el rival.
    """
    own_head = board.char_at(head)
    after = _with_food(board, cells)
    ours = after.distances(
        head, {own_head.lower(), opp.body, opp.head, WALL_CHAR})
    theirs = after.distances(
        board.find(opp.head),
        {own_head.lower(), own_head, opp.body, WALL_CHAR})
    mine = {c for c in cells if ours.get(c, NEVER) < theirs.get(c, NEVER)}
    return len(mine), len(set(cells) & set(theirs) - mine)


class Shooter:
    """Decide si disparar: un tiro a la cabeza o el que más daño haga.

    El disparo es instantáneo, así que apuntar bien lo hace efectivo al
    100 %. Lo que se evalúa es si las celdas cortadas pagan el costo.
    """

    def __init__(self):
        """Empieza sin disparos hechos."""
        self.shots = {}

    def record(self, game_id):
        """Anota un disparo en la partida."""
        self.shots[game_id] = self.shots.get(game_id, 0) + 1

    @staticmethod
    def limits(state):
        """``(máx. disparos, retorno mínimo)``; más agresivo si vamos atrás."""
        behind = state['rival_score'] - state['score']
        if behind >= SHOT_BEHIND_GAP:
            return MAX_SHOTS_WHEN_BEHIND, SHOT_MIN_RETURN_WHEN_BEHIND
        return MAX_SHOTS_PER_GAME, SHOT_MIN_RETURN

    def _allowed(self, state, max_shots):
        """Condiciones generales: interruptor, saldo, tiempo y ventaja."""
        checks = (
            SHOOTING_ENABLED,
            self.shots.get(state['game_id'], 0) < max_shots,
            state['score'] - SHOT_COST >= SHOT_MIN_SCORE_LEFT,
            state['own_moves_left'] >= SHOT_MIN_OWN_MOVES_LEFT,
            state['score'] - state['rival_score'] <= SHOT_LEAD_LIMIT,
        )
        return all(checks)

    @staticmethod
    def swing(ours, rivals, multipliers):
        """Puntos que ganamos de más que el rival con las celdas cortadas."""
        mine, theirs = multipliers
        return 100 * (ours * mine - rivals * theirs)

    @staticmethod
    def worth_it(swing, min_return=SHOT_MIN_RETURN):
        """True si la ventaja esperada paga el disparo (con margen)."""
        return swing >= SHOT_COST * min_return

    def _shot_options(self, board, head, opp, multipliers):
        """``(ventaja, es a la cabeza, dirección)`` de cada tiro posible."""
        options = []
        rival_head = board.find(opp.head)
        for name in DIRS:
            hit = ray_hit(board, head, name, opp)
            if hit:
                cells = cut_list(board, opp, hit)
                ours, rivals = race_counts(board, head, opp, cells)
                value = self.swing(ours, rivals, multipliers)
                options.append((value, hit == rival_head, name))
        return options

    def best_direction(self, board, head, opp, multipliers, min_return):
        """Mejor tiro (más ventaja, cabeza si empatan) o ``None``."""
        options = self._shot_options(board, head, opp, multipliers)
        if not options:
            return None
        value, _, name = max(options)
        return name if self.worth_it(value, min_return) else None

    def decide(self, board, head, opp, state):
        """Dirección de disparo o ``None``.

        ``state`` trae ``game_id``, ``score``, ``rival_score``,
        ``own_moves_left``, ``multiplier`` y ``rival_multiplier``.
        """
        max_shots, min_return = self.limits(state)
        if not self._allowed(state, max_shots):
            return None
        multipliers = (state['multiplier'], state['rival_multiplier'])
        return self.best_direction(board, head, opp, multipliers, min_return)
