import asyncio
import json
from random import randint, choice
import sys
import websockets
import time
from collections import deque


# A running text log of events received / actions sent per game, written to
# game_<game_id>.log when the match ends.
HISTORY = {}


def log_event(game_id, message):
    HISTORY.setdefault(game_id, []).append('< ' + json.dumps(message))


def log_action(game_id, message):
    HISTORY.setdefault(game_id, []).append('> ' + json.dumps(message))


def write_game_log(game_id):
    try:
        with open(f"game_{game_id}.log", "w") as f:
            f.write("\n".join(HISTORY.get(game_id, [])) + "\n")
        print(f"saved game_{game_id}.log")
    except OSError as e:
        print(f"could not write game log: {e}")


async def send(websocket, action, data):
    message = json.dumps(
        {
            'action': action,
            'data': data,
        }
    )
    print(message)
    await websocket.send(message)


async def start(auth_token):
    uri = "wss://server.codechallenge.net.ar/ws?token={}".format(auth_token)
    # uri = "ws://localhost:5000/ws?token={}".format(auth_token)
    while True:
        try:
            print('connection to {}'.format(uri))
            async with websockets.connect(uri) as websocket:
                print('connection READY!')
                await play(websocket)
        except KeyboardInterrupt:
            print('Exiting...')
            break
        except Exception:
            print('connection error!')
            time.sleep(3)


async def play(websocket):
    while True:
        try:
            request = await websocket.recv()
        except KeyboardInterrupt:
            print('Exiting...')
            break
        except Exception as e:
            # The socket itself died -- this really does need a reconnect.
            print('connection lost: {}'.format(str(e)))
            break

        print(f"< {request}")
        try:
            request_data = json.loads(request)
            if request_data['event'] == 'update_user_list':
                pass
            if request_data['event'] == 'game_over':
                game_id = request_data['data'].get('game_id')
                if game_id:
                    log_event(game_id, request_data)
                    write_game_log(game_id)
            if request_data['event'] == 'challenge':
                # if request_data['data']['opponent'] == 'favoriteopponent':
                await send(
                    websocket,
                    'accept_challenge',
                    {
                        'challenge_id': request_data['data']['challenge_id'],
                    },
                )
            if request_data['event'] == 'your_turn':
                log_event(request_data['data']['game_id'], request_data)
                await process_your_turn(websocket, request_data)
        except KeyboardInterrupt:
            print('Exiting...')
            break
        except Exception as e:
            # Something about THIS message was unexpected (weird board,
            # missing field, etc). Log it and keep listening instead of
            # dropping out of the whole match -- losing the connection
            # mid-game means forfeiting every turn until we reconnect.
            print('error handling message: {}'.format(str(e)))


async def process_your_turn(websocket, request_data):
    await process_snake_move(websocket, request_data)


DIRS = {
    'up': (-1, 0),
    'down': (1, 0),
    'left': (0, -1),
    'right': (0, 1),
}


def parse_board(board_str):
    """Turn the raw '|aaA   |\n...' string into a 2D list of chars
    (rows x cols), stripping the leading/trailing '|' wall characters."""
    grid = []
    for line in board_str.split('\n'):
        if not line:
            continue
        inner = line[1:-1] if line.startswith('|') else line
        grid.append(list(inner))
    return grid


def find_char(grid, target):
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == target:
                return (r, c)
    return None


def count_char(grid, target):
    return sum(row.count(target) for row in grid)


def in_bounds(r, c, rows, cols):
    return 0 <= r < rows and 0 <= c < cols


def bfs_paths_to_foods(grid, rows, cols, head, blocked, max_targets=6):
    """Like bfs_path_to_food, but instead of stopping at the first food
    found, keeps collecting food targets in increasing distance order
    (up to max_targets). This lets us skip a nearest food that turns out
    to be a trap and try the next-closest one instead of giving up."""
    visited = {head}
    queue = deque([(head, [])])
    results = []
    while queue and len(results) < max_targets:
        (r, c), path = queue.popleft()
        if grid[r][c] == '*' and path:
            results.append(path)
        for name, (dr, dc) in DIRS.items():
            nr, nc = r + dr, c + dc
            if not in_bounds(nr, nc, rows, cols):
                continue
            if (nr, nc) in visited:
                continue
            if grid[nr][nc] in blocked:
                continue
            visited.add((nr, nc))
            queue.append(((nr, nc), path + [name]))
    return results


def flood_fill_area(grid, rows, cols, start, blocked, cap):
    """Counts how many free cells are reachable from `start` (BFS over
    open space). Used to detect dead ends / pockets that are too small
    for our own body to fit into safely. `cap` stops the search early
    once we know the area is 'big enough', to keep this cheap."""
    if grid[start[0]][start[1]] in blocked:
        return 0
    visited = {start}
    queue = deque([start])
    count = 0
    while queue:
        r, c = queue.popleft()
        count += 1
        if count >= cap:
            return count
        for dr, dc in DIRS.values():
            nr, nc = r + dr, c + dc
            if not in_bounds(nr, nc, rows, cols):
                continue
            if (nr, nc) in visited:
                continue
            if grid[nr][nc] in blocked:
                continue
            visited.add((nr, nc))
            queue.append((nr, nc))
    return count


def bfs_distances_from(grid, rows, cols, source, blocked):
    """BFS distance from a single source cell to every reachable open
    cell. Returns a dict {(r, c): distance}."""
    dist = {source: 0}
    queue = deque([source])
    while queue:
        r, c = queue.popleft()
        d = dist[(r, c)]
        for dr, dc in DIRS.values():
            nr, nc = r + dr, c + dc
            if not in_bounds(nr, nc, rows, cols):
                continue
            if (nr, nc) in dist:
                continue
            if grid[nr][nc] in blocked:
                continue
            dist[(nr, nc)] = d + 1
            queue.append((nr, nc))
    return dist


def territory_score(grid, rows, cols, my_pos, opp_pos, blocked):
    """Rough 'Voronoi' territory count: for every open cell, whoever
    reaches it in fewer steps 'controls' it. Returns how many cells we'd
    control from my_pos. A bigger number means more room to maneuver and
    more food we'll likely reach before the rival does -- a much better
    long-term signal than just distance to the closest food."""
    my_dist = bfs_distances_from(grid, rows, cols, my_pos, blocked)
    opp_dist = bfs_distances_from(grid, rows, cols, opp_pos, blocked) if opp_pos else {}
    score = 0
    for pos, d in my_dist.items():
        if d < opp_dist.get(pos, float('inf')):
            score += 1
    return score


def choose_direction(grid, rows, cols, head, own_head_char, own_body_char,
                      opp_head_char, opp_body_char):
    """Decide the next move:
    1. Look at several of the nearest foods (not just the closest one).
    2. Skip any whose first step leads into a pocket smaller than our
       own body (avoids getting trapped) or right next to a rival that's
       the same size or bigger (avoids a head-to-head we'd likely lose).
    3. Among the safe candidates, go for the closest food; ties are
       broken by whichever step gives us more board territory (Voronoi
       score) and, after that, more distance from the rival's head.
    4. If no food is safely reachable at all, fall back to whichever
       adjacent cell gives the most territory / open space (survive as
       long as possible and out-maneuver the rival).
    """
    blocked = {own_body_char, opp_body_char, opp_head_char}
    # For "what happens after I take this step" lookahead (dead-end and
    # territory checks), our current head cell must count as blocked too:
    # next turn it becomes part of our body, so a candidate move can't
    # rely on looping back through where the head is right now.
    lookahead_blocked = blocked | {own_head_char}
    own_length = 1 + count_char(grid, own_body_char)
    opp_length = 1 + count_char(grid, opp_body_char)
    opp_head = find_char(grid, opp_head_char)

    def risky_head_on(nr, nc):
        if not opp_head:
            return False
        dist = abs(nr - opp_head[0]) + abs(nc - opp_head[1])
        return dist <= 1 and opp_length >= own_length

    def step_area(nr, nc):
        # cap the flood fill at "own_length + a small margin" -- we only
        # need to know if the pocket is big enough, not its exact size.
        return flood_fill_area(grid, rows, cols, (nr, nc), lookahead_blocked, cap=own_length + 5)

    def step_territory(nr, nc):
        return territory_score(grid, rows, cols, (nr, nc), opp_head, lookahead_blocked)

    # 1) Gather several of the nearest foods and keep only the safe ones.
    food_paths = bfs_paths_to_foods(grid, rows, cols, head, blocked, max_targets=6)
    safe_candidates = []  # (path_length, -territory, name, nr, nc)
    for path in food_paths:
        name = path[0]
        dr, dc = DIRS[name]
        nr, nc = head[0] + dr, head[1] + dc
        if not in_bounds(nr, nc, rows, cols) or grid[nr][nc] in blocked:
            continue
        if risky_head_on(nr, nc):
            continue
        if step_area(nr, nc) < own_length:
            continue
        safe_candidates.append((len(path), -step_territory(nr, nc), name, nr, nc))

    if safe_candidates:
        safe_candidates.sort()  # shortest path first, more territory as tie-break
        best_len = safe_candidates[0][0]
        tied = [c for c in safe_candidates if c[0] == best_len]
        best_terr = min(c[1] for c in tied)  # most negative = most territory
        tied = [c for c in tied if c[1] == best_terr]
        if len(tied) > 1 and opp_head:
            tied.sort(key=lambda c: -(abs(c[3] - opp_head[0]) + abs(c[4] - opp_head[1])))
        return tied[0][2]

    # 2) No food is safely reachable: pick whichever legal adjacent move
    # gives the most territory (falls back to open space if no rival),
    # skipping risky head-to-head cells.
    best_dir, best_score = None, -1
    for name, (dr, dc) in DIRS.items():
        nr, nc = head[0] + dr, head[1] + dc
        if not in_bounds(nr, nc, rows, cols) or grid[nr][nc] in blocked:
            continue
        if risky_head_on(nr, nc):
            continue
        score = step_territory(nr, nc) if opp_head else step_area(nr, nc)
        if score > best_score:
            best_score, best_dir = score, name
    if best_dir:
        return best_dir

    # 3) Nothing "safe" left (fully boxed in) -- take any legal move at
    # all rather than not moving, even if it risks a head-to-head.
    for name, (dr, dc) in DIRS.items():
        nr, nc = head[0] + dr, head[1] + dc
        if in_bounds(nr, nc, rows, cols) and grid[nr][nc] not in {own_body_char, opp_body_char}:
            return name

    return None  # truly no legal move exists


async def process_snake_move(websocket, request_data):
    data = request_data['data']
    board_str = data['board']
    rows = data['rows']
    cols = data['cols']
    side = data['side']  # 'A' or 'B' -> that's our head char, lowercase is our body

    own_head_char = side
    own_body_char = side.lower()
    opp_head_char = 'B' if side == 'A' else 'A'
    opp_body_char = opp_head_char.lower()

    grid = parse_board(board_str)
    print(board_str)

    head = find_char(grid, own_head_char)
    direction = None
    if head:
        direction = choose_direction(
            grid, rows, cols, head,
            own_head_char, own_body_char, opp_head_char, opp_body_char,
        )
    if direction is None:
        direction = choice(list(DIRS.keys()))  # last resort, shouldn't normally happen

    move = {
        'game_id': data['game_id'],
        'turn_token': data['turn_token'],
        # NOTE: the exact key name the server expects for a snake move is
        # not confirmed from the sample log (only an old, wrong 'col'
        # format was seen, which cost -500 points every turn as an
        # invalid move). 'direction' with up/down/left/right is the most
        # common convention for this kind of game -- if the server keeps
        # penalizing every move, check your challenge's protocol docs and
        # swap this key/values accordingly.
        'direction': direction,
    }
    log_action(move['game_id'], {'action': 'move', 'data': move})
    await send(websocket, 'move', move)


if __name__ == '__main__':
    if len(sys.argv) >= 2:
        auth_token = sys.argv[1]
        asyncio.get_event_loop().run_until_complete(start(auth_token))
    else:
        print('please provide your auth_token')