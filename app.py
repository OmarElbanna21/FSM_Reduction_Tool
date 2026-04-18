#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  FSM State Reduction & Synthesis Tool — Flask Backend                        ║
║  Digital Logic Circuits II | Alexandria University                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Run:
    pip install flask
    python app.py
Then open http://localhost:5000 in your browser.

API Endpoints:
    POST /api/reduce   → full reduction pipeline
    POST /api/assign   → state assignment (given reduced table)
    POST /api/verify   → equivalence verification
"""

from flask import Flask, request, jsonify, send_file
import math, random, itertools, json, os
from dataclasses import dataclass, field
from typing import Optional

app = Flask(__name__)

# ── CORS for local dev ────────────────────────────────────────────────────────
@app.after_request
def add_cors(r):
    r.headers['Access-Control-Allow-Origin']  = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    r.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return r

@app.route('/options', methods=['OPTIONS'])
def options(): return '', 204

# ══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def is_dc(v):
    """Return True if v represents a don't-care (single or multi-bit: '-', '--', 'xx', etc.)"""
    if not v: return True
    s = str(v).strip().lower()
    if not s: return True
    # Known single-char DC tokens
    if s in ('-', 'x', '*'): return True
    # Multi-bit DC: every character is a DC indicator
    return all(c in '-x*,' for c in s.replace(' ', ''))

def outputs_compat(z1, z2):
    """
    Two output values are compatible if:
    - Either is fully DC ('−', '--', 'xx', etc.)
    - Both are equal as strings
    - Per-bit: each bit position is DC or equal (for '0-' vs '01' style)
    """
    if is_dc(z1) or is_dc(z2): return True
    s1, s2 = str(z1).strip(), str(z2).strip()
    if s1 == s2: return True
    # Per-bit comparison for equal-length multi-bit strings
    if len(s1) == len(s2):
        return all(
            c1 in '-x*X' or c2 in '-x*X' or c1 == c2
            for c1, c2 in zip(s1, s2)
        )
    return False

def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count('1')

def are_adjacent(a: int, b: int) -> bool:
    return hamming(a, b) == 1

def pair_key(a: int, b: int) -> tuple:
    return (max(a, b), min(a, b))


# ══════════════════════════════════════════════════════════════════════════════
#  UNREACHABLE STATE REMOVAL
# ══════════════════════════════════════════════════════════════════════════════

def remove_unreachable_states(states: list) -> tuple:
    """
    BFS from the first state to find all reachable states.
    Don't-care next states are skipped.
    Returns (reachable_states, removed_names_list).
    """
    if not states:
        return [], []

    state_map = {s['name']: s for s in states}
    start     = states[0]['name']
    reachable = {start}
    queue     = [start]

    while queue:
        curr = queue.pop(0)
        s    = state_map.get(curr)
        if s is None:
            continue
        for ns in s['next_states']:
            if not is_dc(ns) and ns in state_map and ns not in reachable:
                reachable.add(ns)
                queue.append(ns)

    filtered = [s for s in states if s['name'] in reachable]
    removed  = [s['name'] for s in states if s['name'] not in reachable]
    return filtered, removed


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 1 — ROW MATCHING
# ══════════════════════════════════════════════════════════════════════════════

def outputs_equal(z1, z2) -> bool:
    """Strict equality for row-matching: both DC, or both same specific value."""
    dc1, dc2 = is_dc(z1), is_dc(z2)
    if dc1 and dc2: return True
    if dc1 or dc2: return False
    return str(z1).strip() == str(z2).strip()


def row_matching(states: list) -> tuple:
    """
    Iterative row matching: repeat until no identical rows remain.
    Supports Moore (single output) and Mealy (per-input outputs list).
    Returns: (remaining_states, removed_dict_all_passes)
    """
    def rows_identical(s1: dict, s2: dict) -> bool:
        # Compare outputs — Mealy uses 'outputs' list, Moore uses 'output'
        o1 = s1.get('outputs') or [s1.get('output', '-')]
        o2 = s2.get('outputs') or [s2.get('output', '-')]
        if len(o1) != len(o2): return False
        # Strict equality: DC only matches DC
        if not all(outputs_equal(a, b) for a, b in zip(o1, o2)): return False
        # Compare next states (DC matches DC only)
        for a, b in zip(s1['next_states'], s2['next_states']):
            if is_dc(a) and is_dc(b): continue
            if is_dc(a) or is_dc(b): return False
            if a != b: return False
        return True

    total_removed = {}
    current = [{**s, 'next_states': list(s['next_states'])} for s in states]

    while True:
        removed = {}
        kept    = []

        for s in current:
            canon = next((k for k in kept if rows_identical(k, s)), None)
            if canon:
                removed[s['name']] = canon['name']
            else:
                kept.append({**s, 'next_states': list(s['next_states'])})

        if not removed:
            break   # no more identical rows

        def rep(n: str) -> str:
            x = n
            while x in removed: x = removed[x]
            return x

        # Update NS of kept states and accumulate removals
        for s in kept:
            s['next_states'] = [v if is_dc(v) else rep(v) for v in s['next_states']]
        for rem, can in removed.items():
            total_removed[rem] = rep(can)

        current = kept

    return current, total_removed


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 2 — IMPLICATION TABLE
# ══════════════════════════════════════════════════════════════════════════════

def build_implication_table(states: list, ni: int, is_mealy: bool = False) -> tuple:
    """
    Build and solve the implication table.
    is_mealy: if True, checks per-input outputs (state['outputs'] list).
    Self-loop implied pairs are skipped (pair cannot imply itself).
    Returns (cells_dict, passes_list).
    """
    n = len(states)
    idx = {s['name']: i for i, s in enumerate(states)}
    cells = {}

    # Pass 0 — output comparison
    p0_new = []
    for i in range(1, n):
        for j in range(i):
            si, sj = states[i], states[j]
            k = pair_key(i, j)
            cell = {'i': i, 'j': j, 'status': 'compat', 'implied': [], 'marked_pass': -1}

            # Output incompatibility check
            out_incompat = False
            if is_mealy:
                # Mealy: check per-input output compatibility
                oi = si.get('outputs') or [si.get('output', '-')] * ni
                oj = sj.get('outputs') or [sj.get('output', '-')] * ni
                for x in range(ni):
                    z1 = oi[x] if x < len(oi) else '-'
                    z2 = oj[x] if x < len(oj) else '-'
                    if not outputs_compat(z1, z2):
                        out_incompat = True
                        break
            else:
                out_incompat = not outputs_compat(si['output'], sj['output'])

            if out_incompat:
                cell['status'] = 'ic_out'
                cell['marked_pass'] = 0
                p0_new.append(list(k))
            else:
                seen = set()
                for x in range(ni):
                    ns1, ns2 = si['next_states'][x], sj['next_states'][x]
                    if is_dc(ns1) or is_dc(ns2): continue
                    ai, bi = idx.get(ns1, -1), idx.get(ns2, -1)
                    if ai < 0 or bi < 0 or ai == bi: continue
                    pk = pair_key(ai, bi)
                    if pk == k: continue           # skip self-reference
                    if pk not in seen:
                        seen.add(pk)
                        cell['implied'].append(list(pk))
            cells[k] = cell

    passes = [p0_new]

    # Propagation passes
    pn = 1
    while True:
        newly = []
        for k, c in cells.items():
            if c['status'] != 'compat': continue
            for imp in c['implied']:
                ik = tuple(imp)
                if cells.get(ik, {}).get('status', 'compat') != 'compat':
                    c['status'] = 'ic_prop'
                    c['marked_pass'] = pn
                    newly.append(list(k))
                    break
        passes.append(newly)
        if not newly: break
        pn += 1

    return cells, passes


def get_equiv_classes(cells: dict, states: list) -> list:
    """Extract equivalence classes via Union-Find."""
    n = len(states)
    p = list(range(n))

    def find(x):
        while p[x] != x: p[x] = p[p[x]]; x = p[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry: p[rx] = ry

    for k, c in cells.items():
        if c['status'] == 'compat': union(c['i'], c['j'])

    cm = {}
    for i in range(n):
        cm.setdefault(find(i), []).append(states[i]['name'])

    result = list(cm.values())
    result.sort(key=lambda cls: next(i for i, s in enumerate(states) if s['name'] == cls[0]))
    return result


def _bron_kerbosch(R: set, P: set, X: set, adj: dict, cliques: list) -> None:
    """Find all maximal cliques via Bron-Kerbosch with pivoting."""
    if not P and not X:
        cliques.append(frozenset(R))
        return
    u = max(P | X, key=lambda v: len(adj.get(v, set()) & P))
    for v in list(P - adj.get(u, set())):
        _bron_kerbosch(R | {v}, P & adj.get(v, set()), X & adj.get(v, set()), adj, cliques)
        P.remove(v)
        X.add(v)


def get_compatible_classes(cells: dict, states: list) -> list:
    """
    For incompletely specified networks: find a minimum cover using
    maximal compatible classes (Bron-Kerbosch + greedy set cover).

    Returns a list of state-name lists representing the chosen cover.
    """
    names = [s['name'] for s in states]
    name_set = set(names)

    # Build adjacency from compatible pairs
    adj: dict = {n: set() for n in names}
    for c in cells.values():
        if c['status'] == 'compat':
            a, b = states[c['i']]['name'], states[c['j']]['name']
            adj[a].add(b)
            adj[b].add(a)

    # Find all maximal cliques
    cliques: list = []
    _bron_kerbosch(set(), set(names), set(), adj, cliques)

    # Greedy minimum set cover
    # Prefer: most uncovered states covered first; tie-break by fewest already-covered states
    covered: set = set()
    chosen: list = []
    remaining_cliques = list(cliques)

    while covered < name_set:
        uncovered = name_set - covered
        # Score = (#uncovered covered, -#already covered) → prefer more new coverage
        def score(c):
            new = len(c & uncovered)
            old = len(c & covered)
            return (new, -old)
        best = max(remaining_cliques, key=score)
        new_coverage = best & uncovered
        if not new_coverage:
            # No clique covers anything new — add singletons
            for s in sorted(uncovered, key=lambda n: next(i for i,x in enumerate(names) if x==n)):
                chosen.append(frozenset({s}))
            break
        chosen.append(best)
        covered |= new_coverage

    # Convert to sorted lists, preserving state order
    order = {n: i for i, n in enumerate(names)}
    result = [sorted(list(c), key=lambda n: order.get(n, 999)) for c in chosen]
    result.sort(key=lambda cls: order.get(cls[0], 999))
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 3 — PARTITIONING METHOD
# ══════════════════════════════════════════════════════════════════════════════

def has_incomplete_ns(states: list) -> bool:
    """Return True if any state has a Don't-Care next state (incompletely specified)."""
    for s in states:
        for ns in s.get('next_states', []):
            if is_dc(ns):
                return True
    return False


def partitioning_method(states: list, ni: int) -> list:
    """Iterative partition refinement. Returns list of step objects."""
    steps = []

    out_map: dict = {}
    for s in states:
        # Mealy: group by all per-input outputs joined; Moore: single output
        if s.get('outputs'):
            zval = '/'.join(str(z) for z in s['outputs'])
        else:
            zval = s.get('output', '-')
        k = '-' if is_dc(zval) else zval
        out_map.setdefault(k, []).append(s['name'])
    partition = list(out_map.values())

    def group_of(name, part):
        for gi, g in enumerate(part):
            if name in g: return gi
        return -1

    def same_part(p1, p2):
        s1 = sorted(['|'.join(sorted(g)) for g in p1])
        s2 = sorted(['|'.join(sorted(g)) for g in p2])
        return s1 == s2

    steps.append({'pass': 0, 'partition': [list(g) for g in partition],
                  'reason': 'Initial: group by output Z', 'converged': False})

    for it in range(1, 30):
        new_part = []
        for group in partition:
            submap: dict = {}
            for sname in group:
                s = next(x for x in states if x['name'] == sname)
                sig = ','.join('*' if is_dc(ns) else str(group_of(ns, partition))
                               for ns in s['next_states'])
                submap.setdefault(sig, []).append(sname)
            new_part.extend(submap.values())

        if same_part(partition, new_part):
            steps.append({'pass': it, 'partition': [list(g) for g in new_part],
                          'reason': 'No refinement — Converged ✓', 'converged': True})
            break
        partition = new_part
        steps.append({'pass': it, 'partition': [list(g) for g in partition],
                      'reason': 'Refined by next-state group signatures', 'converged': False})

    return steps


def build_reduced_table(states: list, classes: list, ni: int) -> list:
    labels = [chr(65 + i) for i in range(len(classes))]
    s2l = {n: lbl for cls, lbl in zip(classes, labels) for n in cls}
    result = []
    for cls, lbl in zip(classes, labels):
        rep = next(s for s in states if s['name'] == cls[0])
        row = {
            'name': lbl, 'members': cls,
            'next_states': ['-' if is_dc(ns) else s2l.get(ns, ns) for ns in rep['next_states']],
            'output': rep.get('output', '-'),
        }
        if rep.get('outputs'):
            row['outputs'] = rep['outputs']   # Mealy per-input outputs
        result.append(row)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 4 — STATE ASSIGNMENT  (3-Rule Scoring)
# ══════════════════════════════════════════════════════════════════════════════

def compute_pair_scores(states: list, ni: int) -> tuple:
    """
    Compute adjacency score for every state pair using 3 rules:
      Rule 1 (+3): same next state for any input
      Rule 2 (+2): both are next states of the same state
      Rule 3 (+1): same output
    Returns: (n×n score matrix, log_entries)
    """
    n = len(states)
    scores = [[0] * n for _ in range(n)]
    log = []

    for i in range(n):
        for j in range(i + 1, n):
            si, sj = states[i], states[j]
            score = 0
            reasons = []

            # Rule 1
            for x in range(ni):
                ns1, ns2 = si['next_states'][x], sj['next_states'][x]
                if not is_dc(ns1) and not is_dc(ns2) and ns1 == ns2:
                    score += 3
                    reasons.append(
                        f"Rule 1 (+3): NS({si['name']}, X={x}) = "
                        f"NS({sj['name']}, X={x}) = {ns1}"
                    )

            # Rule 2
            for sk in states:
                ns_set = {v for v in sk['next_states'] if not is_dc(v)}
                if si['name'] in ns_set and sj['name'] in ns_set:
                    score += 2
                    reasons.append(
                        f"Rule 2 (+2): Both {si['name']} and {sj['name']} "
                        f"are NS of {sk['name']}"
                    )
                    break

            # Rule 3
            if (not is_dc(si['output']) and not is_dc(sj['output'])
                    and si['output'] == sj['output']):
                score += 1
                reasons.append(
                    f"Rule 3 (+1): Z({si['name']}) = Z({sj['name']}) = {si['output']}"
                )

            scores[i][j] = scores[j][i] = score
            if reasons:
                log.append({'pair': (si['name'], sj['name']),
                            'score': score, 'reasons': reasons})

    return scores, log


def find_best_assignments(states: list, pair_scores: list, n_best: int = 3) -> list:
    """
    Try all (or sampled) binary code assignments.
    Returns top n_best assignments with scores, sorted best first.
    """
    n   = len(states)
    k   = max(1, math.ceil(math.log2(n))) if n > 1 else 1
    tot = 2 ** k

    def eval_assign(perm: tuple) -> int:
        return sum(pair_scores[i][j]
                   for i in range(n) for j in range(i + 1, n)
                   if are_adjacent(perm[i], perm[j]))

    results = []
    all_codes = list(range(tot))
    limit = 80_000

    if n <= 9:
        count = 0
        for combo in itertools.combinations(all_codes, n):
            for perm in itertools.permutations(combo):
                results.append((eval_assign(perm), perm))
                count += 1
                if count >= limit: break
            if count >= limit: break
    else:
        for _ in range(limit):
            perm = tuple(random.sample(all_codes, n))
            results.append((eval_assign(perm), perm))

    results.sort(key=lambda x: -x[0])

    seen = set()
    unique = []
    for score, perm in results:
        if perm not in seen:
            seen.add(perm)
            unique.append({'score': score, 'assignment': list(perm)})
            if len(unique) >= n_best: break

    for r in unique:
        r['mapping']  = {states[i]['name']: format(r['assignment'][i], f'0{k}b')
                         for i in range(n)}
        r['n_bits']   = k
        r['adjacency_details'] = _adjacency_details(states, pair_scores, r['assignment'], k)

    return unique


def _adjacency_details(states, scores, assignment, k):
    """Return list of adjacent pairs with scores for tooltip/log."""
    n = len(states)
    details = []
    for i in range(n):
        for j in range(i + 1, n):
            if are_adjacent(assignment[i], assignment[j]) and scores[i][j] > 0:
                details.append({
                    'state_a': states[i]['name'],
                    'code_a':  format(assignment[i], f'0{k}b'),
                    'state_b': states[j]['name'],
                    'code_b':  format(assignment[j], f'0{k}b'),
                    'score':   scores[i][j],
                })
    return details


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 5 — TRANSITION TABLE
# ══════════════════════════════════════════════════════════════════════════════

def generate_transition_table(states: list, mapping: dict, ni: int) -> tuple:
    """
    Build the full binary transition table.
    Returns (rows, k) where rows includes used and unused (don't-care) entries.
    """
    k = len(next(iter(mapping.values())))
    n2c = {nm: int(code, 2) for nm, code in mapping.items()}
    used_codes = set(mapping.values())
    all_codes  = [format(i, f'0{k}b') for i in range(2 ** k)]

    rows = []

    for s in states:
        bin_code = mapping[s['name']]
        is_mealy_state = bool(s.get('outputs'))
        for x in range(ni):
            ns = s['next_states'][x]
            ns_bin = '-' * k if is_dc(ns) else mapping.get(ns, '-' * k)
            # Mealy: per-input output; Moore: state output
            if is_mealy_state and x < len(s['outputs']):
                out_val = s['outputs'][x]
            else:
                out_val = s.get('output', '-')
            rows.append({
                'ps_name': s['name'],
                'ps_bin':  bin_code,
                'input':   x,
                'ns_name': ns,
                'ns_bin':  ns_bin,
                'output':  out_val,
                'unused':  False,
                'd_bits':  list(ns_bin),
            })

    for code in all_codes:
        if code not in used_codes:
            for x in range(ni):
                rows.append({
                    'ps_name': '(unused)',
                    'ps_bin':  code,
                    'input':   x,
                    'ns_name': '-',
                    'ns_bin':  '-' * k,
                    'output':  '-',
                    'unused':  True,
                    'd_bits':  ['-'] * k,
                })

    rows.sort(key=lambda r: (int(r['ps_bin'].replace('-', '0'), 2), r['input']))
    return rows, k


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 6 — QUINE-McCLUSKEY MINIMIZATION
# ══════════════════════════════════════════════════════════════════════════════

def qm_minimize(minterms: list, dontcares: list, n_vars: int) -> list:
    """
    Full Q-M prime implicant extraction + greedy essential cover.
    Term representation: (value_int, dash_bitmask).
    A bit position b is 'dashed' (don't care) when (dash >> b) & 1 == 1.
    """
    if not minterms:
        return []
    all_terms = set(minterms) | set(dontcares)
    if len(all_terms) == 2 ** n_vars:
        return [(0, (1 << n_vars) - 1)]

    mask = (1 << n_vars) - 1

    def count_ones(val: int, dash: int) -> int:
        return bin(val & ~dash & mask).count('1')

    current: dict = {}
    for m in all_terms:
        current.setdefault(count_ones(m, 0), set()).add((m, 0))

    prime_implicants: set = set()

    while True:
        nxt: dict = {}
        combined: set = set()
        groups = sorted(current)
        for i in range(len(groups) - 1):
            for (v1, d1) in current[groups[i]]:
                for (v2, d2) in current[groups[i + 1]]:
                    if d1 != d2: continue
                    xr = v1 ^ v2
                    if xr == 0 or (xr & (xr - 1)) != 0: continue
                    nd = d1 | xr
                    nv = v1 & ~xr & mask
                    nxt.setdefault(count_ones(nv, nd), set()).add((nv, nd))
                    combined.add((v1, d1))
                    combined.add((v2, d2))
        for terms in current.values():
            for t in terms:
                if t not in combined:
                    prime_implicants.add(t)
        if not nxt:
            break
        current = nxt

    # covers(pi, m): pi covers minterm m iff for every non-dashed bit, values agree
    def covers(pi: tuple, m: int) -> bool:
        val, dash = pi
        for b in range(n_vars):
            if (dash >> b) & 1:        # dashed → skip
                continue
            if ((val >> b) & 1) != ((m >> b) & 1):
                return False
        return True

    pis = list(prime_implicants)
    minterm_set = set(minterms)
    covered: set = set()
    selected: list = []

    # Essential PIs
    for m in minterm_set:
        cov = [pi for pi in pis if covers(pi, m)]
        if len(cov) == 1 and cov[0] not in selected:
            selected.append(cov[0])
            covered |= {mm for mm in minterm_set if covers(cov[0], mm)}

    # Greedy cover of remaining
    rem_m  = minterm_set - covered
    rem_pi = [pi for pi in pis if pi not in selected]
    while rem_m and rem_pi:
        best = max(rem_pi, key=lambda pi: len({m for m in rem_m if covers(pi, m)}))
        newly = {m for m in rem_m if covers(best, m)}
        if not newly:
            break
        selected.append(best)
        covered |= newly
        rem_m  -= newly
        rem_pi  = [p for p in rem_pi if p != best]

    return selected


def pi_to_expr(pi: tuple, var_names: list) -> str:
    """Convert a prime implicant (val, dash) to a Boolean expression string."""
    val, dash = pi
    n = len(var_names)
    terms = []
    for bit in range(n - 1, -1, -1):          # MSB first
        if (dash >> bit) & 1:
            continue                            # dashed bit → skip
        vn = var_names[n - 1 - bit]
        terms.append(vn if (val >> bit) & 1 else f"{vn}'")
    return ''.join(terms) if terms else '1'


# ══════════════════════════════════════════════════════════════════════════════
#  STEP 7 — EXCITATION EQUATIONS
# ══════════════════════════════════════════════════════════════════════════════

def generate_excitation_equations(states: list, mapping: dict,
                                   ni: int, ff_type: str = 'D') -> dict:
    """
    Generate D flip-flop excitation equations and Moore output equation Z.

    Encoding:
      k            = number of state bits  (len of binary code string)
      n_input_bits = ceil(log2(ni)) for ni > 1, else 0
                     (ni=2 → 1-bit input X; ni=1 → no input variable)
      n_vars       = k + n_input_bits
      minterm index for (ps_int, x): (ps_int << n_input_bits) | x

    FF labelling: D{b} is the excitation of flip-flop Q{b},
      where Q{k-1} is the MSB and Q{0} is the LSB.
    """
    k            = len(next(iter(mapping.values())))
    n2c          = {nm: int(code, 2) for nm, code in mapping.items()}
    tot          = 2 ** k
    n_input_bits = max(1, math.ceil(math.log2(ni))) if ni > 1 else 0
    n_vars       = k + n_input_bits

    # Variable names: Q_{k-1} … Q_0  then  X  (or X_0,X_1,… for ni>2)
    q_vars = [f'Q{k - 1 - b}' for b in range(k)]
    if n_input_bits == 0:
        x_vars = []
    elif n_input_bits == 1:
        x_vars = ['X']
    else:
        x_vars = [f'X{i}' for i in range(n_input_bits)]
    all_vars = q_vars + x_vars

    equations: dict = {}

    # ── D flip-flops ──────────────────────────────────────────────────────────
    # D{b} = next value of Q{b} = bit b of next-state code (b=0 is LSB)
    for bit in range(k):
        ff          = f'D{bit}'
        minterms: list  = []
        dontcares: list = []

        for ps_int in range(tot):
            sname = next((nm for nm, c in n2c.items() if c == ps_int), None)

            for x in range(ni):
                m_idx = (ps_int << n_input_bits) | x

                if sname is None:
                    dontcares.append(m_idx); continue

                s = next((st for st in states if st['name'] == sname), None)
                if s is None:
                    dontcares.append(m_idx); continue

                ns = s['next_states'][x]          # direct index into ni-column table
                if is_dc(ns):
                    dontcares.append(m_idx); continue

                ns_code = n2c.get(ns)
                if ns_code is None:
                    dontcares.append(m_idx); continue

                if (ns_code >> bit) & 1:
                    minterms.append(m_idx)

        pis   = qm_minimize(minterms, dontcares, n_vars)
        total = len(set(minterms) | set(dontcares))

        if not minterms:
            eq = '0'
        elif total == 2 ** n_vars:
            eq = '1'
        elif pis:
            eq = ' + '.join(pi_to_expr(pi, all_vars) for pi in pis)
        else:
            eq = '0'

        equations[ff] = {
            'equation':  eq,
            'minterms':  sorted(set(minterms)),
            'dontcares': sorted(set(dontcares)),
            'n_vars':    n_vars,
            'var_names': all_vars,
            'display':   f'{ff} = {eq}',
        }

    # ── Output Z ─────────────────────────────────────────────────────────────
    # Mealy: Z depends on (state, input) → use per-input outputs[x]
    # Moore: Z depends on state only → use s['output'], replicated across inputs
    is_mealy_mode = any(s.get('outputs') for s in states)
    z_mt: list  = []
    z_dc: list  = []

    for ps_int in range(tot):
        sname = next((nm for nm, c in n2c.items() if c == ps_int), None)
        for x in range(ni):
            m_idx = (ps_int << n_input_bits) | x
            if sname is None:
                z_dc.append(m_idx); continue
            s = next((st for st in states if st['name'] == sname), None)
            if s is None:
                z_dc.append(m_idx); continue

            if is_mealy_mode:
                outputs_list = s.get('outputs') or []
                z_val = outputs_list[x] if x < len(outputs_list) else '-'
            else:
                z_val = s.get('output', '-')

            if is_dc(z_val):
                z_dc.append(m_idx); continue
            try:
                if int(z_val):
                    z_mt.append(m_idx)
                # output 0 → not a minterm (stays as 0)
            except (ValueError, TypeError):
                z_dc.append(m_idx)

    z_pis  = qm_minimize(z_mt, z_dc, n_vars)
    z_total = len(set(z_mt) | set(z_dc))

    if not z_mt:
        z_eq = '0'
    elif z_total == 2 ** n_vars:
        z_eq = '1'
    elif z_pis:
        z_eq = ' + '.join(pi_to_expr(pi, all_vars) for pi in z_pis)
    else:
        z_eq = '0'

    equations['Z'] = {
        'equation':  z_eq,
        'minterms':  sorted(set(z_mt)),
        'dontcares': sorted(set(z_dc)),
        'n_vars':    n_vars,
        'var_names': all_vars,
        'display':   f'Z = {z_eq}',
    }

    return equations


# ══════════════════════════════════════════════════════════════════════════════
#  VERIFICATION — simulate both FSMs on random inputs
# ══════════════════════════════════════════════════════════════════════════════

def simulate_fsm(states: list, start: str, inputs: list, ni: int) -> list:
    smap = {s['name']: s for s in states}
    cur  = start
    outs = []
    for x in inputs:
        s = smap.get(cur)
        if not s: break
        outs.append(s['output'])
        ns = s['next_states'][x % ni]
        if is_dc(ns): break
        cur = ns
    return outs


def verify_equivalence(orig: list, reduced: list, ni: int, trials: int = 6,
                        steps: int = 25) -> dict:
    """Run both FSMs on the same random input sequences and compare outputs."""
    results = []
    all_passed = True

    # Build state-name map for reduced (A→first member, etc.)
    red_to_orig = {}  # reduced label → original state name
    for r in reduced:
        red_to_orig[r['name']] = r['members'][0]

    # Start state: first state of each
    orig_start = orig[0]['name']
    red_start  = reduced[0]['name']

    for trial in range(trials):
        seq = [random.randint(0, ni - 1) for _ in range(steps)]
        orig_out = simulate_fsm(orig,    orig_start, seq, ni)
        red_out  = simulate_fsm(reduced, red_start,  seq, ni)

        min_len = min(len(orig_out), len(red_out))
        mm = sum(1 for a, b in zip(orig_out[:min_len], red_out[:min_len]) if a != b)

        passed = (mm == 0)
        if not passed: all_passed = False

        results.append({
            'trial':           trial + 1,
            'input_seq':       seq[:8],
            'orig_outputs':    orig_out[:8],
            'reduced_outputs': red_out[:8],
            'mismatches':      mm,
            'passed':          passed,
        })

    return {'trials': results, 'all_passed': all_passed,
            'n_trials': trials, 'steps': steps}



# ══════════════════════════════════════════════════════════════════════════════
#  J-K EXCITATION EQUATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _generate_jk_excitation(states: list, mapping: dict, ni: int) -> dict:
    """
    Generate J-K flip-flop excitation equations.
    J_b minterms: Q_b=0 → NS_b=1  (0→1 transition)
    K_b minterms: Q_b=1 → NS_b=0  (1→0 transition)
    All other entries are Don't Care.
    """
    import math as _math
    k           = len(next(iter(mapping.values())))
    n2c         = {nm: int(code, 2) for nm, code in mapping.items()}
    tot         = 2 ** k
    n_input_bits = max(1, _math.ceil(_math.log2(ni))) if ni > 1 else 0
    n_vars       = k + n_input_bits
    q_vars       = [f'Q{k-1-b}' for b in range(k)]
    x_vars       = [] if n_input_bits == 0 else (['X'] if n_input_bits == 1
                    else [f'X{i}' for i in range(n_input_bits)])
    all_vars     = q_vars + x_vars
    equations    = {}

    for bit in range(k):
        j_mt, j_dc, k_mt, k_dc = [], [], [], []

        for ps_int in range(tot):
            sname   = next((nm for nm, c in n2c.items() if c == ps_int), None)
            ps_bit  = (ps_int >> bit) & 1

            for x in range(ni):
                m_idx = (ps_int << n_input_bits) | x

                if sname is None:
                    j_dc.append(m_idx); k_dc.append(m_idx); continue

                s = next((st for st in states if st['name'] == sname), None)
                if s is None:
                    j_dc.append(m_idx); k_dc.append(m_idx); continue

                ns = s['next_states'][x]
                if is_dc(ns):
                    j_dc.append(m_idx); k_dc.append(m_idx); continue

                ns_code = n2c.get(ns)
                if ns_code is None:
                    j_dc.append(m_idx); k_dc.append(m_idx); continue

                ns_bit = (ns_code >> bit) & 1

                if ps_bit == 0:
                    if ns_bit == 1: j_mt.append(m_idx)   # 0→1 : J=1
                    k_dc.append(m_idx)                    # Q=0  : K=x
                else:
                    j_dc.append(m_idx)                    # Q=1  : J=x
                    if ns_bit == 0: k_mt.append(m_idx)   # 1→0 : K=1

        for ff_name, mt, dc in [(f'J{bit}', j_mt, j_dc), (f'K{bit}', k_mt, k_dc)]:
            pis   = qm_minimize(mt, dc, n_vars)
            total = len(set(mt) | set(dc))
            if not mt:        eq = '0'
            elif total == 2 ** n_vars: eq = '1'
            elif pis:         eq = ' + '.join(pi_to_expr(pi, all_vars) for pi in pis)
            else:             eq = '0'
            equations[ff_name] = {
                'equation':  eq,
                'minterms':  sorted(set(mt)),
                'dontcares': sorted(set(dc)),
                'n_vars':    n_vars,
                'var_names': all_vars,
                'display':   f'{ff_name} = {eq}',
            }

    return equations

# ══════════════════════════════════════════════════════════════════════════════
#  FLASK ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    # Try to serve index.html from same directory
    for path in ['index.html', 'templates/index.html']:
        if os.path.exists(path):
            return send_file(path)
    return ("<h2>Place index.html in the same folder as app.py</h2>"
            "<p>Then restart the server.</p>"), 404


@app.route('/api/ping')
def ping():
    return jsonify({'status': 'ok', 'version': '2.2'})


@app.route('/api/reduce', methods=['POST', 'OPTIONS'])
def api_reduce():
    if request.method == 'OPTIONS': return '', 204
    try:
        data      = request.get_json(force=True)
        raw       = data.get('states', [])
        ni        = int(data.get('num_inputs', 2))
        n_best    = int(data.get('n_best', 10))
        is_mealy  = bool(data.get('is_mealy', False))

        # ── Input Validation ──────────────────────────────────────
        if len(raw) < 2:
            return jsonify({'error': 'Need at least 2 states'}), 400

        names = {s['name'] for s in raw}
        if len(names) != len(raw):
            return jsonify({'error': 'Duplicate state names detected'}), 400

        for s in raw:
            if not s.get('name', '').strip():
                return jsonify({'error': 'Empty state name detected'}), 400
            for x, ns in enumerate(s.get('next_states', [])):
                if not is_dc(ns) and ns not in names:
                    return jsonify({'error': f'Unknown next state "{ns}" in row "{s["name"]}" (X={x})'}), 400

        # ── Pipeline ──────────────────────────────────────────────
        log = []
        mtype = 'Mealy' if is_mealy else 'Moore'
        log.append(f"Starting {mtype} reduction: {len(raw)} states, {ni} input column(s).")

        # 0. Remove unreachable states (skip for incomplete networks —
        #    DC transitions mean reachability is undetermined)
        if has_incomplete_ns(raw):
            reachable_raw = raw
            log.append("Incomplete network — unreachable state removal skipped (DC transitions).")
        else:
            reachable_raw, unreachable = remove_unreachable_states(raw)
            if unreachable:
                log.append(f"Unreachable states removed: {', '.join(unreachable)}")
            else:
                log.append("All states are reachable from the start state.")

        # 1. Row Matching
        rm_states, rm_removed = row_matching(reachable_raw)
        if rm_removed:
            log.append(f"Row matching removed {len(rm_removed)} redundant state(s): "
                       + ', '.join(f"{k}≡{v}" for k, v in rm_removed.items()))
        else:
            log.append("Row matching: no redundant rows found.")

        # 2. Implication Table
        cells, passes = build_implication_table(rm_states, ni, is_mealy)
        n_passes = len(passes) - 1
        log.append(f"Implication table converged in {n_passes} propagation pass(es).")

        # 3. Classes & Reduced Table
        #    For incomplete networks: use maximal compatible sets (not Union-Find)
        is_incomplete_check = has_incomplete_ns(rm_states)
        if is_incomplete_check:
            classes = get_compatible_classes(cells, rm_states)
            log.append(f"Compatible classes (incomplete network): {len(classes)}.  Reduced: {len(classes)} state(s).")
        else:
            classes = get_equiv_classes(cells, rm_states)
            log.append(f"Equivalent classes: {len(classes)}.  Reduced: {len(classes)} state(s).")
        reduced = build_reduced_table(rm_states, classes, ni)

        # 4. Partitioning (cross-check — only for fully specified networks)
        is_incomplete = has_incomplete_ns(rm_states)
        if is_incomplete:
            log.append("Incomplete network detected — partitioning method skipped.")
            part_steps = [{'pass': 0, 'partition': [[s['name'] for s in rm_states]],
                           'reason': 'Skipped: incompletely specified network', 'converged': False}]
        else:
            part_steps = partitioning_method(rm_states, ni)
            log.append("Partitioning method: cross-verification complete.")

        # 5. State assignment
        pair_scores, score_log = compute_pair_scores(reduced, ni)
        best_assigns = find_best_assignments(reduced, pair_scores, n_best)
        log.append(f"State assignment: evaluated assignments, best score = "
                   f"{best_assigns[0]['score'] if best_assigns else 0}.")

        # 6. Transition table + equations (best assignment, D and J-K)
        trans_rows = excitation = jk_excitation = None
        if best_assigns:   # synthesis applies to both Moore and Mealy
            best = best_assigns[0]
            trans_rows, k_bits = generate_transition_table(reduced, best['mapping'], ni)
            excitation = generate_excitation_equations(reduced, best['mapping'], ni)
            jk_excitation = _generate_jk_excitation(reduced, best['mapping'], ni)
            log.append(f"Excitation equations generated for {k_bits}-bit encoding.")


        # 7. Verification
        verify = verify_equivalence(
            [{'name': s['name'], 'next_states': s['next_states'], 'output': s['output']} for s in rm_states],
            reduced, ni
        )

        # Serialize cells (keys are tuples → convert to strings)
        cells_s = {f"{k[0]},{k[1]}": v for k, v in cells.items()}
        passes_s = [[pk if isinstance(pk, list) else list(pk) for pk in p] for p in passes]

        return jsonify({
            'success':    True,
            'log':        log,
            'raw_states': raw,   # original states before any reduction
            'row_matching': {
                'removed':      dict(rm_removed),
                'states_after': rm_states,
            },
            'implication_table': {
                'cells':   cells_s,
                'passes':  passes_s,
                'states':  rm_states,
            },
            'partitioning': part_steps,
            'classes':      classes,
            'reduced':      reduced,
            'state_assignment': {
                'pair_scores': pair_scores,
                'score_log':   [{'pair': list(e['pair']), 'score': e['score'],
                                 'reasons': e['reasons']} for e in score_log],
                'best_assignments': best_assigns,
            },
            'transition_table': trans_rows,
            'excitation':       excitation,
            'jk_excitation':    jk_excitation,
            'is_mealy':         is_mealy,
            'is_incomplete':    is_incomplete,
            'verification':     verify,
        })
    except Exception as exc:
        import traceback
        return jsonify({'error': str(exc), 'trace': traceback.format_exc()}), 500


@app.route('/api/verify', methods=['POST', 'OPTIONS'])
def api_verify():
    if request.method == 'OPTIONS': return '', 204
    try:
        data    = request.get_json(force=True)
        orig    = data['original']
        reduced = data['reduced']
        ni      = int(data.get('num_inputs', 2))
        result  = verify_equivalence(orig, reduced, ni)
        return jsonify(result)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print()
    print('╔══════════════════════════════════════════════════════╗')
    print('║   FSM State Reduction Tool  v2.2  —  Flask Server    ║')
    print('║                                                      ║')
    print('║   Open  http://localhost:5000  in your browser       ║')
    print('║                                                      ║')
    print('║   pip install flask   (if not already installed)     ║')
    print('╚══════════════════════════════════════════════════════╝')
    print()
    app.run(debug=True, port=5000)
