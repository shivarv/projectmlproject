# Semantic Layer vs. Dirty Warehouse — project plan

**Thesis under test:** for LLM SQL generation, is an explicit semantic layer
actually more effective than prompt engineering against raw tables?

**What would falsify it:** if Arm A (raw + good prompt engineering) matches Arm C
(semantic layer) within the paired confidence interval, the semantic layer is not
earning its maintenance cost. That is a publishable result and we report it.

**Decisions locked:** Cube.js for the semantic layer · BRL-only, multi-currency
dropped · three arms.

---

## Status

| Phase | State |
|---|---|
| 0. Dirty warehouse | **Done** — `data/olist_dirty.duckdb`, 15 tables in `raw`, 22 catalogued defects (see `DATA.md`) |
| 1. Baseline schema | Not started |
| 2. Cube.js semantic layer | Not started |
| 3. Gold eval set (60) | Not started |
| 4. Harness + metrics | Not started |
| 5. Analysis | Not started |

---

## The methodological crux

A semantic layer *encodes* business conventions. A prompt can only *state* them.
If we give Arm C the conventions (baked into Cube) but not Arms A/B, we are not
measuring the semantic layer — we are measuring whether the model can guess our
house definition of "revenue." That test is rigged and the result is worthless.

So every query runs in **two modes**:

- **Fair mode** — all three arms receive the same `BUSINESS_RULES.md` (canonical
  revenue definition, canonical order date, refund settlement rule, etc.).
  Measures *enforcement* (layer) vs *compliance* (prompt). This is the honest
  test of the thesis.
- **Realistic mode** — Arms A/B get schema DDL + generic prompt engineering only.
  Measures the gap a real team actually experiences.

Reporting only one mode is the main way this experiment could mislead.

---

## Experimental arms

| Arm | Stack | What the LLM sees | What it emits |
|---|---|---|---|
| **A** | `raw.*` in DuckDB | Raw DDL + row samples + prompt engineering | SQL |
| **B** | dbt marts (clean, typed, deduped) | Clean DDL + prompt engineering | SQL |
| **C** | Cube.js over the dbt marts | Cube `/meta` JSON (measures, dimensions, joins, segments) | Cube query JSON → compiled to SQL by Cube |

**Arm B is the control and it is not optional.** Without it, a win for C only
proves that cleaning your data helps — not that a semantic layer does. B and C
share identical underlying marts, so B→C isolates the semantic layer itself, and
A→B isolates the data cleaning.

---

## Phase 1 — Baseline schema in DuckDB

Build `dbt-duckdb` project with three layers in one `.duckdb` file:

```
raw.*        (exists, untouched — Arm A reads this)
staging.*    1:1 with raw, parsing only: money → DECIMAL(12,2),
             timestamps → TIMESTAMP, codes → normalised enums
marts.*      conformed star schema — Arms B and C read this
```

Marts:

| Model | Grain | Resolves |
|---|---|---|
| `fct_orders` | order | canonical order date, one row per order, status normalised |
| `fct_order_items` | order × item | merchandise + freight, seller attribution |
| `fct_payments` | order | **pre-aggregated** to kill the 2,843-order fan-out |
| `fct_coupon_redemptions` | redemption | **deduped** on `redemption_id` (306 dupes), orphan codes preserved via LEFT JOIN |
| `fct_refunds` | refund | `abs()` applied, settled-only flag, settlement date |
| `fct_replacements` | replacement | zero-revenue units + COGS, kept out of sales |
| `dim_customers` | **`customer_unique_id`** | collapses the 99,441 order-scoped keys → 96,096 people |
| `dim_products` / `dim_sellers` / `dim_geography` | — | `dim_geography` **deduped to one row per zip** (kills the 152× fan-out) |

Every mart carries dbt tests: uniqueness on grain, not-null on keys,
relationships on FKs, and accepted-values on normalised enums. `DATA.md` is the
spec of what must be fixed; `scripts/validate_recoverability.py` already proves
each defect is reversible, so no mart should need a lossy workaround.

---

## Phase 2 — Cube.js semantic layer

`@cubejs-backend/duckdb-driver` 1.7.46, modelling the `marts.*` schema. Maps 1:1
onto the four things requested:

- **Measures** — `gross_merchandise_value`, `freight_revenue`, `discount_total`,
  `refund_total`, `net_revenue`, `replacement_cogs`, `units_sold`,
  `free_units_shipped`, `aov`, `return_rate`, `order_count`, `customer_count`.
  `net_revenue` is defined **once**, in one place, and is the only way to get it.
- **Dimensions** — order/delivery/settlement dates (as separate named time
  dimensions, so "when" is never implicit), category (EN via translation),
  seller, customer state, payment type, normalised return reason.
- **Joins** — declared with explicit `relationship`, so the fan-out joins are
  structurally unavailable. Cube cannot emit the 152× geolocation explosion.
- **Segments** — the canonical filtering rules: `delivered_only`,
  `settled_refunds_only`, `excludes_replacements`, `excludes_canceled`.

**Deliberate coverage test:** we do *not* pre-build a measure for every one of
the 60 queries. Some must fail as "not expressible in the layer." That number is
a headline finding — the real cost of a semantic layer is the questions it
cannot answer — and hiding it would be dishonest. Where Cube genuinely cannot
express something, the SQL API passthrough is recorded as a *partial* pass, not
a pass.

---

## Phase 3 — Gold standard evaluation set (60 queries)

### Format

```yaml
- id: rev_rec_004
  nl: "What was recognised revenue in Q2 2018?"
  tier: 2
  traps: [R1, R2, R3, D2, D3]
  canonical_decisions:
    - revenue recognised on delivery date, not purchase date
    - refunds deducted in the quarter they SETTLED, not the quarter of the sale
  gold_sql: |
    ...
  expected_shape: scalar
  tolerance: {abs: 0.01}
  cube_query: {...}
```

### Distribution

| Tier | n | Purpose |
|---:|---:|---|
| 0 — sanity | 6 | All arms should pass. Establishes the floor and catches harness bugs. |
| 1 — single trap | 24 | One defect each, isolated. Tells us *which* defects the layer fixes. |
| 2 — compositional | 20 | 2–3 traps interacting. Where we expect the gap to open. |
| 3 — adversarial | 10 | Genuinely underspecified questions. Tests whether the layer's canonical answer beats the model's guess. |

### Trap coverage (all 22 defects hit at least twice)

`R1` revenue definition · `R2` refund sign · `R3` refund settlement ·
`R4` coupon dupes · `R5` orphan coupon FK · `R6` coupon scale ambiguity ·
`R7` free replacements · `R8` stale finance snapshot ·
`D1` timestamp formats · `D2` which date · `D3` quarter recognition ·
`D4` clock skew · `J1` geo fan-out · `J2` payments fan-out ·
`J3` multi-seller attribution · `N1` bilingual reasons · `N2` status casing ·
`N3` BR money locale · `C1` customer key · `C2` churn window ·
`F1` order status filter · `F2` freight treatment

### The three named edge cases

**Churn (C1, C2).** Olist has no subscription, and **96.9% of customers buy
exactly once** (93,099 of 96,096 people). So churn must be defined, not
discovered: *"a customer is churned if they have no order in the 180 days
following their last order, measured as of 2018-08-31."* Two traps: joining on
`customer_id` instead of `customer_unique_id` inflates the customer count by
3,345 and makes churn look like ~100%; and the near-degenerate base rate means a
wrong denominator is very hard to notice. 5 queries.

**Recognised quarterly revenue (D2, D3, R1–R3).** Genuinely ambiguous in the
raw data: **11,638 delivered orders fall in a different quarter by delivery date
than by purchase date**, and **1,151 of 2,890 settled refunds (40%) settle in a
later quarter than the sale**. Canonical rule: recognise on delivery, deduct
refunds on settlement date. 8 queries.

**Multi-currency — dropped.** Olist is 100% BRL; there is no currency variation
to test. Rather than fake it shallowly, those slots are backfilled with
**freight allocation** (is shipping revenue?), **seller payout vs marketplace
take**, and **tax-exclusive reporting** — real ambiguities that exist in this
data. 7 queries.

### Authoring protocol (how we trust the gold SQL)

Gold SQL is the thing the whole experiment rests on, so:

1. Written against `raw.*` so it is arm-independent — no arm can be flattered by
   sharing its own abstractions with the answer key.
2. **Independently derived twice** — once hand-written against `raw`, once via
   the Cube-compiled SQL against `marts` — and the two must agree numerically.
   Disagreement means one of them is wrong; resolve before the query enters the set.
3. Scalar metrics additionally get a hand-computed assertion committed alongside.
4. Peer review pass over all 60 before any arm is run.
5. Frozen and hashed. Any post-hoc edit is logged with a reason.

---

## Phase 4 — Harness and metrics

```
harness/
  run_arm.py        # arm × mode × query × seed → prediction
  score.py          # result-set comparison
  report.py         # per-trap breakdown, paired tests, plots
results/runs/<timestamp>/
```

Scoring compares **result sets, not SQL strings** — order-insensitive, column-name
insensitive, `abs tol 0.01` on money, exact on counts.

| Metric | Why |
|---|---|
| **Execution accuracy** | Primary outcome |
| **Silent-error rate** — executes cleanly *and* returns the wrong number | **The headline.** A query that errors is safe; a plausible wrong number is the actual business risk, and it is exactly what these traps produce |
| Hard-error rate | Failed to execute |
| Coverage failures (Arm C) | Not expressible in the layer — the semantic layer's true cost |
| `consistency@3` | Same query, 3 seeds — measures stability, not just accuracy |
| Tokens / latency / cost | A layer that wins but costs 5× matters |

**Statistics.** The design is paired — same 60 queries across all arms — so use
**McNemar's test** on discordant pairs (A vs C, B vs C, A vs B), not a two-sample
proportion test. Report Wilson intervals. Two honest caveats to state up front:
n=60 only powers detection of moderate-to-large effects, and the queries are
**not independent** — they cluster by trap family — so we report per-family
breakdowns and treat the pooled number as indicative rather than precise.

---

## Phase 5 — Analysis

The deliverable is a per-trap table: *which specific defects does a semantic
layer fix, which does prompt engineering fix, and which does neither?* That is
more useful than a single accuracy number, and it is what a team deciding
whether to adopt Cube actually needs.

Expected shape of the result (to be confirmed or refuted): the layer should win
decisively on structural traps (`J1`, `J2`, `R4`, `C1`) because it makes the
error *unrepresentable*, and win far less on definitional traps (`D2`, `R1`)
where a good prompt can simply state the rule. If that pattern holds, the
recommendation is nuanced rather than "semantic layers good."

---

## Risks to validity

| Risk | Mitigation |
|---|---|
| **Training-data contamination** — Olist is all over GitHub and the model may recall its schema | Our 6 generated tables are novel and carry most of the traps. Optionally run a table-renamed variant to quantify the effect. |
| Gold SQL is wrong | Dual independent derivation + peer review (Phase 3 protocol) |
| Arm C flattered by us tuning Cube to the eval set | Freeze the Cube model **before** authoring Tier 2/3 queries; log any later change |
| Prompt engineering for Arm A is strawmanned | Arm A prompts get the same iteration budget as the Cube model, tracked and reported |
| n=60 underpowered | Paired McNemar; per-family reporting; state the limit rather than over-claiming |

---

## Milestones

| # | Deliverable | Depends on |
|---|---|---|
| M1 | dbt project, staging + marts, all tests green | — |
| M2 | `BUSINESS_RULES.md` — canonical definitions, frozen | M1 |
| M3 | Cube.js model serving `/meta`, frozen | M1, M2 |
| M4 | 60 gold queries, dual-verified and hashed | M2, M3 |
| M5 | Harness runs all arms × both modes × 3 seeds | M4 |
| M6 | Analysis report with per-trap breakdown | M5 |

Note M2 precedes M3 and M4: the canonical definitions must be written down
*before* the layer or the answer key encode them, or the experiment quietly
becomes self-confirming.
