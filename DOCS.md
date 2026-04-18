# FSM Tool — Technical Documentation
### Extended Developer & Algorithm Reference

---

## Table of Contents

1. [Algorithm Deep-Dive](#algorithm-deep-dive)
2. [Data Structures](#data-structures)
3. [Edge Cases & Design Decisions](#edge-cases--design-decisions)
4. [JavaScript Function Reference](#javascript-function-reference)
5. [Python Function Reference](#python-function-reference)
6. [Adding a New Preset](#adding-a-new-preset)
7. [Worked Example — End to End](#worked-example--end-to-end)

---

## Algorithm Deep-Dive

### Iterative Row Matching

Standard row matching makes a single pass. The iterative version is required whenever a removal in pass N creates a new identical pair that wasn't detectable before.

```
Example — Lec5 Ex1 (12 states, 2 inputs):

Initial table (relevant rows):
  k: NS=[b,a]  Z=00
  l: NS=[b,a]  Z=00   → identical to k

Pass 1: remove l (≡ k). Update all NS references: l → k
  g: NS=[j,l]  → NS=[j,k]
  e: NS=[j,k]  Z=00
  g: NS=[j,k]  Z=00   → NOW identical to e

Pass 2: remove g (≡ e)

Result: 10 states (was 12)
Without iterative matching: result would be 11 states (incorrect)
```

**Termination:** Guaranteed because each pass strictly reduces the number of states. With `n` states, at most `n−1` passes are possible.

**Complexity:** `O(n² × passes)` where passes ≤ n−1.

---

### Implication Table — Complete Walkthrough

**Setup:** For `n` states, build an `n×n` lower-triangular table with `n(n-1)/2` cells.

**Cell contents before propagation:**
```
(i, j) where i > j:
  - ic_out   if outputs incompatible
  - compat   with implied = list of (NS_i(x), NS_j(x)) pairs for each input x
             (skip if either NS is DC, or if NS_i(x) == NS_j(x))
```

**Propagation loop:**
```python
while True:
    newly_marked = []
    for each compat cell (i,j):
        for each implied pair (a,b):
            if cell(a,b) is NOT compat:
                mark (i,j) as ic_prop
                break
    if not newly_marked:
        break  # converged
```

**Compatible pairs at convergence:** all cells still in `compat` status.

**For Mealy:** Output comparison is per-input:
```
(i, j) is ic_out if ∃ x such that:
    Z(i, x) ≠ Z(j, x)  AND  neither is DC
```

**For incomplete networks:** DC next-states are simply skipped when building the implied-pairs list. A cell with all-DC implied pairs has no constraints and stays `compat`.

---

### Bron-Kerbosch for Compatible Classes

Used only for incompletely specified networks where Union-Find is insufficient (compatibility is not transitive — A compat B, A compat C does NOT imply B compat C).

```
Algorithm: Bron-Kerbosch with pivot selection
Input:  compatibility graph G = (V, E)
Output: all maximal cliques

procedure BK(R, P, X):
    if P = ∅ and X = ∅:
        output R as a maximal clique
        return
    u = vertex in P ∪ X with most neighbors in P  (pivot)
    for each v in P \ N(u):
        BK(R ∪ {v}, P ∩ N(v), X ∩ N(v))
        P = P \ {v}
        X = X ∪ {v}
```

**Greedy Cover after Bron-Kerbosch:**

The minimum clique cover problem is NP-hard. The greedy heuristic:

```
covered = ∅
chosen  = []
while covered ≠ V:
    uncovered = V \ covered
    score each clique C:
        primary   = |C ∩ uncovered|   (maximize new coverage)
        secondary = −|C|              (among ties: prefer smaller clique)
    pick best clique by (primary, secondary)
    add to chosen, mark members covered
```

This tends to match textbook solutions because textbooks also pick the largest group first, then smallest singleton for isolated nodes.

---

### Quine-McCluskey Implementation

```
Input:  minterms[], dontcares[], n_vars

Step 1 — Implicant generation:
  Start: each minterm/DC as a 1-literal implicant (value, mask)
         mask = 0 (no bits eliminated yet)
  Combine: two implicants (v1,d1) and (v2,d2) combine if:
    - d1 == d2  (same eliminated bits)
    - v1 XOR v2 is a power of 2  (differ in exactly 1 bit)
  Result: new implicant (v1 & ~xr, d1 | xr)
  Track which original implicants were combined

Step 2 — Prime implicants:
  Any implicant NOT combined in any step = prime implicant

Step 3 — Essential PIs:
  For each minterm m:
    count how many PIs cover m
    if exactly 1: that PI is essential → select it, mark covered minterms

Step 4 — Greedy cover:
  For remaining uncovered minterms:
    repeatedly select PI covering most uncovered minterms
    until all covered

Output: selected prime implicants
```

**Minterm index formula:**
```
For k state bits + n_input_bits input bits:
  n_input_bits = ⌈log₂(ni)⌉  for ni > 1,  else 0
  m_idx = (ps_int << n_input_bits) | x

Examples:
  ni=2 → n_input_bits=1 → vars = [Q_{k-1}, ..., Q_0, X]
  ni=4 → n_input_bits=2 → vars = [Q_{k-1}, ..., Q_0, X₀, X₁]
  ni=1 → n_input_bits=0 → vars = [Q_{k-1}, ..., Q_0]  (no input variable)
```

---

### 3-Rule State Assignment

**Why adjacency matters:**  
Adjacent codes (1-bit apart) in a K-map → their 1s are physically adjacent → can be grouped → simpler SOP expression.

**Scoring example:**

```
Reduced states: A, B, C, D

Rule 1 (+3 pts): Same NS for any input
  A(X=0)→C,  B(X=0)→C  →  pair (A,B): +3

Rule 2 (+2 pts): Both are NS of the same state
  D goes to A (X=0) and B (X=1)  →  pair (A,B): +2

Rule 3 (+1 pt): Same output
  Z(A) = Z(B) = 0  →  pair (A,B): +1

Total (A,B) = 6 pts → should be adjacent in K-map
```

**Assignment search:**

```python
k = ⌈log₂(n)⌉     # bits needed
codes = [0 .. 2^k−1]

for each combination of n codes from the 2^k available:
    for each permutation of that combination:
        score = sum of pair_scores[i][j]
                for all (i,j) pairs where codes are adjacent (hamming=1)
        record (score, assignment)

return top-N unique assignments sorted by score descending
```

---

## Data Structures

### State Object (JS internal)

```js
{
  n:   "a",          // state name
  ns:  ["b", "-"],   // next states, one per input column
  z:   "0",          // Moore output  (or "-" for Mealy)
  zs:  ["1", "0"],   // Mealy per-input outputs  (undefined for Moore)
}
```

### State Object (API / Python)

```python
{
  "name":        "a",
  "next_states": ["b", "-"],
  "output":      "0",         # Moore output  ("-" for Mealy)
  "outputs":     ["1", "0"],  # Mealy per-input outputs  (None for Moore)
}
```

### Implication Table Cell

```js
{
  i:           3,          // row index (i > j always)
  j:           1,          // column index
  status:      "compat",   // "compat" | "ic_out" | "ic_prop"
  implied:     [[4,2]],    // list of [i,j] pairs this cell depends on
  markedPass:  -1,         // pass in which marked (-1 = still compat)
}
```

### Assignment Object

```js
{
  score:       7,
  assignment:  [0, 3, 1, 2],         // code per state in states[] order
  mapping:     {"A":"00","B":"11","C":"01","D":"10"},
  n_bits:      2,
  adjacency_details: [
    { state_a:"A", code_a:"00", state_b:"C", code_b:"01", score:3 }
  ]
}
```

### Excitation Equation Object

```js
{
  equation:   "Q1' + X",              // SOP expression string
  minterms:   [1, 2, 3, 5],
  dontcares:  [6, 7],
  var_names:  ["Q1", "Q0", "X"],
}
```

---

## Edge Cases & Design Decisions

### 1. Don't-Care output in Row Matching

**Decision:** Strict equality — `–` matches only `–`, not `0` or `1`.

**Rationale:** Row matching requires the rows to be truly identical. If one state has output `0` and another has DC, we cannot claim they are "the same state" — the DC state might output `1` in some realization, making the behaviors different. The implication table (which supports DC via `outputs_compat`) is the correct place to handle this flexibility.

### 2. Incomplete Networks — Skip Unreachable Removal

**Decision:** If any next-state cell is DC, skip unreachable removal entirely.

**Rationale:** Consider state `X` whose only incoming transition is `A(X=0) → X`, but `A(X=0)` is `–`. In a standard BFS, `X` appears unreachable. But `X` may be a required member of a compatible class that covers `A`. Removing it corrupts the compatibility structure. The implication table naturally handles this by treating DC transitions as "no constraint".

### 3. Greedy vs Optimal Cover

**Decision:** Use greedy heuristic for compatible class cover (not exact minimum).

**Rationale:** The minimum clique cover problem is NP-hard. For academic examples (≤ 10 states), the greedy solution matches the textbook answer in virtually all cases. An exact ILP solver would be disproportionate complexity for no practical benefit at this scale.

### 4. Mealy Z in Excitation Table

**Decision:** Each `(state, input)` pair contributes its own minterm row for Z.

**Rationale:** Mealy `Z(state, input)` has `n × ni` possible values instead of Moore's `n`. The minterm index `m = (ps << n_input_bits) | x` naturally encodes both state and input, making the K-map axes `[Q_{k-1} … Q_0, X]` where `X` is the input bit. The resulting equation is `Z = f(Q, X)`.

### 5. Gray Code Row Order in Transition Table

**Decision:** Rows are displayed in Gray code order of the state encoding.

**Rationale:** Adjacent rows in the transition table differ by 1 bit — this visually matches the K-map layout, making it easier to cross-reference minterms with K-map cells.

### 6. Pivot Selection in Bron-Kerbosch

**Decision:** Choose pivot `u` as the vertex in `P ∪ X` with the most neighbors in `P`.

**Rationale:** This maximizes the number of vertices pruned per recursive call, giving near-linear practical performance on sparse graphs typical of FSM compatibility graphs.

---

## JavaScript Function Reference

### `rowMatchJS(states, ni, isMealy) → {states, removed, passes}`

| Param | Type | Description |
|---|---|---|
| `states` | `{n, ns[], z, zs[]}[]` | Input state array |
| `ni` | `number` | Number of input columns |
| `isMealy` | `boolean` | If true, compare `zs[]` instead of `z` |

Returns:
- `states` — remaining states after all passes
- `removed` — `{stateName: canonicalName}` map (all passes combined)
- `passes` — array of per-pass info `{pass, removed, states_after}`

---

### `implTableJS(states, ni, isMealy) → {cells, passes}`

Builds and solves the implication table.

- `cells` — object keyed by `"i,j"` strings
- `passes` — array of arrays; `passes[p]` = keys marked in pass p

---

### `equivClassesJS(cells, states) → string[][]`

Union-Find on compatible pairs. Returns array of equivalence classes (each class = array of state names).

---

### `compatClassesJS(cells, states) → string[][]`

Bron-Kerbosch + greedy cover for incomplete networks. Returns array of compatible classes.

---

### `buildReducedJS(states, classes, ni) → reducedState[]`

Maps original states to new labeled states (A, B, C, …) using the representative (first member) of each class.

---

### `excitationJS(states, mapping, ni, isMealy) → {D0:{}, D1:{}, ..., Z:{}}`

Generates D flip-flop excitation equations and Z output.

- `mapping` — `{stateName: binaryCodeString}` e.g. `{"A":"00","B":"01"}`
- Returns equation objects keyed by `"D0"`, `"D1"`, …, `"Z"`

---

### `qmJS(minterms, dontcares, nVars) → primeImplicants[]`

Pure Quine-McCluskey. Returns array of `[value, mask]` pairs.

---

### `piStr(pi, varNames) → htmlString`

Converts a `[value, mask]` prime implicant to an HTML span string with variable names, primes for complemented literals.

---

### `buildKmap(minterms, dontcares, nv, varNames, title) → htmlString`

Renders a K-map as an HTML table string.

- `nv` — number of variables (2, 3, or 4)
- Cells colored by which prime implicant group they belong to

---

## Python Function Reference

### `is_dc(v) → bool`

Returns `True` for any don't-care representation: `""`, `"-"`, `"--"`, `"x"`, `"xx"`, `"*"`, `None`, `False`.

---

### `outputs_compat(z1, z2) → bool`

Compatibility check (used in implication table):
- Either operand DC → `True`
- Both equal → `True`
- Per-bit: if both same length, any DC bit in either → compatible at that position

---

### `outputs_equal(z1, z2) → bool`

Strict equality (used in row matching):
- Both DC → `True`
- One DC, one not → `False`
- Both specific → string equality only

---

### `row_matching(states) → (kept_states, removed_dict)`

Iterative version. Loops until no identical rows remain. Returns:
- `kept_states` — list of state dicts
- `removed_dict` — `{removed_name: canonical_name}` for all removed states across all passes

---

### `build_implication_table(states, ni, is_mealy) → (cells_dict, passes_list)`

- `cells_dict` — keyed by `(i, j)` tuples
- `passes_list` — `passes[p]` = list of `(i,j)` tuples marked in pass p

---

### `generate_excitation_equations(states, mapping, ni) → equations_dict`

Returns dict with keys `"D0"`, `"D1"`, …, `"Z"`. Each value:
```python
{
    "equation":  "Q0 + X'",
    "minterms":  [0, 1, 3],
    "dontcares": [6, 7],
    "n_vars":    3,
    "var_names": ["Q1", "Q0", "X"],
    "display":   "D1 = Q0 + X'",
}
```

Mealy Z: uses `state["outputs"][x]` per `(state, input)` combination.  
Moore Z: uses `state["output"]` replicated for each input.

---

### `qm_minimize(minterms, dontcares, n_vars) → prime_implicants`

Returns list of `(value, mask)` tuples.

---

## Adding a New Preset

### In `index.html`

1. Add to the `PR` object:

```js
const PR = {
  // ... existing presets ...
  myPreset: {
    ni:    2,          // number of input columns (1, 2, or 4)
    mealy: false,      // true for Mealy
    obits: 1,          // output bits (1 or 2)
    rows: [
      { n:'A', ns:['B','C'], z:'0' },   // Moore
      { n:'B', ns:['A','A'], z:'1' },
      { n:'C', ns:['C','B'], z:'0' },
      // For Mealy: z:'-', zs:['0','1']  instead of  z:'0'
    ]
  },
};
```

2. Add to `PRESET_META`:

```js
const PRESET_META = {
  // ... existing ...
  myPreset: { label: 'My Example', mealy: false },
};
```

That's it — the button appears automatically in the preset bar, filtered by machine type.

---

## Worked Example — End to End

**Input:** Lec5 Ex2 — 9-state Moore FSM, 2 inputs

```
State | X=0 | X=1 | Z
  a   |  e  |  e  | 1
  b   |  c  |  e  | 1
  c   |  i  |  h  | 0
  d   |  h  |  a  | 1
  e   |  i  |  f  | 0
  f   |  e  |  g  | 0
  g   |  h  |  b  | 1
  h   |  c  |  d  | 0
  i   |  f  |  b  | 1
```

### Step 0 — Unreachable Removal

BFS from `a`: all 9 states reachable. None removed.

### Step 1 — Row Matching

Compare rows:
- `a: [e,e,1]` vs `b: [c,e,1]` — different NS(X=0) → not identical
- `a: [e,e,1]` vs `d: [h,a,1]` — different → not identical
- ... (no identical rows found in pass 1)

Row matching: **no states removed**.

### Step 2 — Implication Table

Pass 0 (output incompatibility):
- States with Z=1: {a,b,d,g,i}
- States with Z=0: {c,e,f,h}
- Any pair with one from each group → `ic_out`

Pairs like (a,c), (a,e), (b,f), (d,h), etc. → marked in Pass 0.

Propagation finds further incompatibilities through implied pairs.

Compatible pairs at convergence (example): `{a,b}`, `{a,d}`, `{a,g}`, `{a,i}`, `{b,d}`, ...

### Step 3 — Equivalence Classes

Union-Find on compatible pairs gives classes such as:
```
A = {a, b, d, g, i}
B = {c, h}
C = {e}
D = {f}
```
(4 reduced states — was 9)

### Step 4 — Reduced Table

```
P.S. | X=0 | X=1 | Z
 A   |  C  |  C  | 1
 B   |  C  |  A  | 0
 C   |  D  |  A  | 0
 D   |  C  |  A  | 0
```

### Step 5 — State Assignment

k = ⌈log₂(4)⌉ = 2 bits.

Pair scores:
- (A,B): Rule 1 +3 (both go to C for X=0), Rule 3 ... → score = 3
- (B,C): ...
- (B,D): Rule 1 +3 (NS(X=0)=C, NS(X=1)=A) → score = 3+...
- etc.

Best assignment: e.g. A=00, B=01, C=11, D=10 (Gray code order → better grouping)

### Step 6 — Binary Transition Table

```
P.S.  Q1Q0 | X=0: NS | D1D0 || X=1: NS | D1D0 | Z
 A    00   | C  = 11 | 1 1  || C  = 11 | 1 1  | 1
 B    01   | C  = 11 | 1 1  || A  = 00 | 0 0  | 0
 C    11   | D  = 10 | 1 0  || A  = 00 | 0 0  | 0
 D    10   | C  = 11 | 1 1  || A  = 00 | 0 0  | 0
 --   (unused rows shown as DC)
```

### Step 7 — Equations (example)

```
D1 = Q1' + Q0' X'  + ...    (Q-M minimized)
D0 = Q1' X'  + ...
Z  = Q1'
```

---

*End of DOCS.md*
