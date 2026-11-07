"""Texas Hold'em engine: proper betting rounds, side pots, kicker-aware hand ranking."""
import itertools, os, random, re
from collections import Counter

SB, BB, START = 10, 20, 1000
RV = {r: i for i, r in enumerate("23456789TJQKA", 2)}
CATS = ["High Card", "One Pair", "Two Pair", "Three of a Kind", "Straight",
        "Flush", "Full House", "Four of a Kind", "Straight Flush"]


def rank5(c):
    r = sorted((RV[x[0]] for x in c), reverse=True)
    g = sorted(Counter(r).items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    order, shape = [k for k, _ in g], [v for _, v in g]
    flush = len({x[1] for x in c}) == 1
    u = sorted(set(r), reverse=True)
    st = 0
    if len(u) == 5:
        st = u[0] if u[0] - u[4] == 4 else (5 if u == [14, 5, 4, 3, 2] else 0)
    if flush and st: return (8, [st])
    if shape[0] == 4: return (7, order)
    if shape == [3, 2]: return (6, order)
    if flush: return (5, r)
    if st: return (4, [st])
    if shape[0] == 3: return (3, order)
    if shape[:2] == [2, 2]: return (2, order)
    if shape[0] == 2: return (1, order)
    return (0, r)


def best(cards):
    return max(rank5(c) for c in itertools.combinations(cards, 5)) if len(cards) >= 5 else None


def _llm_move(g, p):
    """Optional LLM brain (set OPENAI_API_KEY). Returns (action, raise_to) or None."""
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from langchain_openai import ChatOpenAI
        call, mn, mx = g.legal(p)
        persona = ("highly aggressive, high-variance bluffing specialist" if p == "Alpha"
                   else "ultra-conservative, analytical tight strategist")
        prompt = (f"You are {p}, a poker agent with a {persona} style.\nStreet: {g.street}\n"
                  f"Your hand: {g.hands[p]}\nBoard: {g.board}\nPot: {g.pot}\nYour stack: {g.stacks[p]}\n"
                  f"To call: {call}\nMin raise-to: {mn}, max raise-to: {mx}\nRecent actions: {' | '.join(g.log[-5:])}\n"
                  "Reply ONLY as: action: <fold/call/raise>, amount: <integer raise-to total>")
        txt = ChatOpenAI(model=os.environ.get("MODEL_NAME", "gpt-4o-mini"), temperature=0.3).invoke(prompt).content.lower()
        m = re.search(r"action:\s*(fold|call|check|raise)\s*,\s*amount:\s*(\d+)", txt)
        return (m.group(1), int(m.group(2))) if m else None
    except Exception:
        return None


class Game:
    def __init__(s):
        s.names = ["You", "Alpha", "Beta"]
        s.stacks = {n: START for n in s.names}
        s.dealer, s.hand_no, s.log = None, 0, []
        s.over, s.hand_over, s.result, s.winners, s.showdown = False, True, None, [], False
        s.seats, s.hands, s.board, s.active, s.last = [], {}, [], set(), {}
        s.street, s.pot, s.cur, s.to_act = "Pre-Flop", 0, 0, None
        s.bets = {n: 0 for n in s.names}
        s.new_hand()

    def say(s, m):
        s.log = (s.log + [m])[-40:]

    # ---------- hand lifecycle ----------
    def new_hand(s):
        alive = [n for n in s.names if s.stacks[n] > 0]
        if len(alive) < 2:
            s.over, s.hand_over, s.to_act = True, True, None
            s.result = f"{alive[0]} wins the tournament!"
            s.say("🏆 " + s.result)
            return
        s.hand_no += 1
        s.seats, m = alive, len(alive)
        i = s.names.index(s.dealer) if s.dealer else -1
        for k in range(1, 4):
            if s.names[(i + k) % 3] in alive:
                s.dealer = s.names[(i + k) % 3]
                break
        s.didx = d = alive.index(s.dealer)
        if m == 2: sb, bb, first = alive[d], alive[(d + 1) % 2], alive[d]
        else:      sb, bb, first = alive[(d + 1) % 3], alive[(d + 2) % 3], alive[d]
        s.deck = [r + u for r in "23456789TJQKA" for u in "HDCS"]
        random.shuffle(s.deck)
        s.hands = {n: [s.deck.pop(), s.deck.pop()] for n in alive}
        s.board, s.street, s.pot = [], "Pre-Flop", 0
        s.bets = {n: 0 for n in s.names}
        s.contrib = {n: 0 for n in s.names}
        s.active, s.acted, s.last = set(alive), set(), {}
        s.last_raise, s.hand_over, s.winners, s.result, s.showdown = BB, False, [], None, False
        s.pay(sb, min(SB, s.stacks[sb])); s.pay(bb, min(BB, s.stacks[bb]))
        s.cur = max(s.bets.values())
        s.say(f"— Hand {s.hand_no}: {s.dealer} has the button, {sb} posts {SB}, {bb} posts {BB}")
        s.pos = (alive.index(first) - 1) % m
        s.advance()

    def pay(s, p, x):
        s.stacks[p] -= x; s.bets[p] += x; s.contrib[p] += x; s.pot += x

    def advance(s):
        if len(s.active) == 1: return s.finish()
        can = [p for p in s.seats if p in s.active and s.stacks[p] > 0]
        if len(can) < 2 and all(s.bets[p] >= s.cur for p in can): return s.next_street()
        m = len(s.seats)
        for k in range(1, m + 1):
            p = s.seats[(s.pos + k) % m]
            if p in can and (p not in s.acted or s.bets[p] < s.cur):
                s.to_act = p
                return
        s.next_street()

    def next_street(s):
        s.bets = {n: 0 for n in s.names}
        s.cur, s.acted, s.last_raise, s.last, s.to_act = 0, set(), BB, {}, None
        s.pos = s.didx
        if s.street == "River": return s.finish(True)
        s.street = {"Pre-Flop": "Flop", "Flop": "Turn", "Turn": "River"}[s.street]
        s.deck.pop()
        s.board += [s.deck.pop() for _ in range(3 if s.street == "Flop" else 1)]
        s.say(f"{s.street}: " + " ".join(s.board))
        s.advance()

    def finish(s, showdown=False):
        s.hand_over, s.to_act = True, None
        s.showdown = showdown and len(s.active) > 1
        if len(s.active) == 1:
            w = next(iter(s.active))
            s.stacks[w] += s.pot
            s.winners, s.result = [w], f"{w} wins {s.pot} - everyone else folded"
        else:
            res = {p: best(s.hands[p] + s.board) for p in s.active}
            c, won = dict(s.contrib), Counter()
            while any(v > 0 for v in c.values()):
                lv = min(v for v in c.values() if v > 0)
                pot, el = 0, []
                for p in c:
                    t = min(lv, c[p]); c[p] -= t; pot += t
                    if t and p in s.active: el.append(p)
                el = el or list(s.active)
                top = max(res[p] for p in el)
                ws = [p for p in el if res[p] == top]
                for w in ws: won[w] += pot // len(ws)
                won[ws[0]] += pot % len(ws)
            for w, v in won.items(): s.stacks[w] += v
            s.winners = list(won)
            s.result = "; ".join(f"{w} wins {v} with {CATS[res[w][0]]}" for w, v in won.items())
        s.say("🏆 " + s.result)
        for n in s.names:
            if s.stacks[n] == 0 and n in s.seats: s.say(f"{n} is out of chips")

    # ---------- actions ----------
    def legal(s, p):
        mx = s.stacks[p] + s.bets[p]
        return min(s.cur - s.bets[p], s.stacks[p]), min(s.cur + max(s.last_raise, BB), mx), mx

    def act(s, p, action, amount=0):
        call, mn, mx = s.legal(p)
        if action == "raise" and mx <= s.cur: action = "call"
        if action == "check" and call > 0: action = "call"
        if action == "fold":
            s.active.discard(p); txt = "folds"
        elif action in ("call", "check"):
            s.pay(p, call)
            txt = "checks" if call == 0 else f"calls {call}"
        else:
            to = max(mn, min(int(amount), mx))
            if to >= mn: s.last_raise = max(s.last_raise, to - s.cur)
            txt = ("bets " if s.cur == 0 else "raises to ") + str(to)
            s.pay(p, to - s.bets[p]); s.cur = to; s.acted = set()
        if s.stacks[p] == 0 and action != "fold": txt += " (all-in)"
        s.last[p] = txt
        s.say(f"{p} {txt}")
        s.acted.add(p); s.pos = s.seats.index(p); s.to_act = None
        s.advance()

    def strength(s, p):
        h = s.hands[p]
        if not s.board:
            a, b = sorted((RV[c[0]] for c in h), reverse=True)
            v = (a + b) / 28 + (0.35 if a == b else 0) + (0.06 if h[0][1] == h[1][1] else 0) + (0.05 if a - b <= 2 else 0)
            return min(v, 1.0)
        return [0.15, 0.5, 0.68, 0.8, 0.86, 0.9, 0.95, 0.98, 1.0][best(h + s.board)[0]]

    def ai(s, p):
        mv = _llm_move(s, p)
        if mv: return mv
        st, (call, mn, mx) = s.strength(p), s.legal(p)
        alpha = p == "Alpha"
        odds = call / (s.pot + call) if call else 0
        bluff = alpha and random.random() < 0.22 and call < 0.25 * s.stacks[p]
        if st >= (0.62 if alpha else 0.78) or bluff:
            size = int(s.pot * (0.75 if st >= 0.8 else 0.5)) // 10 * 10
            return "raise", max(mn, s.cur + size)
        if call == 0: return "check", 0
        if st >= 0.25 + odds - (0.1 if alpha else 0.0): return "call", 0
        return "fold", 0

    # ---------- view ----------
    def label(s):
        h = s.hands.get("You")
        if not h or "You" not in s.active: return ""
        if len(s.board) >= 3: return CATS[best(h + s.board)[0]]
        return "Pair" if h[0][0] == h[1][0] else "High Card"

    def state(s):
        me = "You"
        live = me in s.active and s.stacks[me] > 0 and not s.hand_over
        call, mn, mx = s.legal(me) if live else (0, 0, 0)
        pl = []
        for n in s.names:
            inh = n in s.seats
            if inh and n in s.active and not s.hand_over or (s.hand_over and n in s.active):
                cards = s.hands[n] if (n == me or s.showdown) else ["??", "??"]
            else:
                cards = []
            pl.append(dict(name=n, stack=s.stacks[n], bet=s.bets[n], cards=cards, dealer=n == s.dealer and inh,
                           folded=inh and n not in s.active, out=not inh, allin=inh and n in s.active and s.stacks[n] == 0,
                           last=s.last.get(n, ""), winner=n in s.winners and s.hand_over))
        return dict(hand_no=s.hand_no, street=s.street, pot=s.pot, board=s.board, players=pl, to_act=s.to_act,
                    hand_over=s.hand_over, over=s.over, result=s.result, call=call, min_raise=mn, max_raise=mx,
                    cur=s.cur, your_bet=s.bets[me], label=s.label(), log=s.log[-30:], bb=BB)
