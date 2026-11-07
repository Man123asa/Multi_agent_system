import os
from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .engine import Game

app = FastAPI(title="Hold'em Royale")
games: dict = {}  # one table per browser session


def G(sid: str) -> Game:
    if sid not in games:
        if len(games) > 500: games.pop(next(iter(games)))
        games[sid] = Game()
    return games[sid]


class Act(BaseModel):
    action: str
    amount: int = 0


@app.get("/health")
def health(): return {"status": "ok"}


@app.get("/api/state")
def state(x_session: str = Header("anon")): return G(x_session).state()


@app.post("/api/action")
def action(a: Act, x_session: str = Header("anon")):
    g = G(x_session)
    if a.action not in ("fold", "check", "call", "raise"): raise HTTPException(422, "bad action")
    if g.hand_over or g.to_act != "You": raise HTTPException(409, "not your turn")
    g.act("You", a.action, a.amount)
    return g.state()


@app.post("/api/step")
def step(x_session: str = Header("anon")):
    g = G(x_session)
    if not g.hand_over and g.to_act not in (None, "You"):
        g.act(g.to_act, *g.ai(g.to_act))
    return g.state()


@app.post("/api/next")
def nxt(x_session: str = Header("anon")):
    g = G(x_session)
    if g.hand_over and not g.over: g.new_hand()
    return g.state()


@app.post("/api/reset")
def reset(x_session: str = Header("anon")):
    games[x_session] = Game()
    return games[x_session].state()


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "static"), html=True), name="static")
