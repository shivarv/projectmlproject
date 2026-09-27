# BUSINESS_RULES.md — canonical business definitions

**Status:** DRAFT, pending freeze (see §13) · **Milestone:** M2 ·
**Applies to:** `data/olist_dirty.duckdb`, all schemas · **Currency:** BRL only

This document is the house definition of every contested term in this warehouse:
what a sale is, when it counts, what revenue means, who a customer is. It exists
because those questions have more than one defensible answer in this data, and an
experiment that lets each arm pick its own answer measures nothing.

It is written **before** the Cube.js semantic layer (M3) and before the gold
query set (M4), deliberately. If the rules were written afterwards they would
simply describe whatever the layer happened to do, and Arm C would be graded
against its own behaviour.

Rules are stated in business language, not SQL, and never name a table. Every
rule must be satisfiable against `raw.*` alone — `scripts/verify_business_rules.py`
proves that by deriving each figure twice, once from `raw.*` and once from
`marts.*`, and asserting the two agree.

---

## §0 · How this document is used

| Mode | Arm A (raw) | Arm B (dbt marts) | Arm C (Cube) |
|---|---|---|---|
| **Fair** | gets §1–§12 verbatim | gets §1–§12 verbatim | rules are compiled into the layer |
| **Realistic** | gets nothing from this file | gets nothing from this file | rules are compiled into the layer |

**§1–§12 are the Fair-mode handout. Appendix A is not.** Appendix A contains
worked reconciliation figures, and several of them are answers to gold queries —
handing it to an arm would leak the answer key. The handout stops at §12.

---

## §1 · Global conventions

**BR-01 · Currency.** Every monetary amount is Brazilian Real (BRL). There is no
currency variation in this warehouse and no conversion is ever applied. Report
amounts as plain numbers; do not annotate a currency code.

**BR-02 · Time zone.** All timestamps are naive local wall time
(America/São_Paulo) and are compared as written. No time-zone conversion, no
offset arithmetic. Where a timestamp arrived encoded as epoch seconds it
represents naive UTC wall time and is read back as that same wall-clock value.
*Trap: `D1`*

**BR-03 · Calendar.** The fiscal calendar is the Gregorian calendar. Q1 is
January–March, Q2 April–June, Q3 July–September, Q4 October–December. A quarter
is identified by the quarter its recognition date falls in (§3). Weeks start
Monday. *Trap: `D3`*

**BR-04 · As-of date.** Point-in-time metrics — churn, active customers, any
trailing window — are measured **as of 2018-08-31**. Orders exist after that date
(the last is 2018-10-17); that tail is deliberately held back so trailing windows
have room to close, and it is excluded from as-of metrics. It is *not* excluded
from period metrics: Q4 2018 is a real, if tiny, quarter. *Trap: `C2`*

**BR-05 · Rounding.** Money is carried at two decimal places. Round half-up, and
only once, at presentation. Rates and percentages are reported to two decimals.
Comparisons of money tolerate ±0.01; counts must match exactly.

**BR-06 · Null is not zero.** A missing amount is missing, not zero. An entity
that cannot be assigned to a period is excluded from every period rather than
being swept into the earliest or latest one, and §6.3 and §3.2 name the two
places where that actually happens.

---

## §2 · What counts as a sale

**BR-07 · In-scope orders.** Only orders with status **delivered** produce
revenue. Orders that are shipped, invoiced, processing, created, approved,
canceled or unavailable contribute nothing to revenue, units, AOV or customer
counts — no matter what money was collected against them. *Trap: `F1`*

**BR-08 · Status is a controlled vocabulary.** Order status is compared
case-insensitively against the normalised set `delivered`, `shipped`, `canceled`,
`unavailable`, `invoiced`, `processing`, `created`, `approved`. *Trap: `N2`*

**BR-09 · Status beats timestamps.** A small number of orders carry a customer
delivery timestamp while holding a non-delivered status. Status is authoritative:
those orders are **not** sales. The reverse also occurs — see BR-11. *Trap: `F1`*

---

## §3 · When revenue is recognised

**BR-10 · Recognition date.** Revenue is recognised on the date the order was
**delivered to the customer** — not ordered, not approved, not handed to the
carrier, not the estimated delivery date. "Revenue in period P" means revenue on
orders delivered in P. *Traps: `D2`, `D3`*

> This is the single most consequential rule here. 11,638 delivered orders fall
> in a different quarter by delivery date than by purchase date, so choosing the
> wrong date is not a rounding difference — it moves whole quarters.

**BR-11 · Orders that cannot be dated.** Eight orders are marked delivered but
carry no customer delivery timestamp. They have no recognition date, so they
belong to **no** period and are excluded from period revenue *and* from all-time
revenue. This keeps periods summing to the total. They remain in scope for
status-only questions such as "how many orders were delivered".

**BR-12 · Non-revenue dates.** Refunds recognise on their own settlement date
(§6) and are the one component that does not follow BR-10. Every other component
of revenue — merchandise, freight, discounts — recognises on the order's
recognition date, including discounts whose redemption timestamp falls in a
different period.

**BR-13 · Damaged clocks.** Where a resolution timestamp precedes its request
timestamp, the duration is **undefined**, not zero and not negative. Such rows
are excluded from duration averages and counted separately. Do not clamp to zero;
clamping hides the defect and biases the mean. *Trap: `D4`*

**BR-14 · Timestamp encodings.** Timestamps in the commerce-lifecycle tables
appear in four interleaved encodings: `2018-07-08 04:04:42`,
`2017-07-07T04:41:12Z`, epoch seconds, `25/09/2017 18:55` (day-first), and
date-only `2017-09-25`. All five parse to the same scale. **Day-first is the
Brazilian convention:** `07/08/2018` is 7 August, never 8 July. A date-only value
is midnight. *Trap: `D1`*

---

## §4 · What revenue is

**BR-15 · Net revenue.** Net revenue for a period is:

```
  merchandise sold          (in-scope orders recognised in the period)
+ freight charged           (same orders)
- discounts                 (same orders)
- settled refunds           (refunds that settled in the period, §6)
= NET REVENUE
```

This is the only definition of "revenue", "net revenue" or "recognised revenue".
A question that says "revenue" without qualification means this. *Trap: `R1`*

**BR-16 · Freight is revenue.** Shipping charged to the customer is revenue and
is included in gross and net revenue. A question that wants goods only must say
so; that quantity is **merchandise revenue** and it excludes freight. Never
report merchandise-only under the name "revenue". *Trap: `F2`*

**BR-17 · Payments are not revenue.** What was collected from the customer is a
cash fact, not a revenue fact. It reconciles to neither merchandise nor net
revenue — instalments, gift-card top-ups and partial captures all break the tie.
Use payments only to answer questions explicitly about payment or collection.
*Traps: `R1`, `J2`*

**BR-18 · Gross merchandise value (GMV).** GMV is merchandise + freight on
in-scope orders, before discounts and refunds. It is the numerator of AOV
(BR-39). GMV and net revenue are different numbers and neither is a default.

---

## §5 · Discounts

**BR-19 · Redemptions are unique by redemption id.** A coupon redemption is
identified by its redemption id. 306 redemptions were duplicated by an ETL
replay and must be counted once. **Deduplicate on the redemption id, never on
the amount**: 141 of the duplicate pairs carry the same value in two different
money encodings (`3,59` and `3.59`), so distinct-on-value silently fails to
collapse them and lands on a third wrong answer. *Trap: `R4`*

**BR-20 · Orphan coupon codes still reduce revenue.** 237 redemptions reference
coupon codes (prefix `LEGACY`) that are absent from the coupon master. The
discount was really given. They are retained in full and reported under coupon
code with a null campaign — never dropped by an inner join to the master.
*Trap: `R5`*

**BR-21 · The applied amount is authoritative.** The discount that reduces
revenue is the amount actually applied to the order, not a rate recomputed from
the coupon master. The master's `discount_value` is scale-ambiguous — a 5% coupon
is stored as `0.05` on some rows and `5.0` on others — so it is used only for
coupon-level analysis, where the convention is: **for percentage coupons, a value
of 1.0 or below is a fraction and above 1.0 is whole percent.** *Trap: `R6`*

**BR-22 · Discount scope.** A discount may apply to the order total, to items
only, or to freight. All three reduce net revenue identically. The scope matters
only when splitting revenue between merchandise and freight, where: items-only
discounts reduce merchandise, freight discounts reduce freight, and order-total
discounts are allocated pro rata by each order's merchandise/freight split.

**BR-23 · Discount period.** A discount is recognised in the period of the order
it discounts (BR-10), not the period it was redeemed in.

---

## §6 · Refunds

**BR-24 · Refunds are positive magnitudes.** A refund's amount is its magnitude.
The source stores 1,249 of 3,624 refunds as negative and 2,375 as positive for
the same semantic event, so summing them as stored nets refunds against each
other and understates the total roughly five-fold. Take the absolute value
before aggregating. *Trap: `R2`*

**BR-25 · Only settled refunds count.** A refund reduces revenue only when its
status is **processed**, compared case-insensitively. Pending, failed and
reversed refunds are money that never left the building and are never deducted.
Matching the lowercase literal alone silently drops the 450 refunds recorded as
`PROCESSED`. *Traps: `R3`, `N2`*

**BR-26 · Settlement period.** A settled refund is deducted in the period it
**settled**, not the period of the sale it refunds. Refunds routinely settle a
quarter or more after the order they relate to, and attributing them back to the
sale restates closed quarters. *Trap: `R3`*

**BR-27 · Refunds deduct only against recognised revenue.** A settled refund
reduces net revenue only if the order it refunds was itself in scope and
recognised (BR-07, BR-10). Refunds against orders that were canceled or never
delivered never had revenue to reverse; they are a cash and liability event,
reported separately as **refunds on unrecognised orders**, and excluded from net
revenue.

**BR-28 · Refunds that cannot be dated.** 257 settled refunds carry no settlement
or request timestamp at all. They cannot be assigned to a period and are excluded
from net revenue entirely, per BR-06. Their total is disclosed alongside any
all-time revenue figure rather than silently absorbed. *Trap: `R3`*

**BR-29 · Reason vocabulary.** Refund and return reasons are free text in two
languages across 26 spellings. Group only on the canonical set: `DAMAGED_IN_TRANSIT`,
`DEFECTIVE`, `WRONG_ITEM`, `NOT_AS_DESCRIBED`, `MISSING_PARTS`, `SIZE_FIT`,
`LATE_DELIVERY`, `NO_LONGER_WANTED`, plus three that occur on refunds only —
`ORDER_CANCELED`, `SERVICE_RECOVERY`, `CUSTOMER_COMPLAINT`. *Trap: `N1`*

| Canonical | Also appears as |
|---|---|
| `DAMAGED_IN_TRANSIT` | `damaged`, `DAMAGED`, `damaged_in_transit`, `Produto danificado` |
| `DEFECTIVE` | `defeito` |
| `WRONG_ITEM` | `wrong item`, `wrong-item`, `item_errado` |
| `NOT_AS_DESCRIBED` | `nao conforme anuncio` |
| `MISSING_PARTS` | `faltando pecas` |
| `SIZE_FIT` | `size/fit`, `tamanho` |
| `LATE_DELIVERY` | `late`, `atraso na entrega` |
| `NO_LONGER_WANTED` | `no longer wanted`, `changed_mind`, `arrependimento` |

**BR-30 · Return status vocabulary.** Return status canonicalises to `COMPLETED`
(also `closed`), `APPROVED`, `REJECTED` (**also `denied`**), `REQUESTED` (also
`open`), `IN_TRANSIT` (also `shipping_back`). A **rejected return is not a
return** and is excluded from return counts and return rate. Missing the `denied`
spelling alone counts 119 rejected returns as genuine. *Traps: `N1`, `N2`*

---

## §7 · Free replacements

**BR-31 · Replacements are units without revenue.** 1,436 damaged or defective
orders were resolved by shipping a new unit at no charge. They are real fulfilled
shipments with real cost. The rules: *Trap: `R7`*

- They generate **zero revenue** and never appear in revenue of any kind.
- They are **not orders**. They are excluded from order counts and from the AOV
  denominator — counting them craters AOV against revenue they did not earn.
- Their units are **not units sold**. They are reported, when asked for, as
  **free units shipped**, a separate measure.
- Their cost is real and reduces margin: replacement COGS plus absorbed freight.
- They do not cancel or reduce the original sale. The original order keeps its
  revenue; the replacement adds cost.

**BR-32 · Who bears replacement cost.** Replacement cost is attributed by its
borne-by party: seller, marketplace, or carrier insurance. **Marketplace margin
is reduced only by the marketplace-borne share.** Total replacement cost is a
marketplace-wide figure and is not a P&L line.

---

## §8 · Counting customers, orders and units

**BR-33 · A customer is a person.** The customer key on an order is
**order-scoped**: it is minted per order, so counting it counts orders, not
people. The person is the **customer unique id**. 99,441 order-scoped keys
resolve to 96,096 people. Every customer count, churn rate, repeat rate and
per-customer average uses the person. *Trap: `C1`*

**BR-34 · Churn.** A customer is **churned as of the as-of date (BR-04) if their
most recent order is more than 180 days before it**. The denominator is every
person who has ordered at least once on or before the as-of date. Customers whose
most recent order falls inside the trailing 180 days are **active**, not churned.
*Trap: `C2`*

> Phrase this carefully. "No order in the 180 days *following their last order*"
> is degenerate — by construction nobody orders after their own last order, so
> that reading returns 100% churn for every evaluable customer. The window is
> anchored to the as-of date, not to the customer's last order.

**BR-35 · Repeat customer.** A person with two or more in-scope orders, ever.
96.9% of people buy exactly once, so a repeat rate near 3% is correct and a
result near 50% means the order-scoped key leaked in (BR-33).

**BR-36 · Units.** One order line is one unit sold. Units sold counts lines on
in-scope orders (BR-07) and excludes free replacement units (BR-31).

**BR-37 · Order count.** Orders are counted at order grain, deduplicated. An
order with several items, several payment instalments, several sellers or several
coupons is **one** order.

**BR-38 · Return rate.** Return rate is distinct in-scope orders with at least
one non-rejected return (BR-30), divided by in-scope orders in the same period.
It is order-based, not unit-based; state the basis if a unit-based rate is
wanted.

**BR-39 · AOV.** Average order value is GMV (BR-18) divided by order count
(BR-37), over in-scope orders only. State explicitly if an AOV net of discounts
and refunds is wanted; the default is gross.

---

## §9 · Joins that must not multiply

**BR-40 · One row per order for money.** Payments arrive one row per instalment,
and 2,961 orders have more than one. Payments must be collapsed to order grain
**before** being joined to anything, or every order-level amount on those orders
is multiplied. *Trap: `J2`*

**BR-41 · One location per postcode.** Geolocation holds 1,000,163 points across
19,015 postcodes — up to 1,146 rows for a single postcode. Joining orders to it
un-collapsed multiplies revenue by up to three orders of magnitude. The canonical
location of a postcode is the **median** latitude and longitude of its points,
with the modal city and state. *Trap: `J1`*

**BR-42 · Seller attribution is per line.** 1,278 orders contain items from more
than one seller. Revenue attributes to the seller **of each line**, never of the
order. There is no "the seller" of a multi-seller order, and an order-level seller
join both multiplies the order and mis-assigns its revenue. Order counts by
seller are counts of *orders containing that seller's items* and do not sum to
total orders. *Trap: `J3`*

**BR-43 · Coupons and returns are per line or per event.** An order may carry
several coupon redemptions and several return lines. Both must be aggregated to
order grain before joining to order-level money.

---

## §10 · Money encoding

**BR-44 · Brazilian money literals.** Amounts in the commerce-lifecycle tables
appear as `187.47`, `R$ 272,76` and `1.234,56`. **If a comma is present, the
comma is the decimal separator and dots are thousands separators.** If no comma
is present, the dot is the decimal separator. `1.234,56` is one thousand two
hundred thirty-four; `1.234` without a comma is one point two three four.
*Trap: `N3`*

---

## §11 · Sources that are not authoritative

**BR-45 · The finance revenue snapshot is not the answer.** A table of
pre-computed per-order revenue exists, with a column literally named
`net_revenue`. **It is never authoritative for any question in this warehouse.**
It is: cut off at 2018-07-01 and so missing 12,824 orders; double-counting the
306 duplicate redemptions; dropping goodwill refunds; treating pending and failed
refunds as settled; and ignoring replacement cost entirely. Revenue is computed
from BR-15 every time. The snapshot may be queried only when the question is
explicitly about the finance export itself. *Trap: `R8`*

---

## §12 · House constants

These have **no support in the data** — the warehouse records no commission and
no tax. They are house policy, fixed here so that questions about them have one
answer. They are the most arbitrary rules in this document and are flagged as
such.

**BR-46 · Marketplace take rate.** The marketplace commission is **12% of
merchandise value** on in-scope orders. Freight is not commissionable.

**BR-47 · Seller payout.** Seller payout = merchandise − commission (BR-46) +
freight − settled refunds attributable to that seller's lines (BR-27) − that
seller's borne replacement cost (BR-32).

**BR-48 · Tax.** Listed prices are **tax-inclusive** at a flat **18%** rate on
merchandise; freight is untaxed. Tax-exclusive revenue = merchandise ÷ 1.18 +
freight. "Revenue" unqualified is tax-inclusive (BR-15).

---

## §13 · Freeze and change control

This document freezes at M2, **before** the Cube.js model (M3) and the gold query
set (M4) are authored. Once frozen:

1. Its SHA-256 is recorded here and in the run manifest of every experiment.
2. `scripts/verify_business_rules.py` must exit 0 on the frozen revision. It
   re-derives all 56 quoted figures from `raw.*` and from `marts.*` independently
   and asserts both that the two agree and that the values in Appendix A still
   hold. A failure means either a rule is not expressible on raw or a mart has
   drifted from the rule it claims to encode.
3. Any later edit is logged below with a reason, and every gold query authored
   under the previous revision is re-verified.

| Revision | Date | Change | Reason |
|---|---|---|---|
| r1 | 2026-09-27 | Initial draft, BR-01 … BR-48 | M2 |

**SHA-256:** _(recorded at freeze)_

---

## Appendix A — reconciliation figures

**Not part of the Fair-mode handout (§0).** These are the arithmetic consequences
of §1–§12, and several are answers to gold queries. They exist so that a gold
query's result can be checked against an independently derived number before it
enters the set, per the Phase 3 authoring protocol.

All figures below are asserted by `scripts/verify_business_rules.py`, derived
twice — once from `raw.*`, once from `marts.*`.

### A.1 Net revenue, all time (BR-15)

| Component | BRL |
|---|---:|
| Merchandise | 13,220,248.93 |
| Freight | 2,198,145.90 |
| Discounts | −319,864.16 |
| Settled refunds on recognised orders | −165,511.06 |
| **Net revenue** | **14,933,019.61** |

In-scope recognised orders: 96,470 · Units sold: 110,189

Disclosed alongside, and excluded from the above by rule:

| Excluded | Rule | BRL |
|---|---|---:|
| Refunds on unrecognised orders | BR-27 | 198,126.44 |
| Settled refunds with no date | BR-28 | 23,743.23 (257 refunds) |
| Free replacement units | BR-31 | 1,479 units, 112,080.40 COGS |
| Marketplace-borne replacement cost | BR-32 | 43,943.53 |

### A.2 Net revenue, Q2 2018 (BR-10, BR-26)

| Component | BRL |
|---|---:|
| Merchandise | 3,123,806.48 |
| Freight | 518,357.87 |
| Discounts | −70,222.75 |
| Settled refunds | −44,102.25 |
| **Net revenue** | **3,527,839.35** |

Recognised orders: 21,790 · Units: 25,052 · Q1 2018 net revenue: 2,811,785.05

### A.3 Defect magnitudes

| Figure | Value |
|---|---:|
| Delivered orders (status only, BR-07) | 96,478 |
| …of which have no delivery date (BR-11) | 8 |
| Orders whose delivery quarter ≠ purchase quarter (BR-10) | 11,638 |
| Settled dated refunds on recognised orders | 1,924 |
| …settling in a different quarter than recognition (BR-26) | 725 |
| Signed sum of all refunds vs. magnitude sum (BR-24) | 91,167.57 vs 458,616.03 |
| Duplicate coupon redemptions (BR-19) | 306 |
| Redemptions after dedupe · total discount | 15,293 · 328,743.81 |
| Orphan-code redemptions · value (BR-20) | 237 · 4,631.00 |
| Refund reason spellings (BR-29) | 26 |
| Returns with reversed clocks (BR-13) | 53 |
| Orders with >1 payment row (BR-40) | 2,961 |
| Postcodes · max rows for one postcode (BR-41) | 19,015 · 1,146 |
| Multi-seller orders (BR-42) | 1,278 |
| Orders missing from the finance snapshot (BR-45) | 12,824 |

### A.4 Customers and churn (BR-33, BR-34)

| Figure | Value |
|---|---:|
| Order-scoped customer keys | 99,441 |
| People (customer unique id) | 96,096 |
| People with exactly one order | 93,099 (96.88%) |
| Churn denominator: people ordering on or before 2018-08-31 | 96,078 |
| Churned at 180 days as of 2018-08-31 | 57,550 |
| **Churn rate** | **59.90%** |

Counting the order-scoped key instead inflates the denominator to 99,420 and the
churn rate to 60.54% — off by only 0.64pp, close enough to look right, which is
the trap. The same substitution is far louder on repeat rate (BR-35), where it
is the difference between 3% and a number that cannot be true.

### A.5 Return rate (BR-38)

Non-rejected returns on delivered orders: 4,353 ÷ 96,478 = **4.51%**.
Counting rejected returns as returns gives 4,472 (4.64%).
