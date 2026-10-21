"""Disparos (v9): cuándo vale la pena gastar 5000 puntos en cortar al rival."""

from bot.constants import (
    DIRS, MAX_SHOTS_PER_GAME, SHOOTING_ENABLED, SHOT_COST,
    SHOT_LEAD_LIMIT, SHOT_MIN_OWN_MOVES_LEFT, SHOT_MIN_RETURN,
    SHOT_MIN_SCORE_LEFT, SHOT_RECOVERY_SHARE, WALL_CHAR)


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


def cut_cells(board, opp, hit):
    """Cuántas celdas del rival se cortan si el disparo pega en ``hit``."""
    chain = snake_chain(board, opp)
    if chain is None or hit not in chain:
        return 0
    index = chain.index(hit)
    return len(chain) - 1 if index == 0 else len(chain) - index


class Shooter:
    """Decide si disparar; como mucho ``MAX_SHOTS_PER_GAME`` por partida."""

    def __init__(self):
        """Empieza sin disparos hechos."""
        self.shots = {}

    def record(self, game_id):
        """Anota un disparo en la partida."""
        self.shots[game_id] = self.shots.get(game_id, 0) + 1

    def _allowed(self, game_id, score, rival_score, own_moves_left):
        """Condiciones generales: interruptor, saldo, tiempo y ventaja."""
        checks = (
            SHOOTING_ENABLED,
            self.shots.get(game_id, 0) < MAX_SHOTS_PER_GAME,
            score - SHOT_COST >= SHOT_MIN_SCORE_LEFT,
            own_moves_left >= SHOT_MIN_OWN_MOVES_LEFT,
            score - rival_score <= SHOT_LEAD_LIMIT,
        )
        return all(checks)

    @staticmethod
    def worth_it(cells, multiplier):
        """True si lo que se espera recuperar paga el disparo."""
        gain = cells * 100 * multiplier * SHOT_RECOVERY_SHARE
        return gain >= SHOT_COST * SHOT_MIN_RETURN

    def best_direction(self, board, head, opp, multiplier):
        """Dirección que más celdas corta y paga el disparo, o ``None``."""
        best, best_cells = None, 0
        for name in DIRS:
            hit = ray_hit(board, head, name, opp)
            cells = cut_cells(board, opp, hit) if hit else 0
            if cells > best_cells and self.worth_it(cells, multiplier):
                best, best_cells = name, cells
        return best

    def decide(self, board, head, opp, state):
        """Dirección de disparo o ``None``.

        ``state`` trae ``game_id``, ``score``, ``rival_score``,
        ``own_moves_left`` y ``multiplier``.
        """
        if not self._allowed(state['game_id'], state['score'],
                             state['rival_score'], state['own_moves_left']):
            return None
        return self.best_direction(board, head, opp, state['multiplier'])
