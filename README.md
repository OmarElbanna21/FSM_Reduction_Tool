# FSM State Reduction & Synthesis Tool
### Digital Logic Circuits II — Alexandria University

> An interactive, step-by-step tool for **Finite State Machine** reduction and logic synthesis. Supports Moore, Mealy, and Incompletely Specified networks. Runs fully in the browser with an optional Python/Flask backend for heavier computations.

---

## Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [Getting Started](#getting-started)
5. [Usage Guide](#usage-guide)
6. [Algorithms](#algorithms)
7. [API Reference](#api-reference)
8. [Presets](#presets)
9. [Input Format](#input-format)
10. [Architecture & Design](#architecture--design)
11. [Known Limitations](#known-limitations)
12. [Changelog](#changelog)

---

## Overview

This tool implements the full **FSM state reduction and synthesis pipeline** taught in Digital Logic Circuits II:

```
Raw State Table
      │
      ▼
0. Unreachable State Removal  (skipped for incomplete networks)
      │
      ▼
1. Row Matching  (iterative — multiple passes until stable)
      │
      ▼
2. Implication Table  (Method A — works for all FSMs)
      │
      ▼
3. Partitioning Method  (Method B — fully specified only)
      │
      ▼
4. Equivalent / Compatible Classes  (Union-Find or Bron-Kerbosch + greedy cover)
      │
      ▼
5. Reduced State Table
      │
      ▼
6. State Assignment  (3-Rule Adjacency Scoring)
      │
      ▼
7. Binary Transition Table
      │
      ▼
8. Excitation Equations  (D flip-flop & J-K flip-flop, Quine-McCluskey minimized)
      │
      ▼
9. K-Maps  (2–4 variable, prime implicant groups colored)
      │
      ▼
10. Equivalence Verification  (random simulation trials)
```

---

## Features

| Feature | Description |
|---|---|
| **Moore FSM** | Single output per state |
| **Mealy FSM** | Per-input output (Z depends on state + input) |
| **Incomplete Networks** | Don't-care transitions & outputs fully supported |
| **Row Matching** | Iterative passes — keeps running until no identical rows remain |
| **Implication Table** | Pass-by-pass animated view with click-to-highlight dependencies |
| **Partitioning Method** | Full iterative refinement, skipped automatically for incomplete networks |
| **State Assignment** | 3-rule adjacency scoring with top-N assignment comparison |
| **Adjacency Graph** | Interactive D3.js force-directed graph of state pairs |
| **D & J-K Flip-Flops** | Both excitation equation sets generated and tabbed |
| **Quine-McCluskey** | Full Q-M minimization (not just K-map visual grouping) |
| **K-Maps** | 2, 3, and 4-variable K-maps with prime implicant coloring |
| **Verification** | Probabilistic equivalence check via FSM simulation |
| **Bulk Paste** | Import state tables via space/tab/comma-separated text |
| **PDF Export** | Browser print → PDF with color-safe styles |
| **Standalone Mode** | Entire pipeline runs in pure JavaScript — no backend needed |
| **Backend Mode** | Optional Flask server for larger machines (>9 states) |

---

## Project Structure

```
fsm-tool/
├── index.html          # Single-file frontend — all UI, CSS, and JS algorithms
├── app.py              # Optional Flask backend (same algorithms in Python)
├── README.md           # This file
└── DOCS.md             # Extended technical documentation
```

### Why two implementations?

| | `index.html` (JS) | `app.py` (Python) |
|---|---|---|
| **Runs** | In-browser, no install | Requires Python + Flask |
| **State limit** | Up to ~12 states comfortably | Up to ~20+ states |
| **Assignment search** | 40 000 permutation limit | 80 000 permutation limit |
| **Usage** | Default (standalone mode) | Auto-used when backend is running |

---

## Getting Started

### Option A — Standalone (no installation)

Just open `index.html` in any modern browser.  
All algorithms run in JavaScript. No internet connection required after the page loads.

```bash
# Double-click index.html, or:
open index.html          # macOS
xdg-open index.html      # Linux
start index.html         # Windows
```

### Option B — With Python Backend

The backend unlocks faster computation for large machines and serves `index.html` at `localhost:5000`.

**Requirements:** Python 3.8+, Flask

```bash
# 1. Install Flask
pip install flask

# 2. Place both files in the same folder
# 3. Run the server
python app.py

# 4. Open in browser
# http://localhost:5000
```

The frontend auto-detects the backend at startup. The sidebar shows:
- `backend ✓` (green) — Python pipeline active
- `standalone mode` (red) — JS-only mode

---

## Usage Guide

### Step 1 — Configure the Machine

| Setting | Options | Notes |
|---|---|---|
| **Machine Type** | Moore / Mealy | Mealy adds a Z column per input |
| **Input Columns** | 1, 2, 4 | 1 = single X; 2 = X=0,X=1; 4 = X₁X₂ ∈ {00,01,10,11} |
| **Output Bits** | 1-bit (Z), 2-bit (Z₁Z₂) | Controls output column display width |
| **States** | 2 – 26 | Number of rows in the input table |

### Step 2 — Fill the State Table

- **P.S.** — Present state name (any letters/numbers)
- **N.S.** — Next state for each input column
- **Z** — Output (Moore: one per row; Mealy: one per input)
- Use `–` or `x` for **Don't Care** in any cell

#### Keyboard shortcuts in the table
| Key | Action |
|---|---|
| `Tab` | Move to next cell |
| `Shift+Tab` | Move to previous cell |
| `Enter` | Move down |

#### Bulk Paste
Click **📋 Paste** and enter space/tab/comma-separated rows:

```
# Moore format:  state  ns_x0  ns_x1  output
a  e  f  1
b  c  d  0
c  –  b  1

# Mealy format:  state  ns_x0  z_x0  ns_x1  z_x1
a  b  0  c  1
b  a  1  b  0
```

Use `–` or `x` for don't-care values.

### Step 3 — Run

Click **▶ Reduce** and scroll through the results sections:

| Section | Content |
|---|---|
| **Dashboard** | Summary stats: states reduced, FF count saved, passes, assignment score |
| **Algorithm Log** | Step-by-step log of what the pipeline did |
| **① Row Matching** | Removed states per pass + state table after each pass |
| **② Implication Table** | Pass navigator — click ◀▶ to step through passes; click any compatible cell to highlight its implied pairs |
| **③ Partitioning** | Group evolution across passes (fully specified FSMs only) |
| **⑤ State Assignment** | Top-3 assignments ranked by adjacency score + score log |
| **⑥ Transition Table** | Binary encoding with D-input columns (Gray code row order) |
| **⑦ Equations** | Q-M minimized D and J-K excitation equations + Z output |
| **⑧ K-Maps** | Color-coded prime implicant groups (tab between D and J-K) |
| **Verification** | 6 random simulation trials comparing original vs. reduced FSM |

---

## Algorithms

### 0. Unreachable State Removal

BFS from the first state. Any state not reachable is removed before the pipeline begins.

> ⚠️ **Skipped for incomplete networks.** A state with don't-care transitions may appear unreachable but is still required for the implication table to produce a correct compatible-class cover. If any cell in the N.S. column contains `–`, all states are kept.

### 1. Row Matching

Two states are **identical rows** if:
- Their outputs are equal (strict equality — `–` matches only `–`, not `0` or `1`)
- Their next-state entries are equal for every input (both `–`, or both the same state name)

Runs **iteratively**: after removing identical rows and updating next-state references, the process repeats until no further removals occur. This handles chains where a removal in pass N creates a new identical pair detectable only in pass N+1.

```
Example (Lec5 Ex1 — 12 states):
  Pass 1: k ≡ l  (both map to [b, a] with output 00)
  Pass 2: g ≡ e  (after k/l merged, g's row [j,k] = [j,l] = [j,e] = e's row)
  Result: 10 states
```

### 2. Implication Table (Method A)

Builds a lower-triangular table for all state pairs (i, j) with i > j.

**Pass 0 — Output comparison:**
- Moore: pair is incompatible if `Z(i) ≠ Z(j)` (neither being DC)
- Mealy: pair is incompatible if any per-input output `Z(i, x) ≠ Z(j, x)` (neither being DC)

**Propagation passes:**
- A compatible pair becomes incompatible if any of its *implied pairs* was marked incompatible in a previous pass
- Implied pair for input x: `(NS(i,x), NS(j,x))` — skipped if either is DC

Converges when a pass marks no new pairs.

**Works for all FSMs** including incompletely specified ones.

### 3. Partitioning Method (Method B)

Iterative partition refinement — equivalent to the implication table but faster to compute for fully specified machines.

**Initial partition P₀:** Group states by output Z.

**Refinement:** Within each group, compute a *signature* for each state = the group indices of its next states. States with different signatures split into subgroups.

Repeat until the partition does not change (convergence).

> ⚠️ **Not applicable to incomplete networks** (DC next-states break the group-index signature). The tool automatically hides Method B and shows a warning when any DC transitions are detected.

### 4. Equivalence Classes / Compatible Classes

**Fully specified FSMs (Method A or B):**  
Union-Find on all compatible pairs → equivalence classes.

**Incompletely specified FSMs:**  
1. Build compatibility graph (nodes = states, edges = compatible pairs)
2. Find all **maximal cliques** via Bron-Kerbosch algorithm
3. **Greedy minimum cover**: select cliques to cover every state at least once
   - Score = `(new states covered, −clique size)` — prefer larger coverage, then smaller cliques

### 5. State Assignment — 3-Rule Adjacency Scoring

For every pair of reduced states, compute an adjacency score:

| Rule | Score | Condition |
|---|---|---|
| Rule 1 | +3 pts | Same next state for any input (states "go to the same place") |
| Rule 2 | +2 pts | Both are next states of the same state (shared "parent") |
| Rule 3 | +1 pt | Same output Z |

High-score pairs should receive **adjacent binary codes** (1-bit apart) to cluster 1s in the K-map → simpler SOP equations.

**Search:** All combinations of codes from `{0 … 2^k−1}` assigned to `n` states. Up to 40 000 / 80 000 permutations tried (JS / Python), best-scoring kept.

### 6. Binary Transition Table

Enumerates all (present state, input) combinations in **Gray code** row order.
- Used codes → actual next-state entries
- Unused codes → marked as Don't Care (shown dimmed)
- D-input columns = next-state bits (D flip-flop: `D = NS`)
- Mealy: per-row Z column for each input

### 7. Quine-McCluskey Minimization

Full Q-M implementation for both excitation equations and Z:

1. Group minterms by number of 1-bits
2. Iteratively combine adjacent groups (differ in exactly 1 bit)
3. Track prime implicants (terms that cannot be combined further)
4. Essential prime implicant selection
5. Greedy cover for remaining uncovered minterms

**Minterm indexing** for k state bits + n_input_bits input bits:
```
m_idx = (ps_int << n_input_bits) | x
```

**Output Z:**
- Moore: `Z` depends on state only → same value for all inputs of a state
- Mealy: `Z` depends on (state, input) → each `(state, input)` pair contributes its own minterm

### 8. J-K Flip-Flop Excitation

Derived from the next-state table using the J-K truth table:

| Q(t) | Q(t+1) | J | K |
|---|---|---|---|
| 0 | 0 | 0 | x |
| 0 | 1 | 1 | x |
| 1 | 0 | x | 1 |
| 1 | 1 | x | 0 |

Don't-care transitions in the state table → don't-care in both J and K.

---

## API Reference

When `app.py` is running, the frontend sends requests to `http://localhost:5000`.

### `POST /api/ping`

Health check.

**Response:**
```json
{ "status": "ok", "version": "2.2" }
```

---

### `POST /api/reduce`

Full reduction pipeline.

**Request body:**
```json
{
  "states": [
    {
      "name": "a",
      "next_states": ["b", "c"],
      "output": "0",
      "outputs": null
    }
  ],
  "num_inputs": 2,
  "is_mealy": false,
  "n_best": 10
}
```

| Field | Type | Description |
|---|---|---|
| `states` | array | List of state objects |
| `states[].name` | string | State identifier (e.g. `"a"`, `"A"`) |
| `states[].next_states` | string[] | Next state for each input (use `"-"` for DC) |
| `states[].output` | string | Moore output (use `"-"` for DC or Mealy) |
| `states[].outputs` | string[] \| null | Mealy per-input outputs (use `"--"` or `"-"` for DC) |
| `num_inputs` | int | Number of input columns (1, 2, or 4) |
| `is_mealy` | bool | `true` for Mealy machines |
| `n_best` | int | Top-N state assignments to return |

**Response:**
```json
{
  "success": true,
  "log": ["Starting Moore reduction: 9 states, 2 input(s).", "..."],
  "raw_states": [...],
  "row_matching": {
    "removed": { "i": "h", "g": "f" },
    "states_after": [...]
  },
  "implication_table": {
    "cells": { "3,1": { "i": 3, "j": 1, "status": "compat", "implied": [...], "marked_pass": -1 }, "..." },
    "passes": [ [[3,1]], [], [] ],
    "states": [...]
  },
  "partitioning": [
    { "pass": 0, "partition": [["a","b"], ["c"]], "reason": "Initial: group by output Z", "converged": false },
    "..."
  ],
  "classes": [["a","b"], ["c","d","e"], ["f"]],
  "reduced": [
    { "name": "A", "members": ["a","b"], "next_states": ["B","C"], "output": "0" }
  ],
  "state_assignment": {
    "pair_scores": [[0,3,1],[3,0,2],[1,2,0]],
    "score_log": [...],
    "best_assignments": [
      { "score": 5, "assignment": [0,1,2], "mapping": {"A":"00","B":"01","C":"10"}, "n_bits": 2, "adjacency_details": [...] }
    ]
  },
  "transition_table": [...],
  "excitation": {
    "D1": { "equation": "Q0 + X", "minterms": [1,2,3], "dontcares": [6,7], "var_names": ["Q1","Q0","X"] },
    "D0": { "..." },
    "Z":  { "..." }
  },
  "jk_excitation": { "J1": {...}, "K1": {...}, "J0": {...}, "K0": {...} },
  "is_mealy": false,
  "is_incomplete": false,
  "verification": {
    "all_passed": true,
    "trials": [...]
  }
}
```

#### Cell status values

| `status` | Meaning | Display |
|---|---|---|
| `"compat"` | Compatible — may imply other pairs | ✓ (green) or implied pairs |
| `"ic_out"` | Incompatible — output mismatch (Pass 0) | ✕ (red solid) |
| `"ic_prop"` | Incompatible — propagated from implied pair | ✕ (red faded) |

---

### `POST /api/verify`

Simulate both the original and reduced FSMs on random input sequences and compare outputs.

**Request:**
```json
{
  "original": [...],
  "reduced":  [...],
  "num_inputs": 2
}
```

**Response:**
```json
{
  "all_passed": true,
  "n_trials": 6,
  "steps": 25,
  "trials": [
    {
      "trial": 1,
      "input_seq": [0,1,0,0,1,1,0,1],
      "orig_outputs": ["0","1","0","0","0","1","0","1"],
      "reduced_outputs": ["0","1","0","0","0","1","0","1"],
      "mismatches": 0,
      "passed": true
    }
  ]
}
```

---

## Presets

Click any preset button to instantly load a complete example.

| Label | Key | Type | States | Inputs | Description |
|---|---|---|---|---|---|
| **Lec6 Ex1** | `p1` | Moore | 4 | 2 | Small textbook example |
| **Lec5 Ex2** | `p2` | Moore | 9 | 2 | Medium example with multiple reductions |
| **Lec5 Ex3** | `p3` | Moore | 8 | 2 | 2-bit output example |
| **Lec5 Ex1** | `lec5ex1` | Moore | 12 | 2 | Requires 2 passes of row matching |
| **Lec6 Ex2** | `lec6ex2` | Moore | 7 | 2 | |
| **Mealy Ex** | `mealy1` | Mealy | 8 | 2 | Per-input output example |
| **Incomplete** | `inc1` | Mealy | 7 | 4 | Incompletely specified — 2-bit I/O |

Preset buttons are filtered by machine type — Moore presets are hidden when Mealy mode is active and vice versa.

---

## Input Format

### Don't Care Values

Any of the following are treated as don't-care:

| Symbol | Accepted |
|---|---|
| `–` (dash) | ✓ |
| `-` (hyphen) | ✓ |
| `x` or `X` | ✓ |
| `*` | ✓ |
| `--` (multi-bit) | ✓ |
| `xx` (multi-bit) | ✓ |
| empty cell | ✓ |

### Multi-bit Outputs

Enter as a string with no spaces: `01`, `10`, `11`, `00`, `--`, `0-`, `-1`.

### Bulk Paste Format

```
# Lines starting with # are ignored
# Optional first line: num_states  num_inputs
7  2

# Moore: state  ns_x0  ns_x1  output
a  e  e  1
b  c  e  1
c  i  h  0
d  h  a  1
e  i  f  0
f  e  g  0
g  h  b  1
h  c  d  0
i  f  b  1

# Mealy: state  ns_x0  z_x0  ns_x1  z_x1
a  b  0  c  1
b  –  1  b  0
```

---

## Architecture & Design

### Frontend (`index.html`)

Single self-contained HTML file. No build step, no external dependencies except D3.js (loaded from CDN).

```
index.html
├── CSS (lines ~9–268)       — Design tokens, component styles, print styles
├── HTML (lines ~270–478)    — Layout: sidebar nav, input card, results sections
└── JavaScript (lines ~479–end)
    ├── PR{}                  Preset data
    ├── isDC / zCmp           Utility functions
    ├── rowMatchJS()          Iterative row matching
    ├── implTableJS()         Implication table build + propagation
    ├── equivClassesJS()      Union-Find equivalence classes (complete FSMs)
    ├── compatClassesJS()     Bron-Kerbosch + greedy cover (incomplete FSMs)
    ├── partitionJS()         Partitioning method
    ├── buildReducedJS()      Construct reduced state table
    ├── pairScoresJS()        3-rule adjacency scoring
    ├── findAssignmentsJS()   State assignment search
    ├── buildTransTableJS()   Binary transition table
    ├── excitationJS()        D flip-flop equations (Q-M)
    ├── excitationJKjs()      J-K flip-flop equations (Q-M)
    ├── qmJS()                Quine-McCluskey core
    ├── piStr()               Prime implicant → expression string
    ├── buildKmap()           K-map HTML renderer
    ├── solve()               Main pipeline orchestrator
    ├── renderAll()           Dispatch all render functions
    ├── renderS1–S7()         Section-specific renderers
    └── runVerify()           Equivalence verification runner
```

### Backend (`app.py`)

Flask REST API. Same algorithms as the JS frontend, independently implemented in Python. Auto-detected by the frontend on page load via `/api/ping`.

```
app.py
├── Utilities             is_dc, outputs_compat, hamming, pair_key
├── remove_unreachable_states()
├── row_matching()        Iterative (loop until stable)
├── build_implication_table()
├── get_equiv_classes()   Union-Find
├── has_incomplete_ns()   Detect incomplete networks
├── partitioning_method()
├── build_reduced_table()
├── compute_pair_scores() 3-rule scoring
├── find_best_assignments()
├── generate_transition_table()
├── qm_minimize()         Quine-McCluskey
├── pi_to_expr()          Prime implicant → string
├── generate_excitation_equations()   D FF + Z output
├── _generate_jk_excitation()         J-K FF
├── simulate_fsm()
├── verify_equivalence()
└── Flask routes: /api/ping, /api/reduce, /api/verify
```

### Data Flow

```
User fills table
      │  getTableData() → raw[]  {n, ns[], z, zs[]}
      ▼
solve() checks incomplete → skips/runs rmUnreach()
      │  reach[]
      ▼
rowMatchJS() → {states, removed, passes}
      │  rm.states[]
      ▼
implTableJS() → {cells{}, passes[]}
      │
      ├──(complete)──► equivClassesJS()  → classes[][]
      └──(incomplete)► compatClassesJS() → classes[][]
                              │
                              ▼
                       buildReducedJS() → reduced[]
                              │
                              ▼
                       pairScoresJS() + findAssignmentsJS() → bestA[]
                              │
                              ▼
                       buildTransTableJS() → trows[]
                              │
                              ▼
                       excitationJS() + excitationJKjs() → eqs{}
                              │
                              ▼
                       renderAll(result) → DOM update
```

---

## Known Limitations

| Limitation | Details |
|---|---|
| **State name uniqueness** | All state names must be unique within a table |
| **Maximum states (JS)** | State assignment search caps at 40 000 permutations; for >12 states results may not be globally optimal |
| **Maximum states (Python)** | 80 000 permutation limit; random sampling used for >9 states |
| **K-map variables** | Shown for 2–4 variables only (1-variable and 5-variable maps not rendered) |
| **Incomplete network partitioning** | Correctly disabled — only Method A (implication table) is valid |
| **Greedy cover** | Minimum compatible-class cover is NP-hard in general; the greedy algorithm gives a good but not always globally minimal solution |
| **Verification** | Probabilistic (6 trials × 25 steps) — not a formal proof |
| **Mealy verification** | Simulator uses per-input outputs; equivalence check compares output sequences |

---

## Changelog

### v2.2 (current)
- **Fix:** Unreachable state removal is now **skipped for incomplete networks** — states with DC transitions were being incorrectly removed before the implication table could process them
- **Fix:** Row matching is now **iterative** (multi-pass) — previously stopped after one pass, missing pairs that only become identical after earlier removals (e.g. Lec5 Ex1 required 2 passes)
- **Fix:** Row matching for **Mealy** now compares per-input outputs (`zs[]`) — previously used the single `z` field which is always `'–'` for Mealy
- **Fix:** Binary Transition Table **Mealy Z column** now shows the correct per-input output instead of always showing `'–'`
- **Fix:** **Mealy excitation Z equation** now uses per-input outputs when building minterms — previously treated Mealy states as Moore (all Z = don't care → equation always `0`)
- **Fix:** `loadP()` now reads `obits` from preset data — Incomplete example loads with correct 2-bit output
- **Fix:** Lec5 Ex3 preset — state `e` was unreachable due to wrong next-state in `d`; corrected to `d → [e, h]`
- **Improvement:** `renderS1` now shows the state transition table after **each pass** of row matching
- **Improvement:** `compatClassesJS` greedy scoring improved — prefers cliques that cover more new states and are smaller (better match to textbook solutions)
- **UI:** Removed `(Moore)` label next to State Assignment — synthesis applies to both Moore and Mealy
- **Preset:** Added `inc1` — Incompletely Specified Network example (7 states, 4 inputs, 2-bit output)

### v2.1
- Added Mealy machine support
- Added J-K flip-flop excitation equations
- Added adjacency graph (D3.js)
- Added bulk paste import
- Added PDF export

### v2.0
- Complete rewrite with standalone JS pipeline
- Flask backend optional
- Implication table pass navigator
- Partitioning method added
- K-map prime implicant coloring

---

## License

Academic use — Alexandria University, Faculty of Engineering.  
Digital Logic Circuits II · Prof. Dr. Magdy A. Ahmed
