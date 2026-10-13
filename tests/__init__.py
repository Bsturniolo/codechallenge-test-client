"""Tests del bot.

Si ``websockets`` no está instalado se reemplaza por un módulo falso, así
los tests corren sin red ni dependencias externas.
"""

import sys
import types

if 'websockets' not in sys.modules:
    sys.modules['websockets'] = types.ModuleType('websockets')
if not hasattr(sys.modules['websockets'], 'connect'):
    sys.modules['websockets'].connect = lambda *args, **kwargs: None
