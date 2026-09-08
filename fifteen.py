"""
fifteen.py — 15-puzzle with a Supabase leaderboard (CSCI 2521 reference app)

Setup:
  pip install streamlit supabase

  1. In the Supabase SQL editor, create the table:

     create table if not exists leaderboard (
       id         bigint generated always as identity primary key,
       name       text    not null,
       seconds    double precision not null,
       moves      int     not null default 0,
       created_at timestamptz not null default now()
     );

  2. Create .streamlit/secrets.toml next to this file:

     SUPABASE_KEY = "eyJhbGciOi..."   # Dashboard → Project Settings → API keys

     NOTE: supabase-py needs the project's API key, not the Postgres database
     password — the client talks to Supabase's REST API, which authenticates
     with the key. Use the service_role key for a class demo (it bypasses row
     level security). Keep it in secrets.toml, never in the repo.

  3. streamlit run fifteen.py     (requires Streamlit >= 1.39)
"""

import os
import random
import time

import streamlit as st
from supabase import create_client
import os

SUPABASE_URL = "https://dtqcritroplivlizslbk.supabase.co"

CELL = 72            # tile size in px
GAP = 8              # gap between tiles in px
PITCH = CELL + GAP   # distance between neighboring tiles — used by the animation
ANIM_MS = 150        # slide duration

SOLVED = list(range(1, 17))   # 1..15 in order, 16 stands in for the blank

# ---------------- persistence ----------------

@st.cache_resource
def db():
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    if not key:
        st.error("Missing SUPABASE_KEY — add it to .streamlit/secrets.toml (see file header).")
        st.stop()
    return create_client(SUPABASE_URL, key)

# ---------------- game logic ----------------

def is_solvable(board):
    """Classic 15-puzzle criterion: inversions + blank's row from the bottom is odd."""
    tiles = [v for v in board if v != 16]
    inversions = sum(
        1
        for i in range(len(tiles))
        for j in range(i + 1, len(tiles))
        if tiles[i] > tiles[j]
    )
    row_from_bottom = 4 - board.index(16) // 4   # bottom row = 1
    return (inversions + row_from_bottom) % 2 == 1

def scrambled_board(n_swaps=150):
    """Start from the solved board and swap random pairs (blank counts as a
    piece) an even number of times. Even swaps alone do NOT guarantee a
    solvable puzzle — the blank's row matters too — so we rescramble until
    the parity check passes (about two tries on average)."""
    while True:
        board = SOLVED.copy()
        for _ in range(n_swaps):                  # even number of pair swaps
            i, j = random.sample(range(16), 2)
            board[i], board[j] = board[j], board[i]
        if is_solvable(board):
            return board

def fresh_game():
    st.session_state.board = scrambled_board()
    st.session_state.moves = 0
    st.session_state.tick = 0
    st.session_state.started = False
    st.session_state.t0 = None
    st.session_state.won = False
    st.session_state.final_time = None
    st.session_state.anim = []         # now a LIST of (value, dx, dy) — one per tile that slid
    st.session_state.score_saved = False
    st.session_state.saved_kind = None

def slide(idx):
    """Click handler: any tile in the blank's row or column shoves the whole
    run of tiles between it and the blank, one cell each, toward the blank."""
    board = st.session_state.board
    if st.session_state.won:
        return
    if not st.session_state.started:
        st.session_state.started = True
        st.session_state.t0 = time.time()

    blank = board.index(16)
    br, bc = divmod(blank, 4)
    r, c = divmod(idx, 4)
    dr, dc = (br > r) - (br < r), (bc > c) - (bc < c)
    if (dr != 0) == (dc != 0):         # must share exactly one axis
        return

    st.session_state.tick += 1
    dist = abs(br - r) + abs(bc - c)   # how many tiles slide (1 = classic move)
    st.session_state.moves += dist

    # Shift tiles toward the blank, starting with the one adjacent to it.
    anims = []
    pr, pc = br, bc
    for _ in range(dist):
        tr, tc = pr - dr, pc - dc              # next tile on the way to the click
        value = board[tr * 4 + tc]
        board[pr * 4 + pc] = value
        anims.append((value, (pc - tc) * PITCH, (pr - tr) * PITCH))
        pr, pc = tr, tc
    board[pr * 4 + pc] = 16                    # clicked tile's old spot is now blank
    st.session_state.anim = anims

    if board == SOLVED:
        st.session_state.won = True
        st.session_state.final_time = time.time() - st.session_state.t0

def fmt_time(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:05.2f}"

# ---------------- rendering ----------------

def render_board():
    anims = st.session_state.anim
    anim_map = {a[0]: a for a in anims}        # value -> (value, dx, dy); tile values are unique
    css = f"""
    <style>
      [class*="st-key-board"] {{
        display: grid;
        grid-template-columns: repeat(4, {CELL}px);
        gap: {GAP}px;
        justify-content: center;
      }}
      [class*="st-key-board"] button {{
        width: {CELL}px; height: {CELL}px;
        font-size: 1.7rem; font-weight: 700;
        border-radius: 12px;
      }}
      [class*="st-key-blank"] button {{ visibility: hidden; }}
    """
    for value, dx, dy in anims:
        tick = st.session_state.tick
        css += f"""
      @keyframes slide{value}x{tick} {{
        from {{ transform: translate({dx}px, {dy}px); }}
        to   {{ transform: translate(0, 0); }}
      }}
      [class*="st-key-t{value}x{tick}"] button {{ animation: slide{value}x{tick} {ANIM_MS}ms ease-out; }}
        """
    css += "</style>"
    st.markdown(css, unsafe_allow_html=True)

    tick = st.session_state.tick
    with st.container(key="board"):
        for idx, value in enumerate(st.session_state.board):
            if value == 16:
                st.button(" ", key=f"blank{idx}", disabled=True)
            elif value in anim_map:
                # Fresh keys this move -> buttons remount -> all slides animate together
                if st.button(str(value), key=f"t{value}x{tick}", disabled=st.session_state.won):
                    slide(idx)
                    st.rerun()
            else:
                if st.button(str(value), key=f"t{value}", disabled=st.session_state.won):
                    slide(idx)
                    st.rerun()


def render_status():
    if st.session_state.won:
        st.success(
            f"🎉 Solved in **{fmt_time(st.session_state.final_time)}** "
            f"with **{st.session_state.moves}** moves!"
        )
    elif st.session_state.started:
        st.caption(f"⏱ {fmt_time(time.time() - st.session_state.t0)} · {st.session_state.moves} moves")
    else:
        st.caption("⏱ Timer starts when you click your first tile.")

def render_save_score():
    if not st.session_state.won or st.session_state.score_saved:
        return
    st.subheader("Save your time")
    name = st.text_input("Name for the leaderboard", max_chars=30, key="name_input")
    save_col, cancel_col = st.columns(2)
    if save_col.button("💾 Save score", type="primary"):
        if name.strip():
            try:
                db().table("leaderboard").insert({
                    "name": name.strip(),
                    "seconds": round(st.session_state.final_time, 3),
                    "moves": st.session_state.moves,
                }).execute()
                st.session_state.saved_kind = "saved"
            except Exception as e:
                st.session_state.saved_kind = "failed"
                st.error(f"Could not save your score: {e}")
            st.session_state.score_saved = True
            st.rerun()
        else:
            st.warning("Type a name first — or click Cancel to skip.")
    if cancel_col.button("Cancel"):
        st.session_state.score_saved = True
        st.session_state.saved_kind = "cancelled"
        st.rerun()

def render_leaderboard():
    st.subheader("🏆 Fastest solves")
    try:
        rows = (
            db().table("leaderboard")
            .select("name, seconds, moves")
            .order("seconds")
            .limit(10)
            .execute()
            .data
        )
    except Exception as e:
        st.warning(f"Couldn't reach the leaderboard: {e}")
        return
    if not rows:
        st.info("No scores yet — be the first!")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = [
        f"**{medals[i] if i < 3 else f'{i + 1}.'} {r['name']}** — "
        f"{fmt_time(r['seconds'])} · {r['moves']} moves"
        for i, r in enumerate(rows)
    ]
    st.markdown("\n\n".join(lines))

# ---------------- app ----------------

st.set_page_config(page_title="15 Puzzle", page_icon="🧩")
st.title("🧩 15-Puzzle")
st.caption("Slide a tile into the empty spot. Order the tiles 1–15, fastest time wins.")

if "board" not in st.session_state:
    fresh_game()

if st.button("🔀 Scramble / New game"):
    fresh_game()
    st.rerun()

if st.session_state.score_saved and st.session_state.saved_kind == "saved":
    st.info("Score saved — nice run!")

render_status()
render_board()
render_save_score()
render_leaderboard()
