"""Envío de mensajes al servidor."""

import json


async def send(websocket, action, data):
    """Serializa y envía ``{"action": ..., "data": ...}``."""
    message = json.dumps({'action': action, 'data': data})
    print(message)
    await websocket.send(message)
