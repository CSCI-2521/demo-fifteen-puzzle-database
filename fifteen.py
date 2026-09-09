"""
fifteen.py — sliding puzzles with a Supabase leaderboard (CSCI 2521 reference app)

Setup:
  pip install streamlit supabase

  1. In the Supabase SQL editor, create the table:

     create table if not exists leaderboard (
       id         bigint generated always as identity primary key,
       name       text    not null,
       puzzle_size text    not null check (puzzle_size in ('3', '8', '15')),
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
import time

import streamlit as st
from supabase import create_client
from game_logic import move_tile, scrambled_board, solved_board

SUPABASE_URL = "https://dtqcritroplivlizslbk.supabase.co"

CELL = 72            # tile size in px
GAP = 8              # gap between tiles in px
PITCH = CELL + GAP   # distance between neighboring tiles — used by the animation
ANIM_MS = 150        # slide duration

PUZZLES = {
    3: ("3-Puzzle (2×2)", 2),
    8: ("8-Puzzle (3×3)", 3),
    15: ("15-Puzzle (4×4)", 4),
}

# ---------------- persistence ----------------

@st.cache_resource
def db():
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    if not key:
        st.error("Missing SUPABASE_KEY — add it to .streamlit/secrets.toml (see file header).")
        st.stop()
    return create_client(SUPABASE_URL, key)

def fresh_game():
    puzzle_size = st.session_state.puzzle_size
    dimension = PUZZLES[puzzle_size][1]
    st.session_state.board = scrambled_board(dimension)
    st.session_state.moves = 0
    st.session_state.tick = 0
    st.session_state.started = False
    st.session_state.t0 = None
    st.session_state.won = False
    st.session_state.final_time = None
    st.session_state.anim = None       # (value, dx, dy, tick) for the tile that slid
    st.session_state.score_saved = False
    st.session_state.saved_kind = None

def slide(idx):
    """Click handler: move an adjacent tile into the blank."""
    board = st.session_state.board
    puzzle_size = st.session_state.puzzle_size
    dimension = PUZZLES[puzzle_size][1]
    if st.session_state.won:
        return
    if not st.session_state.started:
        st.session_state.started = True
        st.session_state.t0 = time.time()

    blank = board.index(dimension * dimension)
    br, bc = divmod(blank, dimension)
    r, c = divmod(idx, dimension)
    if abs(br - r) + abs(bc - c) != 1:
        return

    st.session_state.tick += 1
    st.session_state.moves += 1
    value = board[idx]
    board[:] = move_tile(board, idx, dimension)
    st.session_state.anim = (value, (c - bc) * PITCH, (r - br) * PITCH, st.session_state.tick)

    if board == solved_board(dimension):
        st.session_state.won = True
        st.session_state.final_time = time.time() - st.session_state.t0

def fmt_time(seconds):
    m, s = divmod(seconds, 60)
    return f"{int(m)}:{s:05.2f}"

# ---------------- rendering ----------------

def render_board():
    anim = st.session_state.anim
    puzzle_size = st.session_state.puzzle_size
    dimension = PUZZLES[puzzle_size][1]
    css = f"""
    <style>
      [class*="st-key-board"] {{
        display: grid;
        grid-template-columns: repeat({dimension}, {CELL}px);
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
    if anim:
        value, dx, dy, tick = anim
        css += f"""
      @keyframes slide{tick} {{
        from {{ transform: translate({dx}px, {dy}px); }}
        to   {{ transform: translate(0, 0); }}
      }}
      [class*="st-key-t{puzzle_size}x{value}x{tick}"] button {{ animation: slide{tick} {ANIM_MS}ms ease-out; }}
        """
    css += "</style>"
    st.markdown(css, unsafe_allow_html=True)

    tick = st.session_state.tick
    with st.container(key="board"):
        for idx, value in enumerate(st.session_state.board):
            if value == dimension * dimension:
                st.button(" ", key=f"blank{puzzle_size}x{idx}", disabled=True)
            elif anim and value == anim[0]:
                if st.button(str(value), key=f"t{puzzle_size}x{value}x{tick}", disabled=st.session_state.won):
                    slide(idx)
                    st.rerun()
            else:
                if st.button(str(value), key=f"t{puzzle_size}x{value}", disabled=st.session_state.won):
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
                    "puzzle_size": str(st.session_state.puzzle_size),
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
    puzzle_size = st.session_state.puzzle_size
    st.subheader(f"🏆 Fastest {PUZZLES[puzzle_size][0]} solves")
    try:
        rows = (
            db().table("leaderboard")
            .select("name, seconds, moves")
            .eq("puzzle_size", str(puzzle_size))
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
st.title("🧩 Sliding Puzzle")
st.caption("Slide adjacent tiles into the empty spot. Order the tiles, fastest time wins.")

if "puzzle_size" not in st.session_state:
    st.session_state.puzzle_size = 15

st.selectbox(
    "Puzzle size",
    options=list(PUZZLES),
    format_func=lambda value: PUZZLES[value][0],
    key="puzzle_size",
    on_change=fresh_game,
)

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
