# 🐍 Snake Challenge Bot

Bot en Python que juega automáticamente al desafío de Snake multijugador vía WebSocket, para la actividad de la facultad.

## ¿Qué hace?

Se conecta al servidor del challenge, acepta desafíos automáticamente, y en cada turno decide su movimiento (`up`/`down`/`left`/`right`) usando una estrategia con tres capas:

1. **Busca comida de forma inteligente**: evalúa varias de las manzanas más cercanas (no solo la primera que encuentra) y descarta las que están en zonas peligrosas.
2. **Evita quedarse encerrado**: antes de moverse, calcula (con flood-fill) si el espacio disponible detrás de ese paso alcanza para el largo de su propio cuerpo. Si no alcanza, descarta esa opción.
3. **Controla territorio**: compara, celda por celda, quién del tablero (nosotros o el rival) llega primero a cada zona libre (heurística tipo Voronoi), y prioriza los movimientos que dejan más espacio bajo nuestro control — esto lo hace jugar mejor a largo plazo, no solo perseguir la comida más cercana.
4. **Esquiva choques de cabeza**: si el rival es igual o más largo y está a un paso de distancia, evita esa celda.

## Archivos

| Archivo | Qué es |
|---|---|
| `run.py` | El bot. Se conecta al servidor y juega. |
| `test_run.py` | Suite de tests offline (no se conecta a nada) que verifica la lógica de decisión contra tableros armados a mano. |

## Requisitos

- Python 3.10+
- [`websockets`](https://pypi.org/project/websockets/)

```bash
pip install websockets
```

## Uso

```bash
python3 run.py <tu_auth_token>
```

El bot se conecta, acepta cualquier desafío que le llegue, y juega solo. Al terminar cada partida guarda un log completo (eventos recibidos y jugadas mandadas) en `game_<game_id>.log`, útil para revisar qué pasó turno a turno.

### Servidor

```
wss://server.codechallenge.net.ar/ws?token=<auth_token>
```

Si esta URL cambia (la cátedra a veces migra el servidor), actualizala en la variable `uri` dentro de `start()` en `run.py`.

## Tests

`test_run.py` corre offline: prueba las funciones de decisión (parseo del tablero, detección de callejones sin salida, cálculo de territorio, etc.) contra tableros de ejemplo, sin necesidad de conexión.

```bash
python3 test_run.py
```

Salida esperada:

```
Ran 10 tests in 0.00Xs

OK
```

Si algo falla, el traceback indica exactamente qué escenario no se comporta como se espera — útil para revisar antes de arriesgar puntos en una partida real.

## Protocolo (formato de mensajes)

El tablero llega como un string con `|` en los bordes de cada fila:

```
|*              |
|aaA            |
|               |
```

| Símbolo | Significado |
|---|---|
| `A` / `a` | Cabeza / cuerpo de **nuestra** serpiente |
| `B` / `b` | Cabeza / cuerpo de la serpiente **rival** |
| `*` | Comida |
| ` ` | Celda vacía |

El movimiento se manda como:

```json
{
  "action": "move",
  "data": {
    "game_id": "...",
    "turn_token": "...",
    "direction": "up"
  }
}
```

> **Nota:** el campo `direction` con valores `up`/`down`/`left`/`right` es la convención que confirmamos funcionando en partidas reales del challenge.

## Posibles mejoras futuras

- Simulación de varios turnos hacia adelante (lookahead) en vez de solo el siguiente paso.
- Estrategia agresiva: cortarle el paso al rival en vez de solo evitarlo.
- Ajustar heurísticas según el tamaño del tablero o la cantidad de comida disponible.

## Créditos

Armado para la actividad de programación de bots de la facultad. Estrategia y tests desarrollados iterativamente probando contra partidas reales del challenge.