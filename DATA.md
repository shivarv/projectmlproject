# Olist "dirty warehouse" — data dictionary

Everything lands in `data/olist_dirty.duckdb`, schema `raw`.

```sql
SELECT * FROM raw.orders LIMIT 5;
```

## Provenance

| Source | Tables | Status |
|---|---|---|
| Kaggle `olistbr/brazilian-ecommerce` | 9 | **Real**, byte-identical to source |
| `scripts/generate_commerce_layer.py` | 6 | **Generated**, keyed to real Olist entities |

Olist ships no refund, coupon, return, damage or replacement data. Those six
tables are synthesised. They are deterministic (seed `20181017`) and grounded:
return propensity is driven by the *real* review score, discounts by *real*
order totals, and every timestamp by the *real* order lifecycle.

## Real tables (unmodified)

| Table | Rows | Grain |
|---|---:|---|
| `raw.orders` | 99,441 | one order |
| `raw.order_items` | 112,650 | one line item |
| `raw.order_payments` | 103,886 | one payment instalment |
| `raw.order_reviews` | 99,224 | one review |
| `raw.customers` | 99,441 | one order-scoped customer key |
| `raw.products` | 32,951 | one product |
| `raw.sellers` | 3,095 | one seller |
| `raw.geolocation` | 1,000,163 | one zip/lat-lng point |
| `raw.product_category_name_translation` | 71 | PT→EN category |

## Generated tables

| Table | Rows | Grain |
|---|---:|---|
| `raw.coupons` | 64 | one coupon code (master) |
| `raw.order_coupons` | 15,599 | one redemption (**306 are duplicates**) |
| `raw.order_returns` | 4,841 | one RMA line |
| `raw.refunds` | 3,624 | one refund attempt |
| `raw.replacement_orders` | 1,436 | one free replacement shipment |
| `raw.finance_order_revenue_snapshot` | 86,617 | one order, per finance BI export |

All six load as `VARCHAR` so the encoding mess survives ingestion instead of
being silently coerced or nulled.

---

## The defect catalogue

This is the experiment surface. Every defect is **recoverable** — none destroy
information — and `scripts/validate_recoverability.py` asserts that on every run.

### Ambiguous timestamps
`orders` alone carries five date columns with no guidance on which means
"the order date": `order_purchase_timestamp`, `order_approved_at`,
`order_delivered_carrier_date`, `order_delivered_customer_date`,
`order_estimated_delivery_date`. Approval lags purchase; carrier and customer
delivery differ by days; ~3% are NULL. "Revenue in March" has five defensible answers.

Generated tables add *format* ambiguity on top — four encodings interleaved in
one column:

```
2018-07-08 04:04:42     ISO, space-separated
2017-07-07T04:41:12Z    ISO-8601 with Z
1519628688              epoch seconds
25/09/2017 18:55        BR day-first, no seconds
2017-09-25              date only, time lost
```

### Money encodings
Three encodings in one column, Brazilian locale:
`187.47`, `R$ 272,76`, `1.234,56`. Comma-present means comma is the decimal
separator and dots are thousands separators.

### Revenue is not one number
Five components live in five places and none is labelled "revenue":

- `order_items.price` — merchandise, per line
- `order_items.freight_value` — shipping charged
- `order_payments.payment_value` — what was actually collected (sums to a
  different number than items + freight)
- `order_coupons.discount_amount_applied` — reduces it
- `refunds.refund_amount` — reduces it, sometimes

### The sign trap
`refunds.refund_amount` stores **1,249 rows negative and 2,375 positive** for the
same semantic event. `SUM(refund_amount)` silently nets them against each other.

### The settlement trap
`refunds.refund_status` ∈ `processed` (2,615), `PROCESSED` (450), `pending` (290),
`failed` (179), `reversed` (90). Only the first two settled. Naive aggregation
deducts 559 refunds that never left the building — and case-sensitive matching
on `'processed'` silently drops 450 that did.

### Free replacements: units without revenue
1,436 damaged/defective orders were resolved by shipping a **new unit at zero
charge**. They are real fulfilled shipments: `quantity_shipped` > 0,
`charged_to_customer` = 0.00, and a real `replacement_cogs` cost.

- Count them as orders → AOV craters
- Count their units as sales → volume overstated by 1,479 units
- Ignore `replacement_cogs` → margin overstated
- They are **not** in `raw.order_items`; they must be unioned in deliberately

### Coupon traps
- **Type vocabulary is 11 spellings** of 3 concepts: `PCT`/`percent`/`PERCENTAGE`/`%`,
  `FIXED`/`BRL`/`amount`/`fixed_amount`, `FREESHIP`/`free_shipping`/`FRETE`
- **`discount_value` is scale-ambiguous**: a 5% coupon is stored as `0.05` on some
  rows and `5.0` on others. Only magnitude + type disambiguate.
- **306 duplicate redemptions** from an ETL replay, sharing `redemption_id`.
  `SUM(discount_amount_applied)` double-counts them (R$ 335,184.82 vs the true
  R$ 328,743.81). Worse: **141 of the pairs carry different money encodings**
  (`3,59` vs `3.59`), so `SELECT DISTINCT` on the *value* silently fails to
  collapse them and lands on R$ 331,796.30. Dedupe must key on `redemption_id`.
- **243 orphan `coupon_code`s** (`LEGACY***`) absent from `raw.coupons`. An inner
  join silently drops them.
- `applies_to` varies: `ORDER_TOTAL` / `ITEMS_ONLY` / `FREIGHT` / `order_total`
- `is_active` is `Y`/`N`/`1`/`0`/`true`/`TRUE`/`false`

### Return reason is free text in two languages
`DAMAGED_IN_TRANSIT` also appears as `damaged`, `DAMAGED`, `damaged_in_transit`
and `Produto danificado`. Likewise `DEFECTIVE`/`defeito`, `NOT_AS_DESCRIBED`/
`nao conforme anuncio`, `NO_LONGER_WANTED`/`arrependimento`. Grouping on the raw
column splits one reason across five buckets. `return_status` has the same
problem (`completed`/`COMPLETED`/`Completed`/`closed`).

### Clock skew
~0.8% of `order_returns` have `resolved_at` **before** `requested_at`. Naive
cycle-time averages go negative.

### The red herring
`raw.finance_order_revenue_snapshot.net_revenue` is the single most
question-shaped column in the warehouse, and it is **wrong**:

- **Stale** — cut off 2018-07-01, missing 12,824 orders
- Double-counts the 306 duplicate redemptions
- Drops goodwill refunds
- Treats `pending`/`failed` refunds as settled
- Ignores replacement COGS entirely

An LLM that pattern-matches the column name to the question will be confidently,
quietly incorrect. That is the point.

---

## Retained real signal

The generated layer is not noise. Return rate tracks the real review score:

| review_score | delivered orders | returned | rate |
|---:|---:|---:|---:|
| 1 | 9,381 | 2,107 | 22.5% |
| 2 | 2,938 | 403 | 13.7% |
| 3 | 7,942 | 627 | 7.9% |
| 4 | 18,943 | 593 | 3.1% |
| 5 | 56,817 | 1,110 | 2.0% |

Late deliveries carry an additional +3pp. Damage and defects resolve to
replacement 52% of the time; buyer's remorse almost never does (5%).


---

## Phase 1 output — the clean layer

`dbt/` builds two further schemas into the same DuckDB file. `raw` is never
modified.

| Schema | Models | Materialisation |
|---|---:|---|
| `staging` | 15 | views, 1:1 with `raw`, parsing and normalisation only |
| `marts` | 12 | tables, conformed star schema |

```bash
cd dbt && DBT_PROFILES_DIR=. dbt run && DBT_PROFILES_DIR=. dbt test
```

Defects retired by Phase 1: `N3` money encodings, `D1` timestamp formats,
`R2` refund sign, `R4` coupon dupes, `N1` bilingual reasons, `N2` status casing,
`C1` customer key, `J1` geo fan-out, `J2` payments fan-out, `D4` clock skew
(flagged, not hidden), `R8` stale snapshot (parsed in `staging`, deliberately
never promoted to `marts`).

Defects that **survive** cleaning and are Phase 2's job — they live in the
question, not the data: `R1` revenue definition, `R3` refund settlement filter,
`R5` orphan coupons, `R6` coupon scale, `R7` replacement handling, `D2` which
date, `D3` recognition quarter, `C2` churn window, `F1` status filter,
`F2` freight treatment, `J3` seller attribution.
