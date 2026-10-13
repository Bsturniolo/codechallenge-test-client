"""Tests de ``GameLogger``."""

import contextlib
import io
import os
import tempfile
import unittest
from unittest.mock import patch

from bot.logger import GameLogger
from tests.helpers import quiet


class TestGameLogger(unittest.TestCase):
    """Registro de eventos y escritura de ``game_<id>.log``."""

    def setUp(self):
        self.logger = GameLogger()
        self.cwd = os.getcwd()
        os.chdir(tempfile.mkdtemp())

    def tearDown(self):
        os.chdir(self.cwd)

    def test_log_event_and_action(self):
        self.logger.log_event('g1', {'a': 1})
        self.logger.log_action('g1', {'b': 2})
        self.assertEqual(self.logger.history['g1'],
                         ['< {"a": 1}', '> {"b": 2}'])

    def test_write_creates_file(self):
        self.logger.log_event('g2', {'x': 1})
        with quiet():
            self.logger.write('g2')
        with open('game_g2.log') as handle:
            self.assertIn('< {"x": 1}', handle.read())

    def test_write_handles_oserror(self):
        buffer = io.StringIO()
        with patch('builtins.open', side_effect=OSError('boom')):
            with contextlib.redirect_stdout(buffer):
                self.logger.write('g3')
        self.assertIn('could not write game log', buffer.getvalue())


if __name__ == '__main__':
    unittest.main()
