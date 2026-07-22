# Fleet Fuel Management

Flask-based fleet management with GPS tracking, fuel monitoring, and a 3D/2D **Truck Load Planner** featuring a multi-vehicle bin-packing algorithm, door-aware access validation, and step-by-step placement animation.

## Pages

- **Map** (`/`) — GPS trip tracking with geofencing (Ray Casting)
- **Fuel Efficiency** (`/fuel-efficiency`) — Dashboard with KPIs, chart, refuel log
- **Container Fuel** (`/fuel-container`) — Container-vehicle dashboard with partial-tank support
- **Truck Load Planner** (`/truck-load-planner`) — 3D/2D cargo loader with auto-arrange, stacking, step animation
- **Vehicle Management** (`/vehicle-management`) — Vehicle CRUD and interactive 3D container diagram (Three.js)
- **Oil Change** (`/oil-change`) — Oil change tracking

---

## Running Tests

All tests, benchmarks, diagnostics, queries, and instrumentation are unified in `tests/test_all.py`. Output is saved to `reports/`.

```bash
# ── Benchmarks ─────────────────────────────────────────────
python tests/test_all.py benchmark --mode distribution   # Single distribution run (46 pkgs, 32 vehicles)
python tests/test_all.py benchmark --mode floor_contact  # Compare floor_contact weight 25 vs 5 (60 trials)
python tests/test_all.py benchmark --mode real_data      # End-to-end with real DB data

# ── Diagnostics ────────────────────────────────────────────
python tests/test_all.py diagnose --scenario general     # KBF 280R + 3x LC 900 placement debug
python tests/test_all.py diagnose --scenario kbf_lc900   # Same scenario, focused output
python tests/test_all.py diagnose --scenario candidates  # Candidate generation & scoring breakdown
python tests/test_all.py diagnose --scenario stacking    # Floor vs stack decision analysis (15 pkgs)
python tests/test_all.py diagnose --scenario stacking --full  # Detailed breakdown

# ── Debug ──────────────────────────────────────────────────
python tests/test_all.py debug --mode py3dbp      # Run py3dbp engine on first vehicle
python tests/test_all.py debug --mode stats       # Statistics from py3dbp engine
python tests/test_all.py debug --mode validation  # Validate first package through pipeline
python tests/test_all.py debug --mode vehicles    # List all vehicles with dimensions

# ── Database Queries ───────────────────────────────────────
python tests/test_all.py query --mode vehicles   # Vehicles sorted by capacity
python tests/test_all.py query --mode tables     # Row counts per table
python tests/test_all.py query --mode db         # Full database overview
python tests/test_all.py query --mode shipments  # Shipments with package details

# ── Instrumentation ────────────────────────────────────────
python tests/test_all.py instrument --mode trace      # Read instrument_trace.jsonl
python tests/test_all.py instrument --mode bug-trace  # Support integrity trace (10 pkgs)

# ── Pytest Unit Tests ──────────────────────────────────────
python -m pytest tests/test_scorer.py -v

# ── Standalone Debugger ────────────────────────────────────
python tests/debug_arrange.py kbf_lc900          # Auto-arrange debug per scenario
python tests/debug_arrange.py real --full        # Full 46-pkg real shipment debug

# ── Manual Test (full pipeline) ────────────────────────────
python manual_test.py                            # Internal engine (default)
python manual_test.py --engine py3dbp            # py3dbp engine
python manual_test.py --compare                  # Side-by-side comparison
```

---

## Truck Load Planner — Algorithm Reference

### Multi-Vehicle Distribution (Largest-Vehicle-First)

When auto-arrange is triggered, all packages are distributed across every vehicle that has a container config. The algorithm (`distribute_across_vehicles` in `engine/distribution.py`) uses **Largest-Vehicle-First**:

1. **Sort packages**: non-stackable first, then by volume DESC, weight DESC, footprint DESC
2. **Sort vehicles**: by combined capacity (volume × payload) descending
3. **For each vehicle** (biggest → smallest): try to place all remaining packages using a simple constructive sweep
4. **Result**: Largest vehicles are loaded first, smaller ones only receive what big ones cannot fit

### Placement Strategy: `LargestFirstStrategy`

Within each vehicle, packages are placed one at a time:

1. **Sort**: non-stackable first, then by volume DESC, weight DESC, footprint DESC
2. **For each package**:
   - Generate candidate positions from origin + right/front/top corners of all placed packages
   - Expand each candidate with both 0° and (if allowed) 90° rotation
   - **Score** on 4 weighted criteria: `package_contact` (1000), `x_preference` (200), `floor_contact` (100), `y_balance` (50)
   - Validate: boundary, weight, collision, support, door fit, door sweep
   - Pick the highest-scoring valid position and commit
3. No post-processing, no repair, no gap-filling, no compaction — the first placement is the final placement

### Scoring Engine (`engine/scorer.py`)

Every valid candidate position receives a score (4 terms, no clamping). The scorer never determines validity.

| Category | Weight | Raw → Score |
|----------|--------|-------------|
| Package Contact | 1000 | Sum of coincident-face overlap areas (mm²) across all neighbors |
| X Preference | 200 | `max(0, container.length − xmin)` — rewards deep (front-wall) placement |
| Floor Contact | 100 | `container.width × container.length` if z=0, else 0 |
| Y Balance | 50 | Rewards Y-centre-of-gravity close to container midpoint |

### Validation Pipeline

1. `validate_placement()` — progressive filter (cheapest first):
   - **Boundary** — actual AABB vs container bounds
   - **Payload / Weight** — total weight vs container payload
   - **Collision** — inflated AABB (with per-axis clearance) against all placed packages
   - **Support** — actual AABB, combined-support model (union overlap + centre-of-mass)
   - **Door fit** — cross-section fits through door opening
   - **Door sweep** — sweep volume from position to door must be clear

### Stacking Rules (`engine/support.py`)

1. Candidate must be stackable (`stackable=True`)
2. Package below must allow stacking (mode ≠ `NONE`)
3. Above package must be lighter than every package below
4. Max stack layers: package below must not exceed `max_stack_layers`
5. Footprint: above ≤ every below package's footprint
6. Combined support coverage ≥ 50% of candidate footprint (grid-sampled 20×20)
7. Centre-of-mass: XY centre must lie within at least one below package's XY extent

### Door Access Validation (`engine/access.py`)

- **Rear door**: cross-section fits opening, sweep from position to rear must be clear
- **Side door**: cross-section fits opening, X-range overlaps door position, sweep clear
- Default: full-width/full-height rear door when no features configured

### Step Animation & 3D Controls

After auto-arrange, packages enter one-by-one in `load_sequence` order from the appropriate door. Controls: ◀ Prev, 0/15 counter, ▶ Next, ▶▶ Play, ⏭ End, ⛶ Fullscreen. Keyboard: **F** toggles fullscreen, **Escape** exits.

---

## Engine Architecture (`truck_load_planner/engine/`)

| Module | Responsibility |
|--------|---------------|
| `planner.py` | Orchestrates all planning operations |
| `auto_arrange.py` | Strategy-based auto-arrange (LargestFirstStrategy) |
| `distribution.py` | Multi-vehicle fleet distribution (Largest-Vehicle-First) |
| `candidate_points.py` | Candidate position generation (origin + package corners) |
| `scorer.py` | 4-category placement quality scoring |
| `validation.py` | All rule checks: boundary, collision, weight, support, door access |
| `access.py` | Door access validation (rear + side sweep checks) |
| `support.py` | Stacking validation with combined-support model |
| `state.py` | Planner state: spatial index, extreme points, placement mutations |
| `spatial.py` | Spatial hash grid for fast AABB queries |
| `geometry.py` | AABB with clearance-aware from_dimensions, overlap/intersection |
| `collision.py` | AABB collision detection |
| `boundary.py` | Container boundary containment |
| `statistics.py` | Utilization, weight, and package counts |
| `weight.py` | Total weight vs payload calculation |
| `container.py` | Container dataclass (dimensions, features, payload) |
| `package.py` | Package dataclass (dimensions, stackable, rotation, clearance) |
| `placement.py` | Placement dataclass (position, rotation, sequence, door_used) |
| `profile.py` | Solver profile configuration (name, candidate_limit, tighten_step) |

---

## Experimental: py3dbp Packing Engine

An experimental integration of the [py3dbp](https://pypi.org/project/py3dbp/) 3D bin-packing library is available as an alternative packing engine for benchmarking purposes.

```bash
python manual_test.py --engine py3dbp
python manual_test.py --compare
```

Both engines implement the `PackingEngine` interface defined in `truck_load_planner/engines/base.py`.

## Project Structure

```
app.py                          # Main Flask application entry point
main.py                         # Standalone TTAS GPS tracking tool
manual_test.py                  # Manual pipeline test with instrumentation
tests/                          # All test, debug, and diagnostic files
  test_all.py                   # Unified test harness (16 subcommands)
  test_scorer.py                # Pytest unit tests (17 tests)
  debug_arrange.py              # Per-package auto-arrange debugger
  merge_duplicate_vehicles.py   # One-time DB dedup utility
reports/                        # Test and debug output files
truck_load_planner/             # Core application package
  routes.py                     # Flask routes / API endpoints
  session.py                    # Load planning session
  db.py                         # Database initialization
  engine/                       # Packing algorithms (17 modules)
  engines/                      # Packing engine abstraction (internal + py3dbp)
  models/                       # Data models
  logistics/                    # Legacy logistics helpers
static/                         # Frontend assets (JS, CSS)
templates/                      # HTML templates
```

## Tech Stack

- **Backend**: Python, Flask, SQLite3
- **Frontend**: Vanilla JS, Chart.js 4.4.7, Konva.js 9 (canvas), Three.js (3D)
- **No ORM** — raw SQL for full control
