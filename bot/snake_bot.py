"""Bot que convierte un turno del servidor en un movimiento."""

from random import choice

from bot.board import Board
from bot.constants import DIRS, STARTING_DIGIT, WALL_CHAR
from bot.planner import MovePlanner, Side, opposite
from bot.protocol import send
from bot.shooter import Shooter


class SnakeBot:
    """Resuelve cada ``your_turn`` y manda la dirección elegida."""

    def __init__(self, logger):
        """Recibe el ``GameLogger`` donde se anotan las acciones."""
        self.logger = logger
        self.shooter = Shooter()

    @staticmethod
    def multipliers(data):
        """Multiplicadores ``(propio, rival)`` según nuestro lado (v4)."""
        mine, theirs = 'multiplier_1', 'multiplier_2'
        if data['side'] != 'A':
            mine, theirs = theirs, mine
        return data.get(mine), data.get(theirs)

    @staticmethod
    def own_score(data):
        """Puntaje propio según nuestro lado (0 si no viene)."""
        key = 'score_1' if data['side'] == 'A' else 'score_2'
        return data.get(key) or 0

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
                           mine or 1, data.get('remaining_moves'),
                           self.own_score(data))

    def _plan(self, data):
        """Dirección elegida por el planner para los datos de un turno."""
        print(data['board'])
        board = Board.from_string(data['board'])
        head = board.find(data['side'])
        if head is None:
            return self.random_direction()
        planner = self.build_planner(board, head, data)
        return planner.choose()[0] or self.random_direction()

    def decide(self, data):
        """Elige la dirección; ante cualquier error juega al azar.

        Un fallo inesperado (por ejemplo un carácter nuevo en el tablero
        tras una regla nueva) no debe hacer perder el turno ni cortar la
        partida.
        """
        try:
            return self._plan(data)
        except Exception as error:
            print('error al decidir, se juega al azar: {!r}'.format(error))
            return self.random_direction()

    @staticmethod
    def _number(data, key, default=0):
        """Valor numérico de ``data[key]`` o ``default`` si falta."""
        return data.get(key) or default

    def shot_state(self, data):
        """Datos del turno que usa el ``Shooter``, según nuestro lado."""
        mine, theirs = 'score_1', 'score_2'
        if data['side'] != 'A':
            mine, theirs = theirs, mine
        return {
            'game_id': data['game_id'],
            'score': self._number(data, mine),
            'rival_score': self._number(data, theirs),
            'own_moves_left': self._number(data, 'remaining_moves') // 2,
            'multiplier': self.multipliers(data)[0] or 1,
            'rival_multiplier': self.multipliers(data)[1] or 1,
        }

    def shot_direction(self, data):
        """Dirección de disparo (v9) o ``None``; nunca lanza excepciones."""
        try:
            board = Board.from_string(data['board'])
            head = board.find(data['side'])
            if head is None:
                return None
            opp = Side.from_letter(opposite(data['side']))
            return self.shooter.decide(
                board, head, opp, self.shot_state(data))
        except Exception as error:
            print('error al evaluar el disparo: {!r}'.format(error))
            return None

    async def _send_action(self, websocket, action, data, direction):
        """Registra y envía un ``move`` o ``shoot`` con su dirección."""
        message = {
            'game_id': data['game_id'],
            'turn_token': data['turn_token'],
            'direction': direction,
        }
        self.logger.log_action(
            message['game_id'], {'action': action, 'data': message})
        await send(websocket, action, message)

    async def handle_turn(self, websocket, request_data):
        """Dispara si conviene; si no, decide y envía el movimiento."""
        data = request_data['data']
        shot = self.shot_direction(data)
        if shot:
            self.shooter.record(data['game_id'])
            await self._send_action(websocket, 'shoot', data, shot)
            return
        await self._send_action(
            websocket, 'move', data, self.decide(data))
