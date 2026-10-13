"""Cliente WebSocket: conexión, reconexión y despacho de eventos."""

import json
import time

import websockets

from bot.constants import RECONNECT_DELAY_SECONDS, SERVER_URI
from bot.logger import GameLogger
from bot.protocol import send
from bot.snake_bot import SnakeBot


class GameClient:
    """Se conecta al servidor, acepta desafíos y juega los turnos."""

    def __init__(self, auth_token, logger=None, bot=None):
        """Guarda el token y arma el logger y el bot si no se pasan."""
        self.auth_token = auth_token
        self.logger = logger or GameLogger()
        self.bot = bot or SnakeBot(self.logger)

    async def start(self):
        """Conecta y reconecta indefinidamente hasta Ctrl+C."""
        uri = SERVER_URI.format(self.auth_token)
        while True:
            try:
                print('connection to {}'.format(uri))
                async with websockets.connect(uri) as websocket:
                    print('connection READY!')
                    await self.play(websocket)
            except KeyboardInterrupt:
                print('Exiting...')
                break
            except Exception:
                print('connection error!')
                time.sleep(RECONNECT_DELAY_SECONDS)

    async def play(self, websocket):
        """Procesa mensajes hasta que se corta la conexión."""
        while True:
            request = await self._receive(websocket)
            if request is None:
                break
            if not await self._process(websocket, request):
                break

    @staticmethod
    async def _receive(websocket):
        """Próximo mensaje crudo, o ``None`` si hay que cortar el bucle."""
        try:
            return await websocket.recv()
        except KeyboardInterrupt:
            print('Exiting...')
        except Exception as error:
            print('connection lost: {}'.format(error))
        return None

    async def _process(self, websocket, request):
        """Procesa un mensaje. Devuelve ``False`` si hay que salir.

        Un mensaje inesperado se informa pero no corta la partida:
        perder la conexión implica perder todos los turnos siguientes.
        """
        print("< {}".format(request))
        try:
            await self._dispatch(websocket, json.loads(request))
        except KeyboardInterrupt:
            print('Exiting...')
            return False
        except Exception as error:
            print('error handling message: {}'.format(error))
        return True

    async def _dispatch(self, websocket, request_data):
        """Llama al manejador del evento (los desconocidos se ignoran)."""
        handlers = {
            'game_over': self._on_game_over,
            'challenge': self._on_challenge,
            'your_turn': self._on_your_turn,
        }
        handler = handlers.get(request_data['event'])
        if handler:
            await handler(websocket, request_data)

    async def _on_game_over(self, websocket, request_data):
        """Guarda el log de la partida terminada."""
        game_id = request_data['data'].get('game_id')
        if game_id:
            self.logger.log_event(game_id, request_data)
            self.logger.write(game_id)

    async def _on_challenge(self, websocket, request_data):
        """Acepta cualquier desafío."""
        challenge_id = request_data['data']['challenge_id']
        await send(websocket, 'accept_challenge',
                   {'challenge_id': challenge_id})

    async def _on_your_turn(self, websocket, request_data):
        """Registra el turno y manda el movimiento."""
        self.logger.log_event(request_data['data']['game_id'], request_data)
        await self.bot.handle_turn(websocket, request_data)
