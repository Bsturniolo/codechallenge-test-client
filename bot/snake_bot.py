"""Bot que convierte un turno del servidor en un movimiento."""

from random import choice

from bot.board import Board
from bot.constants import DIRS, STARTING_DIGIT, WALL_CHAR
from bot.planner import MovePlanner, Side, opposite
from bot.protocol import send


class SnakeBot:
    """Resuelve cada ``your_turn`` y manda la dirección elegida."""

    def __init__(self, logger):
        """Recibe el ``GameLogger`` donde se anotan las acciones."""
        self.logger = logger

    @staticmethod
    def multipliers(data):
        """Multiplicadores ``(propio, rival)`` según nuestro lado (v4)."""
        mine, theirs = 'multiplier_1', 'multiplier_2'
        if data['side'] != 'A':
            mine, theirs = theirs, mine
        return data.get(mine), data.get(theirs)

    @staticmethod
    def random_direction():
        """Dirección al azar, solo si no hay ninguna decisión posible."""
        return choice(list(DIRS))

    def build_planner(self, board, head, data):
        """Arma el ``MovePlanner`` del turno a partir de los datos.

        El dígito objetivo se lee del tablero original; después se marca
        la zona de explosión de las bombas (v8) para que el planificador
        las evite.
        """
        own = Side.from_letter(data['side'])
        opp = Side.from_letter(opposite(data['side']))
        mine, theirs = self.multipliers(data)
        if mine is not None:
            print('multiplier: us={} rival={}'.format(mine, theirs))
        target = board.target_digit() or STARTING_DIGIT
        keep = {own.head, own.body, opp.head, opp.body, WALL_CHAR}
        return MovePlanner(board.mark_danger(keep), head, own, opp, target,
                           mine or 1, data.get('remaining_moves'))

    def decide(self, data):
        """Elige la dirección para los datos de un turno."""
        print(data['board'])
        board = Board.from_string(data['board'])
        head = board.find(data['side'])
        if head is None:
            return self.random_direction()
        planner = self.build_planner(board, head, data)
        return planner.choose()[0] or self.random_direction()

    async def handle_turn(self, websocket, request_data):
        """Decide y envía el movimiento del turno."""
        data = request_data['data']
        move = {
            'game_id': data['game_id'],
            'turn_token': data['turn_token'],
            'direction': self.decide(data),
        }
        self.logger.log_action(
            move['game_id'], {'action': 'move', 'data': move})
        await send(websocket, 'move', move)
