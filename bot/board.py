"""Representación del tablero y algoritmos de búsqueda sobre él."""

from collections import deque

from bot.constants import DIGIT_CHARS, DIRS


class Board:
    """Grilla del juego con búsquedas de caminos y de espacio libre.

    Las posiciones son tuplas ``(fila, columna)``. Las filas y columnas
    se derivan de la grilla recibida, no de ningún campo del mensaje.
    """

    def __init__(self, grid):
        """Crea el tablero a partir de una lista de filas de caracteres."""
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0

    @classmethod
    def from_string(cls, board_str):
        """Parsea el string ``|...|\\n|...|`` que manda el servidor."""
        lines = [line for line in board_str.split('\n') if line]
        return cls([list(cls._strip_walls(line)) for line in lines])

    @staticmethod
    def _strip_walls(line):
        """Quita los ``|`` de los bordes de una fila si los tiene."""
        return line[1:-1] if line.startswith('|') else line

    def in_bounds(self, pos):
        """Indica si la posición está dentro del tablero."""
        row, col = pos
        return 0 <= row < self.rows and 0 <= col < self.cols

    def char_at(self, pos):
        """Devuelve el carácter de una celda."""
        return self.grid[pos[0]][pos[1]]

    def find(self, char):
        """Primera posición donde aparece ``char`` o ``None``."""
        for row_index, row in enumerate(self.grid):
            if char in row:
                return (row_index, row.index(char))
        return None

    def count(self, char):
        """Cantidad de veces que aparece ``char`` en el tablero."""
        return sum(row.count(char) for row in self.grid)

    def digits_present(self):
        """Conjunto de dígitos (enteros) que hay en el tablero."""
        chars = {ch for row in self.grid for ch in row}
        return {int(ch) for ch in chars & DIGIT_CHARS}

    @staticmethod
    def _predecessor(digit):
        """Dígito anterior en la secuencia cíclica (el 1 sigue al 9)."""
        return 9 if digit == 1 else digit - 1

    def target_digit(self):
        """Dígito correcto a comer ahora, leído directo del tablero.

        Es el dígito presente cuyo predecesor cíclico NO está presente.
        Devuelve ``None`` si no hay dígitos. Si el tablero tuviera el
        ciclo completo (no debería), devuelve el menor.
        """
        present = self.digits_present()
        starts = [d for d in sorted(present)
                  if self._predecessor(d) not in present]
        if starts:
            return starts[0]
        return min(present) if present else None

    def neighbors(self, pos):
        """Vecinos dentro del tablero como pares ``(direccion, celda)``."""
        cells = [(name, (pos[0] + dr, pos[1] + dc))
                 for name, (dr, dc) in DIRS.items()]
        return [(name, cell) for name, cell in cells if self.in_bounds(cell)]

    def is_open(self, cell, blocked, extra=()):
        """True si el carácter de la celda no está bloqueado.

        ``blocked`` es un conjunto de caracteres y ``extra`` un conjunto
        de coordenadas que también se consideran ocupadas.
        """
        return self.char_at(cell) not in blocked and cell not in extra

    def open_neighbors(self, pos, blocked, extra=()):
        """Vecinos transitables, en el orden de ``DIRS``."""
        return [(name, cell) for name, cell in self.neighbors(pos)
                if self.is_open(cell, blocked, extra)]

    def walk(self, start, path):
        """Celdas que se visitan al recorrer ``path`` desde ``start``."""
        trail = []
        pos = start
        for name in path:
            dr, dc = DIRS[name]
            pos = (pos[0] + dr, pos[1] + dc)
            trail.append(pos)
        return trail

    def _expand(self, pos, path, visited, queue, blocked):
        """Agrega a la cola BFS los vecinos nuevos de ``pos``."""
        for name, cell in self.open_neighbors(pos, blocked):
            if cell not in visited:
                visited.add(cell)
                queue.append((cell, path + [name]))

    def path_to_char(self, start, blocked, target_char):
        """Camino más corto (lista de direcciones) a ``target_char``.

        Devuelve ``None`` si no hay camino. Evita los caracteres de
        ``blocked``.
        """
        visited = {start}
        queue = deque([(start, [])])
        while queue:
            pos, path = queue.popleft()
            if path and self.char_at(pos) == target_char:
                return path
            self._expand(pos, path, visited, queue, blocked)
        return None

    def path_to_cell(self, start, blocked, target):
        """Camino más corto a una celda concreta o ``None``.

        Devuelve ``[]`` si ya está en ella.
        """
        if start == target:
            return []
        visited = {start}
        queue = deque([(start, [])])
        while queue:
            pos, path = queue.popleft()
            if pos == target:
                return path
            self._expand(pos, path, visited, queue, blocked)
        return None

    def _enqueue_new(self, pos, visited, blocked, extra):
        """Marca y devuelve los vecinos transitables aún no visitados."""
        found = [cell for _, cell in self.open_neighbors(pos, blocked, extra)
                 if cell not in visited]
        visited.update(found)
        return found

    def flood_fill(self, start, blocked, cap, extra=()):
        """Cuenta las celdas libres alcanzables desde ``start``.

        Corta al llegar a ``cap``: solo interesa saber si el espacio es
        suficientemente grande. ``extra`` simula celdas ocupadas por el
        propio cuerpo a lo largo de un camino planeado.
        """
        if not self.is_open(start, blocked, extra):
            return 0
        visited = {start}
        queue = deque([start])
        count = 0
        while queue:
            pos = queue.popleft()
            count += 1
            if count >= cap:
                return count
            queue.extend(self._enqueue_new(pos, visited, blocked, extra))
        return count

    def distances(self, source, blocked, extra=()):
        """Distancia BFS desde ``source`` a cada celda alcanzable."""
        dist = {source: 0}
        queue = deque([source])
        while queue:
            pos = queue.popleft()
            for _, cell in self.open_neighbors(pos, blocked, extra):
                if cell not in dist:
                    dist[cell] = dist[pos] + 1
                    queue.append(cell)
        return dist

    def territory(self, my_pos, opp_pos, blocked, extra=()):
        """Celdas a las que llegamos antes que el rival (tipo Voronoi)."""
        mine = self.distances(my_pos, blocked, extra)
        theirs = self.distances(opp_pos, blocked) if opp_pos else {}
        inf = float('inf')
        return sum(1 for pos, d in mine.items() if d < theirs.get(pos, inf))
