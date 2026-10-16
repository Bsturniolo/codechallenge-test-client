# 🐍 Snake Challenge Bot

![Lint](https://github.com/Bsturniolo/codechallenge-test-client/actions/workflows/lint.yml/badge.svg)
![Tests](https://github.com/Bsturniolo/codechallenge-test-client/actions/workflows/tests.yml/badge.svg)
![Complejidad](https://github.com/Bsturniolo/codechallenge-test-client/actions/workflows/complexity.yml/badge.svg)
[![Cobertura](https://raw.githubusercontent.com/Bsturniolo/codechallenge-test-client/python-coverage-comment-action-data/badge.svg)](https://github.com/Bsturniolo/codechallenge-test-client/tree/python-coverage-comment-action-data)

Bot en Python que juega automáticamente al Snake multijugador del
CodeChallenge (Computación II – 2026) por WebSocket.

## Cómo ejecutarlo

Requiere Python 3.10+.

```bash
pip install -r requirements.txt
python3 run.py <tu_auth_token>
```

También se puede usar `./start.sh <tu_auth_token>`, que instala
`websockets` si falta y lanza el bot. El bot acepta cualquier desafío que
le llegue, juega solo y al terminar cada partida guarda
`partidas/game_<game_id>.log` (la carpeta se crea sola) con los eventos
recibidos (`<`) y las jugadas
enviadas (`>`).

Servidor: `wss://server.codechallenge.net.ar/ws?token=<auth_token>`
(constante `SERVER_URI` en `bot/constants.py`). Un `HTTP 404` al
conectar suele indicar que la cátedra cambió la URL.

## Estructura del proyecto

```
run.py                 Punto de entrada (python3 run.py <token>)
bot/
  constants.py         Constantes de reglas y estrategia
  board.py             Board: tablero y búsquedas (BFS, flood fill, territorio)
  planner.py           Side y MovePlanner: la estrategia de movimiento
  snake_bot.py         SnakeBot: convierte un turno del servidor en una jugada
  client.py            GameClient: conexión, reconexión y eventos
  logger.py            GameLogger: logs por partida
  protocol.py          send(): envío de mensajes
tests/                 Tests unittest (+ tests/data con partidas reales)
.github/workflows/     CI: lint.yml, tests.yml, complexity.yml
```

### Clases principales

| Clase | Responsabilidad |
|---|---|
| `Board` | Parsea el tablero y responde preguntas sobre él: dónde está algo, caminos más cortos, espacio libre, territorio y dígito objetivo. |
| `Side` | Letras de una serpiente (cabeza, cuerpo) y su comida de cola. |
| `MovePlanner` | Decide la dirección del turno aplicando la estrategia por prioridades. |
| `SnakeBot` | Arma el planificador con los datos de `your_turn` y envía la jugada. |
| `GameClient` | Maneja la conexión WebSocket, acepta desafíos y despacha eventos. |
| `GameLogger` | Guarda eventos y acciones de cada partida. |

## Estrategia

`MovePlanner.choose()` prueba estos pasos en orden y usa el primero que
da una jugada:

1. **Acumular multiplicador (v4):** mientras el multiplicador propio sea
   menor a `MULTIPLIER_ACCUMULATION_CAP` (16) y queden suficientes
   movimientos, va por una `X` segura, pero solo si el camino cuesta menos
   de `movimientos propios restantes * MULTIPLIER_BUDGET_FACTOR / multiplicador`
   pasos, y además solo si rinde más puntos por paso que comer el dígito
   objetivo (un 8 o 9 con multiplicador alto se come antes que una `X`
   lejana).
2. **Comida de cola propia (v7):** `Ⓐ`/`Ⓑ` de nuestra letra a 2 pasos o
   menos.
3. **Dígito correcto:** evalúa las 4 direcciones, descarta las que
   terminan en un callejón sin salida (chequeo de varios pasos) y prefiere
   rutas que el rival no pueda disputar. Con varias copias (v6) va a la más
   cercana.
4. **`X` o comida de cola** si el dígito no es alcanzable con seguridad.
5. **Territorio:** entre los pasos que controlan casi tantas celdas como el
   mejor (`TERRITORY_TOLERANCE`), el que queda más cerca del dígito objetivo.
6. **Último recurso:** el paso menos costoso (celda libre, dígito
   incorrecto, zona de bomba, cabeza rival, pared, cuerpo) y, a igual
   costo, el que deja más espacio libre.

Siempre evita dígitos incorrectos, cuerpos, la pared `#`, y no se acerca a
la cabeza del rival si este es estrictamente más largo.

**Bombas (v8):** `Board.mark_danger()` marca como prohibidas todas las celdas
dentro de la zona de explosión de alguna bomba. Como cada celda de un camino
es el final de un movimiento, el bot no pisa ninguna celda de la zona, ni en
el destino ni de paso. Como el juego nunca pone comida dentro de una zona, evitarlas no
cuesta puntos. Solo si no queda otra opción, el último recurso pisa la zona de una bomba
(antes que la cabeza rival, la pared o un cuerpo).

## Tests

```bash
python3 -m unittest discover
```

Cobertura (mínimo exigido: 90 %; configuración en `.coveragerc`):

```bash
pip install -r requirements-dev.txt
coverage run -m unittest discover
coverage report -m --fail-under=90
```

Los tests de `tests/test_regression.py` reproducen partidas reales de
torneo (`tests/data/*.json`) para verificar la lectura del dígito objetivo.

## Integración continua y calidad

Cada push a `main` y cada pull request ejecutan en GitHub Actions:

| Workflow | Qué verifica |
|---|---|
| `lint.yml` | `flake8 .` (configuración en `setup.cfg`) |
| `tests.yml` | `coverage run -m unittest discover`, `coverage report --fail-under=90` y comentario/badge de cobertura |
| `complexity.yml` | `xenon --max-absolute A --max-modules A --max-average A bot run.py` |

Para correrlos localmente:

```bash
flake8 .
xenon --max-absolute A --max-modules A --max-average A bot run.py
```

## Reglas del juego (resumen)

| Versión | Fecha | Cambio |
|---|---|---|
| v1 | — | Tablero fijo 15×15, comida `*`. |
| v2 | 2 sep 2026 | Tamaño de tablero variable (12–20 por lado). El bot deriva filas y columnas del propio tablero. |
| v3 | 9 sep 2026 | Comida numérica `1`-`9` en orden cíclico. Correcto: `dígito × 100`; incorrecto: −500. El objetivo es el dígito presente cuyo predecesor cíclico no está. |
| v4 | 16 sep 2026 | `X`: +50 y multiplicador permanente por jugador (`multiplier_1/2`). |
| v5 | 23 sep 2026 | Pared `#` (línea de hasta 11 celdas que se achica). Chocarla: −500 y no se mueve. |
| v6 | 30 sep 2026 | Cada dígito aparece en 3–5 copias; solo una copia da puntos. |
| v7 | 7 oct 2026 | Partidas de 400 movimientos. Chocar ya no termina la partida: la serpiente no se mueve, conserva 3 celdas y suelta comida de cola `Ⓐ`/`Ⓑ` para el rival. Primer choque: puntaje a 0; luego −500; bajo −2500 se pierde. |
| v8 | 14 oct 2026 | Bombas `💣` (zona 5×5) y `🧨` (zona 3×3): explotan si la cabeza termina un movimiento a distancia Chebyshev ≤ 2 (`💣`) o ≤ 1 (`🧨`). La explosión deja el puntaje en 0 (o −500 si ya era ≤ 0), pero el movimiento se hace igual. Nunca hay comida ni `X` dentro de una zona. Tras la ronda 150 desaparecen todas las bombas. Tableros de 20 a 30 por lado. |

## Protocolo

El tablero llega como string con `|` en los bordes de cada fila:

| Símbolo | Significado |
|---|---|
| `A` / `a` | Cabeza / cuerpo de la serpiente A |
| `B` / `b` | Cabeza / cuerpo de la serpiente B |
| `1`-`9` | Comida numérica (solo el dígito objetivo suma) |
| `X` | Multiplicador permanente |
| `#` | Pared |
| `Ⓐ` / `Ⓑ` | Comida de cola (solo la come la serpiente de esa letra) |
| `💣` / `🧨` | Bomba grande / chica (desde v8): explota si la cabeza termina cerca |

Movimiento:

```json
{"action": "move",
 "data": {"game_id": "...", "turn_token": "...", "direction": "up"}}
```

## Mejoras posibles

- Comparar copias del dígito objetivo por seguridad y no solo por cercanía.
- Pisar a propósito la comida de cola del rival para negársela (v7).
- Calibrar los umbrales de acumulación para partidas de 400 movimientos.
- Simular varios turnos del rival en lugar de estimar solo su distancia.
