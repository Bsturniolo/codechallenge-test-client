"""Punto de entrada: ``python3 run.py <auth_token>``."""

import asyncio
import sys

from bot.client import GameClient


def main(argv):
    """Arranca el cliente si se pasó el token de autenticación."""
    if len(argv) < 2:
        print('please provide your auth_token')
        return
    asyncio.run(GameClient(argv[1]).start())


if __name__ == '__main__':
    main(sys.argv)
