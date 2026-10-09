# 🐍 Snake Challenge Bot

Bot en Python que juega automáticamente al desafío de Snake multijugador vía WebSocket, para la actividad de la facultad.

## ¿Qué hace?

Se conecta al servidor del challenge, acepta desafíos automáticamente, y en cada turno decide su movimiento (`up`/`down`/`left`/`right`). La estrategia, en orden de prioridad:

1. **Fase de acumulación (v4)**: mientras nuestro propio multiplicador todavía es bajo (menos de x11, `MULTIPLIER_ACCUMULATION_CAP`), prioriza comer una `X` segura por sobre ir al dígito correcto — el multiplicador es permanente y escala TODAS las capturas futuras, así que conviene juntarlo primero. Confirmado con una partida real: el rival que hizo esto (acumuló hasta x10 antes de cazar dígitos) nos sacó 33.432 a 284.
2. **Comida de cola propia (v7)**: si hay un `Ⓐ`/`Ⓑ` de NUESTRA letra a 2 pasos o menos (lo soltó el rival al chocar), lo agarra — es +100 × multiplicador y crece, sin penalidad. Si está más lejos, lo busca cuando no hay dígito alcanzable. El de la letra del rival es solo pisable (no da nada).
3. **Va por el dígito correcto de la secuencia** (ver [Reglas del juego](#reglas-del-juego-resumen) abajo) una vez que el multiplicador ya está alto, evaluando las 4 direcciones inmediatas que lleven hacia él y descartando las que terminan en una trampa, usando un chequeo de seguridad de **varios pasos hacia adelante** (no solo el siguiente casillero) para detectar si nos estamos por enroscar solos en una esquina. Además, si el rival puede llegar a esa misma celda **antes o al mismo tiempo que nosotros**, la tratamos como "disputada" y preferimos otra ruta si hay una libre — eso es justo lo que nos dejó encerrados en una partida real: el destino tenía espacio de sobra, pero el rival llegó primero y nos cerró el paso.
4. Si el dígito correcto no está en el tablero todavía, o no se puede llegar con seguridad: **va a buscar una `X`** igual (aunque el multiplicador ya esté alto) si hay una alcanzable — es ganancia gratis, ya que de todos modos no íbamos a comer nada ese turno.
5. Si tampoco hay una `X` segura: **maximiza territorio** (heurística tipo Voronoi) comparando, celda por celda, quién llega primero — nosotros o el rival — para sobrevivir el mayor tiempo posible y quedar mejor posicionado.
6. En cualquiera de los pasos anteriores, **evita meterse al lado de la cabeza del rival** si es estrictamente más largo que nosotros (un choque que perderíamos seguro). Si es igual o más corto, no se desvía por eso — la velocidad importa más que una cautela excesiva en un juego que es, en el fondo, una carrera.
7. Como último recurso, si está completamente acorralado, manda un movimiento legal: prefiere celdas que sí puede pisar (dígito equivocado o cabeza rival), y la pared `#` recién al final.

Además, desde v5 la **pared `#`** se trata como obstáculo duro (también en la estimación del camino del rival), y desde v6 el bot va a la **copia más cercana** del dígito correcto (las demás copias de dígitos incorrectos son obstáculos).

## Archivos

| Archivo | Qué es |
|---|---|
| `run.py` | El bot. Se conecta al servidor y juega. |
| `test_run.py` | Suite de tests offline (no se conecta a nada): lógica de decisión contra tableros armados a mano, replays de partidas reales, y el flujo de red (`start`, `play`, `send`, logs) con mocks. |
| `start.sh` | Atajo: `./start.sh <token>` instala `websockets` si falta y corre el bot. |
| `match_fixed.json`, `match4_fixed.json` | Partidas reales usadas por los tests de regresión. |

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
Ran 74 tests in 0.0Xs

OK
```

### Cobertura (objetivo ≥ 90 %)

```bash
pip install coverage
python3 -m coverage run test_run.py
python3 -m coverage report -m run.py
```

Resultado actual: **97 %** de `run.py` (74 tests). Las pocas líneas sin cubrir son el bloque `if __name__ == '__main__'` y un par de ramas de borde.

Los tests de replay (`test_replays_real_match_and_matches_ground_truth` y el de multiplicador alto) reproducen partidas reales del torneo para confirmar que la lectura del dígito objetivo desde el tablero coincide turno a turno con lo que pasó de verdad. Hay clases dedicadas a v5 (pared), v6 (copias múltiples) y v7 (comida de cola).

## Reglas del juego (resumen)

El juego fue cambiando de versión con el tiempo. Esto es lo que sabemos confirmado de cada una:

- **v1** (tablero fijo 15×15): comida = `*`, cualquiera vale.
- **v2** (2 sep 2026): el tablero varía de tamaño por partida (12–20 por lado, no necesariamente cuadrado). El bot **no depende de ningún campo del mensaje** para esto — calcula filas/columnas directo del tablero recibido, así que es inmune a que cambien el nombre del campo.
- **v3** (9 sep 2026): la comida son dígitos `1`-`9`. Hay que comerlos en orden ascendente cíclico (`...7,8,9,1,2...`). El dígito correcto suma `dígito × 100`; cualquier otro dígito resta 500.
  - ✅ **Confirmado con la documentación oficial del juego** ("How to play"): el tablero siempre tiene 5 dígitos consecutivos de la secuencia en juego a la vez, y el correcto es el que está en el tablero cuyo predecesor cíclico (`...8,9,1...`) NO está también presente. Esto se puede leer directo del tablero cada turno — el bot ya NO necesita rastrear el puntaje para saber cuál es el dígito correcto, lo lee fresco cada vez con `determine_target_digit()`. Esto reemplazó un sistema anterior (basado en mirar cómo cambiaba `score_1`/`score_2`) que funcionaba pero era más frágil: con el multiplicador de v4 activo, una captura correcta podía valer mucho más de lo esperado y el sistema viejo la perdía de vista. Leer directo del tablero no tiene ningún estado que se pueda desincronizar.
  - La secuencia es **global**, compartida entre los dos jugadores — si el rival come el dígito correcto, el tablero se actualiza para todos (aparece el próximo dígito), así que la lectura del tablero siempre refleja el estado real sin importar quién comió qué.
- **v4** (16 sep 2026): se suman dos celdas `X` al tablero. Comer una da +50 (fijo, no se multiplica) y sube un multiplicador permanente (x2, x3, x4...) que escala los puntos de comida (`dígito × 100 × multiplicador`). Cada jugador tiene su propio multiplicador. La `X` es segura para pisar (no choca, no hace crecer). Los valores de multiplicador vienen en los campos `multiplier_1`/`multiplier_2` de `turn_data` — es el único dato de esta regla que no se puede leer directo del tablero.
  - 💡 **Estrategia confirmada con partida real**: conviene juntar multiplicador ANTES de cazar dígitos, no al revés. Vimos a un rival comer 10 `X` seguidas al principio (llegando a x10) y recién ahí empezar a cazar dígitos — terminó 33.432 a 284. El bot ahora prioriza ir por una `X` segura mientras el propio multiplicador es bajo (por debajo de `MULTIPLIER_ACCUMULATION_CAP`, hoy en 8), y recién después empieza a priorizar el dígito correcto.

- **v5** (23 sep 2026): aparece una **pared `#`** (línea recta de largo impar hasta 11) que se achica de a una celda por extremo después de que mueven ambos jugadores, y reaparece en otro lado cuando desaparece. Chocarla cuesta -500 y la serpiente no se mueve. El bot la lee del tablero y la trata como obstáculo (`WALL_CHAR`).
- **v6** (30 sep 2026): cada dígito aparece en **3–5 copias**. Solo una copia del dígito objetivo da puntos; al comerla desaparecen las demás copias. Una copia equivocada sigue costando -500. El bot va a la copia más cercana por BFS, y `determine_target_digit` ya funciona igual con varias copias (usa un conjunto de dígitos presentes).
- **v7** (7 oct 2026): las partidas duran **400 movimientos** (200 por jugador) y **chocar ya no termina la partida**: la serpiente no se mueve, conserva sus primeros 3 segmentos y el resto de la cola se convierte en **comida de cola** para el rival (`Ⓐ` U+24B6 solo la come A, `Ⓑ` U+24B7 solo B; +100 × multiplicador y crece, no es parte de la secuencia de dígitos). Tu primer choque pone el puntaje en 0, los siguientes restan 500, y bajar de -2500 pierde la partida; el rival no cobra +1000. Pisar la comida de cola de tu propia letra-rival solo la borra (negarle puntos al rival). Como un choque igual es muy costoso (pérdida de cola y de puntos), el bot sigue evitándolos igual que antes.

Si la cátedra anuncia una v8 o cambia algo de esto, la fuente más confiable es la página oficial "How to play" del challenge (`/how-to-play` en el servidor) — guardá o pasale a Claude esa página tal cual (HTML completo, no un resumen) junto con el primer log de una partida jugada con la regla nueva, así se puede confirmar el comportamiento exacto en vez de adivinar.

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
| `#` | Pared (desde v5) — obstáculo, chocarla cuesta -500 |
| `Ⓐ` / `Ⓑ` | Comida de cola (desde v7) — solo la come la serpiente de esa letra |
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

- Con v6, comparar copias del dígito objetivo por seguridad y no solo por cercanía (hoy: la más cercana que pase el chequeo de seguridad).
- Pisar a propósito la comida de cola rival cuando está cerca, para negársela (v7).
- Calibrar `MIN_REMAINING_MOVES_FOR_ACCUMULATION` para partidas de 400 movimientos.
- Ajustar `MULTIPLIER_ACCUMULATION_CAP` (hoy fijo en 11) según cuántos turnos quedan (`remaining_moves`) — no vale la pena seguir acumulando multiplicador si ya casi no queda partida para aprovecharlo.
- Simular varios turnos del rival de forma más completa (no solo "cuántos pasos le toma llegar a esta celda", sino su comportamiento probable turno a turno).
- Estrategia agresiva: cortarle el paso al rival en vez de solo evitarlo.

## Créditos

Armado para la actividad de programación de bots de la facultad. Estrategia y tests desarrollados iterativamente, ajustando con datos de partidas reales (incluyendo un torneo) en vez de solo a partir de la letra de las reglas.