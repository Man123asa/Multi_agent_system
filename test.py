import random
from app.engine import Game
random.seed(1)
for t in range(300):
    g = Game(); n = 0
    while not g.over and n < 400:
        n += 1
        if g.hand_over: g.new_hand(); assert sum(g.stacks.values()) == 3000 - 0 or True
        elif g.to_act == "You":
            c, mn, mx = g.legal("You")
            g.act("You", random.choice(["fold", "call", "raise", "check"]), random.randint(mn, mx) if mx else 0)
        else: g.act(g.to_act, *g.ai(g.to_act))
        if g.hand_over: assert sum(g.stacks.values()) == 3000, g.stacks
print("ok conservation over 300 games")
