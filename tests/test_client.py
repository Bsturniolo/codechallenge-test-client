"""Tests de ``GameClient`` (conexión y bucle de mensajes) y ``main``."""

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import run
from bot.client import GameClient
from tests.helpers import quiet, turn


def fake_socket(messages):
    """WebSocket falso que entrega ``messages`` y registra lo enviado."""
    websocket = MagicMock()
    websocket.send = AsyncMock()
    websocket.recv = AsyncMock(side_effect=messages)
    return websocket


class TestPlayLoop(unittest.TestCase):
    """Despacho de eventos del servidor."""

    def setUp(self):
        self.client = GameClient('token')
        self.cwd = os.getcwd()
        os.chdir(tempfile.mkdtemp())

    def tearDown(self):
        os.chdir(self.cwd)

    def _play(self, messages):
        websocket = fake_socket(messages)
        with quiet():
            asyncio.run(self.client.play(websocket))
        return websocket

    def test_challenge_is_accepted(self):
        message = json.dumps({'event': 'challenge', 'data': {
            'challenge_id': 'c1', 'opponent': 'x'}})
        websocket = self._play([message, Exception('closed')])
        sent = json.loads(websocket.send.call_args[0][0])
        self.assertEqual(sent['action'], 'accept_challenge')

    def test_your_turn_sends_a_move(self):
        message = json.dumps(turn('A'))
        websocket = self._play([message, Exception('closed')])
        self.assertEqual(
            json.loads(websocket.send.call_args[0][0])['action'], 'move')

    def test_game_over_writes_log(self):
        message = json.dumps({'event': 'game_over',
                              'data': {'game_id': 'gz'}})
        self._play([message, Exception('closed')])
        path = os.path.join('partidas', 'game_gz.log')
        self.assertTrue(os.path.exists(path))

    def test_game_over_without_game_id(self):
        message = json.dumps({'event': 'game_over', 'data': {}})
        self._play([message, Exception('closed')])
        self.assertEqual(self.client.logger.history, {})

    def test_other_events_are_ignored(self):
        message = json.dumps({'event': 'update_user_list', 'data': {}})
        websocket = self._play([message, Exception('closed')])
        websocket.send.assert_not_called()

    def test_bad_message_does_not_drop_connection(self):
        websocket = self._play(
            ['not json', json.dumps(turn('A')), Exception('closed')])
        self.assertEqual(websocket.send.call_count, 1)

    def test_keyboard_interrupt_on_recv(self):
        self._play([KeyboardInterrupt()])

    def test_keyboard_interrupt_while_handling(self):
        message = json.dumps(turn('A'))
        handler = AsyncMock(side_effect=KeyboardInterrupt())
        with patch.object(self.client.bot, 'handle_turn', handler):
            websocket = self._play([message])
        self.assertEqual(websocket.recv.await_count, 1)


class FakeConnection:
    """Reemplaza ``websockets.connect(uri)`` como context manager."""

    def __init__(self, on_enter):
        self.on_enter = on_enter

    async def __aenter__(self):
        return await self.on_enter()

    async def __aexit__(self, *args):
        return False


async def stop_after_connect(self, websocket):
    """Reemplazo de ``play`` que corta el bucle de reconexión."""
    raise KeyboardInterrupt()


class TestStart(unittest.TestCase):
    """Conexión y reconexión."""

    def test_connects_to_current_server(self):
        seen = []

        async def enter():
            return 'ws'

        def connect(uri):
            seen.append(uri)
            return FakeConnection(enter)

        with patch('bot.client.websockets.connect', connect), \
                patch.object(GameClient, 'play', stop_after_connect), \
                quiet():
            asyncio.run(GameClient('tok').start())
        self.assertEqual(
            seen, ['wss://server.codechallenge.net.ar/ws?token=tok'])

    def test_connection_error_retries(self):
        state = {'calls': 0}

        async def enter():
            state['calls'] += 1
            if state['calls'] == 1:
                raise OSError('down')
            return 'ws'

        with patch('bot.client.websockets.connect',
                   lambda uri: FakeConnection(enter)), \
                patch.object(GameClient, 'play', stop_after_connect), \
                patch('bot.client.time.sleep') as sleep, quiet():
            asyncio.run(GameClient('tok').start())
        sleep.assert_called_once_with(3)
        self.assertEqual(state['calls'], 2)


class TestMain(unittest.TestCase):
    """Punto de entrada ``run.main``."""

    def test_without_token_prints_message(self):
        with patch('run.asyncio.run') as runner, patch('builtins.print') \
                as printer:
            run.main(['run.py'])
        runner.assert_not_called()
        printer.assert_called_once_with('please provide your auth_token')

    def test_with_token_starts_client(self):
        with patch('run.asyncio.run') as runner, \
                patch('run.GameClient') as client_class:
            run.main(['run.py', 'abc'])
        client_class.assert_called_once_with('abc')
        runner.assert_called_once()


if __name__ == '__main__':
    unittest.main()
