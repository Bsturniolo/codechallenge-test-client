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

# v4 (16 Sep 2026): the board now also has two 'X' cells -- eating one
# gives +50 (flat, not multiplied) and permanently bumps your own score
# multiplier a notch (x2, x3, x4...), which then scales digit catches
# (digit*100*multiplier). It's always safe to step on (doesn't collide,
# doesn't grow you), so it needs no special entry in any 'blocked' set --
# it's already passable by default since only chars explicitly listed
# in a blocked set stop movement. We do actively route to it when it's
# free value (see choose_direction step 1b below).
MULTIPLIER_CHAR = 'X'

# How high our own multiplier needs to get before we stop prioritizing
# 'X' pickups over the correct digit. Confirmed valuable from a real
# match: a rival who built up to x10 before cashing in digits massively
# outscored us (33432 vs our 284) -- each of their catches after that
# was worth up to 10x more than ours. Chosen a bit below the x10 we saw
# them reach, since returns diminish (going from x9 to x10 helps less
# than x1 to x2) and there's still a real game to play with the
# multiplier once we have it.
MULTIPLIER_ACCUMULATION_CAP = 8


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
    to be a trap and try the next-closest one instead of giving up.

    NOTE: kept for v1-style boards where food is '*'. Since v3, food is
    digits and process_snake_move uses bfs_path_to_char() instead (see
    below) -- this is left in only as a fallback in case a match somehow
    still uses the old '*' food marker."""
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


def bfs_path_to_char(grid, rows, cols, head, blocked, target_char):
    """Shortest path (list of direction names) from head to the nearest
    cell containing `target_char`, avoiding blocked cells. Returns None
    if no such cell is reachable."""
    visited = {head}
    queue = deque([(head, [])])
    while queue:
        (r, c), path = queue.popleft()
        if grid[r][c] == target_char and path:
            return path
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
    return None


def bfs_path_to_cell(grid, rows, cols, start, blocked, target_cell):
    """Shortest path (list of direction names) from start to a specific
    (r, c) coordinate, avoiding blocked cells. Returns [] if start is
    already target_cell, or None if unreachable."""
    if start == target_cell:
        return []
    visited = {start}
    queue = deque([(start, [])])
    while queue:
        (r, c), path = queue.popleft()
        for name, (dr, dc) in DIRS.items():
            nr, nc = r + dr, c + dc
            if not in_bounds(nr, nc, rows, cols):
                continue
            if (nr, nc) in visited:
                continue
            if grid[nr][nc] in blocked:
                continue
            new_path = path + [name]
            if (nr, nc) == target_cell:
                return new_path
            visited.add((nr, nc))
            queue.append(((nr, nc), new_path))
    return None


def flood_fill_area(grid, rows, cols, start, blocked, cap, extra_blocked_coords=None):
    """Counts how many free cells are reachable from `start` (BFS over
    open space). Used to detect dead ends / pockets that are too small
    for our own body to fit into safely. `cap` stops the search early
    once we know the area is 'big enough', to keep this cheap.

    `extra_blocked_coords`, if given, is a set of specific (r, c) cells
    to also treat as blocked -- used to simulate our own body occupying
    cells further along a planned path (see path_is_safe below), since
    those cells won't be free anymore by the time we'd actually be
    standing at `start`."""
    extra_blocked_coords = extra_blocked_coords or ()
    if grid[start[0]][start[1]] in blocked or start in extra_blocked_coords:
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
            if (nr, nc) in extra_blocked_coords:
                continue
            visited.add((nr, nc))
            queue.append((nr, nc))
    return count


def path_is_safe(grid, rows, cols, head, path, lookahead_blocked, own_length, depth=3):
    """Multi-step lookahead dead-end check. A single-step flood fill can
    be fooled: the immediate next cell might open into a big room, but
    a few steps further down the SAME path our own body (which keeps
    growing behind us as we walk) can pinch that room down to nothing --
    the classic 'coiled into a corner' trap.

    This always evaluates safety at the path's TRUE final destination
    (not some arbitrary earlier point), since the actual risk is "can I
    still move once I arrive". Only the last `depth` cells travelled
    before that point are treated as freshly-occupied body (our own
    tail will have had time to shift out of older, farther-back path
    cells by the time we get here, so we don't pessimistically block
    those)."""
    pos = head
    trail = []
    for name in path:
        dr, dc = DIRS[name]
        pos = (pos[0] + dr, pos[1] + dc)
        trail.append(pos)
    passed_through = set(trail[:-1][-depth:]) if len(trail) > 1 else set()
    area = flood_fill_area(
        grid, rows, cols, pos, lookahead_blocked,
        cap=own_length + 1, extra_blocked_coords=passed_through,
    )
    return area >= own_length


def bfs_distances_from(grid, rows, cols, source, blocked, extra_blocked_coords=None):
    """BFS distance from a single source cell to every reachable open
    cell. Returns a dict {(r, c): distance}.

    `extra_blocked_coords`, if given, is a set of specific (r, c) cells
    to also treat as blocked (used to simulate our own body trail), kept
    separate from `blocked` since that's a set of board CHARACTERS, not
    coordinates."""
    extra_blocked_coords = extra_blocked_coords or ()
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
            if (nr, nc) in extra_blocked_coords:
                continue
            dist[(nr, nc)] = d + 1
            queue.append((nr, nc))
    return dist


def territory_score(grid, rows, cols, my_pos, opp_pos, blocked, extra_blocked_coords=None):
    """Rough 'Voronoi' territory count: for every open cell, whoever
    reaches it in fewer steps 'controls' it. Returns how many cells we'd
    control from my_pos. A bigger number means more room to maneuver and
    more food we'll likely reach before the rival does -- a much better
    long-term signal than just distance to the closest food.

    `extra_blocked_coords`, if given, are cells to also treat as blocked
    for OUR OWN distances only (simulating our own body occupying them by
    the time we'd be standing at my_pos) -- the rival's distances aren't
    affected by our body trail."""
    my_dist = bfs_distances_from(grid, rows, cols, my_pos, blocked, extra_blocked_coords)
    opp_dist = bfs_distances_from(grid, rows, cols, opp_pos, blocked) if opp_pos else {}
    score = 0
    for pos, d in my_dist.items():
        if d < opp_dist.get(pos, float('inf')):
            score += 1
    return score


def choose_direction(grid, rows, cols, head, own_head_char, own_body_char,
                      opp_head_char, opp_body_char, target_digit, own_multiplier=1):
    """Decide the next move.

    v3 rules: food is now digits 1-9. Only the correct next digit in the
    ascending cyclic sequence (target_digit) is safe to eat -- any other
    digit costs -500 points. So we:

    1. Treat every digit that ISN'T target_digit as an obstacle, exactly
       like a snake body -- we should never walk onto it, whether or not
       it's on our way somewhere.
    2. Try every immediate direction that leads toward the correct
       digit, using a multi-step lookahead (not just the next cell) to
       skip any that would coil us into a dead end, and skipping moves
       right next to a rival that's the same size or bigger (risky
       head-to-head). Among the safe ones, take the shortest.
    3. If target_digit isn't reachable safely (or isn't on the board
       yet), fall back to whichever open, non-digit cell gives the most
       territory / space, same as before -- survive and wait for it to
       appear rather than risk a wrong digit.

    Returns (direction, target_cell) where target_cell is the actual
    digit cell we're ultimately routing to (or None if we're just
    playing it safe with no specific target this turn). The caller uses
    target_cell to detect, next turn, whether we actually arrived there.
    """
    target_char = str(target_digit)
    wrong_digits = DIGIT_CHARS - {target_char}

    blocked = {own_body_char, opp_body_char, opp_head_char} | wrong_digits
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
        # Only bail out when the rival is STRICTLY longer than us (a
        # collision we'd clearly lose). If we're equal or longer, the
        # risk is acceptable given how much speed matters in this
        # digit-racing format -- being overly cautious here just loses
        # races to the rival reaching food first.
        return dist <= 1 and opp_length > own_length

    def step_area(nr, nc):
        # cap the flood fill right above own_length -- we only need to
        # know the pocket is big enough, not its exact size, so there's
        # no benefit to a bigger cap.
        return flood_fill_area(grid, rows, cols, (nr, nc), lookahead_blocked, cap=own_length + 1)

    def step_territory(nr, nc):
        return territory_score(grid, rows, cols, (nr, nc), opp_head, lookahead_blocked)

    def opp_distance_to(target_pos):
        """How many steps the rival needs to reach target_pos, using
        their own body/our body as obstacles (a reasonable estimate of
        their movement even without knowing their exact algorithm).
        None if unreachable for them (or no rival on the board)."""
        if not opp_head:
            return None
        opp_blocked = {own_body_char, opp_body_char, own_head_char}
        opp_path = bfs_path_to_cell(grid, rows, cols, opp_head, opp_blocked, target_pos)
        return len(opp_path) if opp_path is not None else None

    def try_reach_x():
        """If an 'X' (permanent multiplier) is safely reachable and not
        contested by the rival, return (direction, target_cell) for it.
        None otherwise."""
        x_path = bfs_path_to_char(grid, rows, cols, head, blocked, MULTIPLIER_CHAR)
        if not x_path or not path_is_safe(grid, rows, cols, head, x_path, lookahead_blocked, own_length):
            return None
        name = x_path[0]
        dr, dc = DIRS[name]
        nr, nc = head[0] + dr, head[1] + dc
        if risky_head_on(nr, nc):
            return None
        r, c = head
        for step_name in x_path:
            pdr, pdc = DIRS[step_name]
            r, c = r + pdr, c + pdc
        x_opp_dist = opp_distance_to((r, c))
        # Only worth it if we're not walking into a contested cell --
        # the multiplier bump isn't worth risking a trap for.
        if x_opp_dist is None or x_opp_dist > len(x_path):
            return name, (r, c)
        return None

    # 0) v4 ACCUMULATION PHASE: a real match showed a rival who ate ten
    # 'X's back to back BEFORE going after any digit, building their
    # multiplier to x10, then started cashing in digits worth up to
    # 9000 each instead of 900 -- they ended that match with 33432
    # points to our 284. Since the multiplier is permanent and scales
    # every future digit catch, it's usually worth deferring the digit
    # chase while our own multiplier is still low and grabbing a safely
    # reachable 'X' first -- the earlier in the game we do this, the
    # more future catches benefit from it.
    if own_multiplier < MULTIPLIER_ACCUMULATION_CAP:
        result = try_reach_x()
        if result:
            return result

    # 1) Try to reach the correct digit. Rather than computing only the
    # single shortest path and giving up on the target entirely if that
    # one path looks unsafe, we check all 4 immediate directions that
    # still lead somewhere toward the target and take the shortest one
    # that passes a multi-step lookahead safety check (path_is_safe) --
    # this catches self-coiling traps a single-step check would miss,
    # while committing to the target more often than bailing out to the
    # open-space fallback the first time the single shortest route looks
    # borderline.
    #
    # Among the safe candidates, we also avoid ones where the rival can
    # reach that exact same cell at least as fast as us: that's exactly
    # how we ended up boxed in in real matches -- the destination looked
    # spacious, but the rival got there around the same time and sealed
    # off the room before we could use it. We only fall back to a
    # contested candidate if it's the only option, since standing still
    # doing nothing isn't available either.
    candidates = []       # ones where we clearly win the race
    contested = []        # rival ties or beats us there -- last resort only
    for name, (dr, dc) in DIRS.items():
        nr, nc = head[0] + dr, head[1] + dc
        if not in_bounds(nr, nc, rows, cols) or grid[nr][nc] in blocked:
            continue
        if risky_head_on(nr, nc):
            continue
        if grid[nr][nc] == target_char:
            sub_path = []
        else:
            sub_path = bfs_path_to_char(grid, rows, cols, (nr, nc), blocked, target_char)
            if sub_path is None:
                continue  # this direction doesn't lead to the target at all
        full_path = [name] + sub_path
        if not path_is_safe(grid, rows, cols, head, full_path, lookahead_blocked, own_length):
            continue
        r, c = head
        for step_name in full_path:
            pdr, pdc = DIRS[step_name]
            r, c = r + pdr, c + pdc
        entry = (len(full_path), name, full_path, (r, c))
        opp_dist = opp_distance_to((r, c))
        if opp_dist is not None and opp_dist <= len(full_path):
            contested.append(entry)
        else:
            candidates.append(entry)

    for pool in (candidates, contested):
        if pool:
            pool.sort(key=lambda c: c[0])
            _, name, full_path, target_pos = pool[0]
            return name, target_pos

    # 1b) The correct digit isn't safely reachable right now (not on the
    # board yet, or only reachable through a trap). Rather than jump
    # straight to pure territory maximization, check if an 'X' (permanent
    # score multiplier) is safely reachable -- since we weren't going to
    # catch the digit this turn anyway, grabbing a multiplier is free
    # value with no race time lost. (Already tried above if we were in
    # the accumulation phase, but worth trying again here regardless of
    # multiplier level -- still better than nothing.)
    result = try_reach_x()
    if result:
        return result

    # 2) Neither the digit nor an X is safely reachable: pick whichever legal adjacent
    # move gives the most territory / space, skipping risky
    # head-to-head cells and any wrong digit.
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
        return best_dir, None

    # 3) Nothing "safe" left (fully boxed in) -- take any legal move at
    # all rather than not moving, even if it risks a head-to-head or a
    # wrong digit (better than certain death standing still).
    for name, (dr, dc) in DIRS.items():
        nr, nc = head[0] + dr, head[1] + dc
        if in_bounds(nr, nc, rows, cols) and grid[nr][nc] not in {own_body_char, opp_body_char}:
            return name, None

    return None, None  # truly no legal move exists


# --- v3: digit-sequence food -------------------------------------------
#
# Since 9 Sep 2026, food is digits 1-9 instead of '*'. You must eat them
# in ascending cyclic order (..., 7, 8, 9, 1, 2, ...); the correct digit
# scores digit*100, any other digit costs -500.
#
# CONFIRMED FROM OFFICIAL DOCS ("How to play"): the correct next digit
# can be read directly off the board every turn -- no state tracking
# needed at all. The board always holds 5 consecutive digits in the
# cyclic sequence (e.g. 1,2,3,4,5; once 1 is eaten correctly, 6 appears,
# leaving 2..6); the correct one is whichever present digit's cyclic
# predecessor (...8,9,1...) is NOT also present on the board.
#
# This replaces an earlier, more fragile approach that tried to infer
# the sequence purely from watching score_1/score_2 change turn to
# turn. That approach worked (validated against real matches) but had a
# real failure mode: v4's per-player multiplier scales catches
# (digit*100*multiplier) enough that a catch could be easy to miss or
# misread if the multiplier value used didn't line up exactly right.
# Reading the digit straight off the board sidesteps that class of bug
# entirely -- there's no persistent state to desync, it's recomputed
# fresh from the ground truth every single turn.
DIGIT_CHARS = set('123456789')
STARTING_DIGIT = 1  # board's own starting layout, kept as a fallback default


def determine_target_digit(grid):
    """Scan the board for every digit present and return the one whose
    cyclic predecessor (9's predecessor is... no wait, 1's predecessor
    is 9) is NOT also on the board -- that's the correct one to eat
    next, straight from the rules. Returns None if the board has no
    digits at all (shouldn't normally happen -- the rules say 5 are
    always in play -- but we fall back gracefully if it does)."""
    present = {int(ch) for row in grid for ch in row if ch in DIGIT_CHARS}
    if not present:
        return None
    for d in present:
        predecessor = 9 if d == 1 else d - 1
        if predecessor not in present:
            return d
    # Degenerate case (shouldn't happen per the rules: a full 1-9 ring
    # with no gap has no valid "start"). Fall back to the smallest
    # present digit rather than crashing.
    return min(present)
# -------------------------------------------------------------------------


async def process_snake_move(websocket, request_data):
    data = request_data['data']
    board_str = data['board']
    side = data['side']  # 'A' or 'B' -> that's our head char, lowercase is our body

    own_head_char = side
    own_body_char = side.lower()
    opp_head_char = 'B' if side == 'A' else 'A'
    opp_body_char = opp_head_char.lower()

    grid = parse_board(board_str)
    # v2: board size now varies per match (12-20 per side, not necessarily
    # square) and your_turn gained a 'board_size' field. Rather than trust
    # any particular field name (which may keep changing), we derive the
    # real dimensions straight from the parsed board itself -- this works
    # no matter what the server calls the size field, or whether it even
    # sends one.
    rows = len(grid)
    cols = len(grid[0]) if grid else 0
    print(board_str)

    # v4: score multiplier per player, confirmed not derivable from the
    # board itself -- has to come from these fields. Confirmed from real
    # match logs that player_1 <-> side 'A' and player_2 <-> side 'B'
    # consistently, so we map it the same way as score_1/score_2.
    own_multiplier = data.get('multiplier_1') if side == 'A' else data.get('multiplier_2')
    opp_multiplier = data.get('multiplier_2') if side == 'A' else data.get('multiplier_1')
    if own_multiplier is not None:
        print('multiplier: us={} rival={}'.format(own_multiplier, opp_multiplier))

    head = find_char(grid, own_head_char)
    target_digit = determine_target_digit(grid)
    if target_digit is None:
        target_digit = STARTING_DIGIT  # no digits on board yet (shouldn't normally happen)

    direction = None
    if head:
        direction, _target_pos = choose_direction(
            grid, rows, cols, head,
            own_head_char, own_body_char, opp_head_char, opp_body_char,
            target_digit, own_multiplier or 1,
        )

    if direction is None:
        direction = choice(list(DIRS.keys()))  # last resort, shouldn't normally happen

    move = {
        'game_id': data['game_id'],
        'turn_token': data['turn_token'],
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