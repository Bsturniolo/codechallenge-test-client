# 🐍 Snake Challenge Bot

Bot en Python que juega automáticamente al desafío de Snake multijugador vía WebSocket, para la actividad de la facultad.

## ¿Qué hace?

Se conecta al servidor del challenge, acepta desafíos automáticamente, y en cada turno decide su movimiento (`up`/`down`/`left`/`right`). La estrategia, en orden de prioridad:

1. **Va por el dígito correcto de la secuencia** (ver [Reglas del juego](#reglas-del-juego-resumen) abajo), evaluando las 4 direcciones inmediatas que lleven hacia él y descartando las que terminan en una trampa, usando un chequeo de seguridad de **varios pasos hacia adelante** (no solo el siguiente casillero) para detectar si nos estamos por enroscar solos en una esquina. Además, si el rival puede llegar a esa misma celda **antes o al mismo tiempo que nosotros**, la tratamos como "disputada" y preferimos otra ruta si hay una libre — eso es justo lo que nos dejó encerrados en una partida real: el destino tenía espacio de sobra, pero el rival llegó primero y nos cerró el paso.
2. Si el dígito correcto no está en el tablero todavía, o no se puede llegar con seguridad: **va a buscar una `X`** (multiplicador permanente) si hay una alcanzable — es ganancia gratis, ya que de todos modos no íbamos a comer nada ese turno.
3. Si tampoco hay una `X` segura: **maximiza territorio** (heurística tipo Voronoi) comparando, celda por celda, quién llega primero — nosotros o el rival — para sobrevivir el mayor tiempo posible y quedar mejor posicionado.
4. En cualquiera de los pasos anteriores, **evita meterse al lado de la cabeza del rival** si es estrictamente más largo que nosotros (un choque que perderíamos seguro). Si es igual o más corto, no se desvía por eso — la velocidad importa más que una cautela excesiva en un juego que es, en el fondo, una carrera.
5. Como último recurso, si está completamente acorralado, igual manda un movimiento legal en vez de trabarse.

## Archivos

| Archivo | Qué es |
|---|---|
| `run.py` | El bot. Se conecta al servidor y juega. |
| `test_run.py` | Suite de tests offline (no se conecta a nada) que verifica la lógica de decisión contra tableros armados a mano, y contra un replay de una partida real. |

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

Si esta URL cambia (la cátedra a veces migra el servidor), actualizala en la variable `uri` dentro de `start()` en `run.py`. Un error `HTTP 404` al conectar (`InvalidStatusCode`) es la señal de que esto pasó — no es un bug del bot.

## Tests

`test_run.py` corre offline: prueba las funciones de decisión (parseo del tablero, detección de callejones sin salida, tracking de la secuencia de dígitos, manejo de la `X`, etc.) contra tableros y datos de ejemplo, sin necesidad de conexión.

```bash
python3 test_run.py
```

Salida esperada:

```
Ran 26 tests in 0.0Xs

OK
```

Uno de los tests (`test_replays_real_match_log_and_tracks_correctly`) reproduce el `score_1`/`score_2` real de una partida jugada en torneo para confirmar que el tracker de la secuencia de dígitos se mantiene sincronizado turno a turno — es la mejor defensa contra que se rompa de nuevo silenciosamente.

## Reglas del juego (resumen)

El juego fue cambiando de versión con el tiempo. Esto es lo que sabemos confirmado de cada una:

- **v1** (tablero fijo 15×15): comida = `*`, cualquiera vale.
- **v2** (2 sep 2026): el tablero varía de tamaño por partida (12–20 por lado, no necesariamente cuadrado). El bot **no depende de ningún campo del mensaje** para esto — calcula filas/columnas directo del tablero recibido, así que es inmune a que cambien el nombre del campo.
- **v3** (9 sep 2026): la comida son dígitos `1`-`9`. Hay que comerlos en orden ascendente cíclico (`...7,8,9,1,2...`). El dígito correcto suma `dígito × 100`; cualquier otro dígito resta 500.
  - ⚠️ **Importante, confirmado con partidas reales**: la secuencia es **global**, compartida entre los dos jugadores — no es "tu propio contador". Si el rival come el dígito correcto, la secuencia avanza igual que si lo hubiéramos comido nosotros. El bot sincroniza su propio contador mirando `score_1` y `score_2` (que vienen en todos los mensajes) en vez de asumir que solo nuestras propias comidas cuentan.
- **v4** (16 sep 2026): se suman dos celdas `X` al tablero. Comer una da +50 (fijo, no se multiplica) y sube un multiplicador permanente (x2, x3, x4...) que escala los puntos de comida (`dígito × 100 × multiplicador`). Cada jugador tiene su propio multiplicador. La `X` es segura para pisar (no choca, no hace crecer) y **no hace falta tratarla como obstáculo**. Los valores de multiplicador vienen en los campos `multiplier_1`/`multiplier_2` de `turn_data` (es el único dato de esta regla que no se puede leer directo del tablero).

Si la cátedra anuncia una v5 o cambia algo de esto, lo mejor es pasarle a Claude el anuncio de la regla tal cual (copiado, no resumido) y el primer log de una partida jugada con la regla nueva — así se puede confirmar el comportamiento real en vez de adivinar.

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
| `1`-`9` | Comida (desde v3) — solo el dígito correcto de la secuencia suma puntos |
| `X` | Multiplicador permanente (desde v4) — siempre segura para pisar |
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

- Elegir entre **varias ocurrencias** del mismo dígito objetivo (si hay dos '5' en el tablero a la vez) prefiriendo la más segura, no solo evaluar rutas hacia la más cercana. Hoy el chequeo de "carrera disputada" funciona bien cuando hay una sola instancia del dígito, pero no compara instancias distintas entre sí.
- Simular varios turnos del rival de forma más completa (no solo "cuántos pasos le toma llegar a esta celda", sino su comportamiento probable turno a turno).
- Estrategia agresiva: cortarle el paso al rival en vez de solo evitarlo.
- Usar el multiplicador propio/rival (`multiplier_1`/`multiplier_2`) para decidir cuándo vale la pena desviarse a buscar una `X` vs. ir directo por el dígito (por ejemplo, ser menos agresivo por la `X` una vez que el multiplicador ya es alto, porque el valor marginal baja).

## Créditos

Armado para la actividad de programación de bots de la facultad. Estrategia y tests desarrollados iterativamente, ajustando con datos de partidas reales (incluyendo un torneo) en vez de solo a partir de la letra de las reglas.