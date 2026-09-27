#!/usr/bin/env python3
"""Verify every check figure in BUSINESS_RULES.md, twice.

Each headline number is derived independently two ways:

  RAW    — from `raw.*` only, with the messy encodings parsed inline. This is
           the arm-independent derivation; it proves a rule is expressible
           without the dbt layer, so no arm is flattered by the answer key.
  MARTS  — from `marts.*`, i.e. the Phase 1 dbt build.

The two must agree. Disagreement means either a rule is unimplementable on raw
or a mart has drifted from the rule it claims to encode; both are bugs, and
both must be resolved before the number enters the gold set.

Usage:
    python scripts/verify_business_rules.py            # assert against locked values
    python scripts/verify_business_rules.py --emit     # print figures, assert nothing
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal

import duckdb

DB = "data/olist_dirty.duckdb"
AS_OF = "2018-08-31"
CHURN_WINDOW_DAYS = 180

# --- raw-side parsers, mirroring dbt/macros/parsers.sql --------------------


def money(col: str) -> str:
    """BR money: '187.47' | 'R$ 272,76' | '1.234,56' -> DECIMAL(14,2)."""
    stripped = f"replace(replace({col}, 'R$', ''), ' ', '')"
    return f"""cast(case
        when {col} is null then null
        when position(',' in {stripped}) > 0
            then replace(replace({stripped}, '.', ''), ',', '.')
        else {stripped}
    end as decimal(14,2))"""


def ts(col: str) -> str:
    """Four interleaved timestamp encodings -> TIMESTAMP."""
    return f"""coalesce(
        try_strptime(trim({col}), '%Y-%m-%d %H:%M:%S'),
        try_strptime(trim({col}), '%Y-%m-%dT%H:%M:%SZ'),
        try_strptime(trim({col}), '%d/%m/%Y %H:%M'),
        try_strptime(trim({col}), '%Y-%m-%d'),
        case when regexp_matches(trim({col}), '^[0-9]{{9,11}}$')
             then cast(to_timestamp(try_cast(trim({col}) as bigint)) at time zone 'UTC' as timestamp)
        end)"""


# --- raw-side building blocks ----------------------------------------------

# raw.orders is one of the nine real Olist tables and lands already typed, so
# the timestamp parser is not needed here -- only the generated tables carry the
# four interleaved encodings.
RAW_ORDERS = """
    select
        order_id,
        customer_id,
        lower(trim(order_status))                as order_status,
        order_purchase_timestamp                 as purchased_at,
        order_delivered_customer_date            as delivered_at,
        case when lower(trim(order_status)) = 'delivered'
             then order_delivered_customer_date end as recognized_at
    from raw.orders
"""

RAW_ITEMS = """
    select
        order_id,
        cast(price as decimal(14,2))            as item_price,
        cast(freight_value as decimal(14,2))    as freight_value
    from raw.order_items
"""

# BR-R4: dedupe on redemption_id. The duplicate pairs carry different money
# encodings, so DISTINCT on the value does not collapse them -- key on the id.
RAW_REDEMPTIONS = f"""
    select redemption_id, order_id, coupon_code, discount_amount, discount_applies_to
    from (
        select
            redemption_id,
            order_id,
            trim(coupon_code)                       as coupon_code,
            {money('discount_amount_applied')}      as discount_amount,
            upper(trim(discount_applies_to))        as discount_applies_to,
            row_number() over (partition by redemption_id order by order_id) as rn
        from raw.order_coupons
    ) where rn = 1
"""

# BR-R2 (abs), BR-R3 (settled = status 'processed', case-insensitively).
RAW_REFUNDS = f"""
    select
        refund_id,
        order_id,
        abs({money('refund_amount')})            as refund_amount,
        lower(trim(refund_status)) = 'processed' as is_settled,
        case when lower(trim(refund_status)) = 'processed'
             then {ts('processed_at')} end       as settled_at
    from raw.refunds
"""

RAW_CUSTOMERS = """
    select customer_id, trim(customer_unique_id) as customer_unique_id
    from raw.customers
"""


def q(con, sql: str):
    return con.execute(sql).fetchone()


def build(con) -> None:
    con.execute(f"create or replace temp view r_orders as {RAW_ORDERS}")
    con.execute(f"create or replace temp view r_items as {RAW_ITEMS}")
    con.execute(f"create or replace temp view r_red as {RAW_REDEMPTIONS}")
    con.execute(f"create or replace temp view r_refunds as {RAW_REFUNDS}")
    con.execute(f"create or replace temp view r_customers as {RAW_CUSTOMERS}")


# --- the checks -------------------------------------------------------------
# Each entry: (id, label, raw_sql, marts_sql, locked_value)

def checks(period: str | None = None):
    """period: None for all-time, or a quarter-start date string."""
    if period is None:
        raw_period_rev = ""
        raw_period_ref = ""
        m_period_rev = ""
        m_period_ref = ""
    else:
        raw_period_rev = f"and date_trunc('quarter', o.recognized_at) = date '{period}'"
        raw_period_ref = f"and date_trunc('quarter', f.settled_at) = date '{period}'"
        m_period_rev = raw_period_rev
        m_period_ref = raw_period_ref

    return [
        (
            "merchandise",
            f"""select sum(i.item_price) from r_items i join r_orders o using (order_id)
                where o.order_status = 'delivered' and o.recognized_at is not null {raw_period_rev}""",
            f"""select sum(i.item_price) from marts.fct_order_items i join marts.fct_orders o using (order_id)
                where o.is_delivered and o.recognized_at is not null {m_period_rev}""",
        ),
        (
            "freight",
            f"""select sum(i.freight_value) from r_items i join r_orders o using (order_id)
                where o.order_status = 'delivered' and o.recognized_at is not null {raw_period_rev}""",
            f"""select sum(i.freight_value) from marts.fct_order_items i join marts.fct_orders o using (order_id)
                where o.is_delivered and o.recognized_at is not null {m_period_rev}""",
        ),
        (
            "discounts",
            f"""select sum(c.discount_amount) from r_red c join r_orders o using (order_id)
                where o.order_status = 'delivered' and o.recognized_at is not null {raw_period_rev}""",
            f"""select sum(c.discount_amount) from marts.fct_coupon_redemptions c join marts.fct_orders o using (order_id)
                where o.is_delivered and o.recognized_at is not null {m_period_rev}""",
        ),
        (
            "settled_refunds",
            f"""select sum(f.refund_amount) from r_refunds f join r_orders o using (order_id)
                where f.is_settled and f.settled_at is not null
                  and o.order_status = 'delivered' and o.recognized_at is not null {raw_period_ref}""",
            f"""select sum(f.refund_amount) from marts.fct_refunds f join marts.fct_orders o using (order_id)
                where f.is_settled and f.settled_at is not null
                  and o.is_delivered and o.recognized_at is not null {m_period_ref}""",
        ),
        (
            "order_count",
            f"""select count(*) from r_orders o
                where o.order_status = 'delivered' and o.recognized_at is not null {raw_period_rev}""",
            f"""select count(*) from marts.fct_orders o
                where o.is_delivered and o.recognized_at is not null {m_period_rev}""",
        ),
        (
            "units_sold",
            f"""select count(*) from r_items i join r_orders o using (order_id)
                where o.order_status = 'delivered' and o.recognized_at is not null {raw_period_rev}""",
            f"""select count(*) from marts.fct_order_items i join marts.fct_orders o using (order_id)
                where o.is_delivered and o.recognized_at is not null {m_period_rev}""",
        ),
    ]


STANDALONE = [
    (
        "customers_people",
        "select count(distinct customer_unique_id) from r_customers",
        "select count(*) from marts.dim_customers",
    ),
    (
        "customers_order_keys",
        "select count(distinct customer_id) from r_customers",
        "select count(distinct customer_id) from marts.fct_orders",
    ),
    (
        "churn_denominator",
        f"""select count(*) from (
              select c.customer_unique_id, max(o.purchased_at) last_at
              from r_orders o join r_customers c using (customer_id)
              group by 1) where last_at <= timestamp '{AS_OF}'""",
        f"select count(*) from marts.dim_customers where last_purchase_at <= timestamp '{AS_OF}'",
    ),
    (
        "churned_customers",
        f"""select count(*) from (
              select c.customer_unique_id, max(o.purchased_at) last_at
              from r_orders o join r_customers c using (customer_id)
              group by 1)
            where last_at <= timestamp '{AS_OF}'
              and last_at < timestamp '{AS_OF}' - interval {CHURN_WINDOW_DAYS} day""",
        f"""select count(*) from marts.dim_customers
            where last_purchase_at <= timestamp '{AS_OF}'
              and last_purchase_at < timestamp '{AS_OF}' - interval {CHURN_WINDOW_DAYS} day""",
    ),
    (
        "redemptions_deduped",
        "select count(*) from r_red",
        "select count(*) from marts.fct_coupon_redemptions",
    ),
    (
        "discount_total_all",
        "select sum(discount_amount) from r_red",
        "select sum(discount_amount) from marts.fct_coupon_redemptions",
    ),
    (
        "orphan_redemptions",
        """select count(*) from r_red c
           left join (select distinct trim(coupon_code) cc from raw.coupons) m on m.cc = c.coupon_code
           where m.cc is null""",
        "select count(*) from marts.fct_coupon_redemptions where is_orphan_coupon",
    ),
    (
        "refunds_unassignable",
        """select count(*) from r_refunds where is_settled and settled_at is null""",
        "select count(*) from marts.fct_refunds where is_settled and settled_at is null",
    ),
    (
        "refunds_unassignable_brl",
        """select sum(refund_amount) from r_refunds where is_settled and settled_at is null""",
        "select sum(refund_amount) from marts.fct_refunds where is_settled and settled_at is null",
    ),
    (
        "refunds_unrecognized_orders",
        """select sum(f.refund_amount) from r_refunds f join r_orders o using (order_id)
           where f.is_settled and f.settled_at is not null
             and not (o.order_status = 'delivered' and o.recognized_at is not null)""",
        """select sum(f.refund_amount) from marts.fct_refunds f join marts.fct_orders o using (order_id)
           where f.is_settled and f.settled_at is not null
             and not (o.is_delivered and o.recognized_at is not null)""",
    ),
    (
        "free_units_shipped",
        f"select sum(cast(quantity_shipped as integer)) from raw.replacement_orders",
        "select sum(quantity_shipped) from marts.fct_replacements",
    ),
    (
        "replacement_cogs",
        f"select sum({money('replacement_cogs')}) from raw.replacement_orders",
        "select sum(replacement_cogs) from marts.fct_replacements",
    ),
    (
        "orders_recognition_undated",
        """select count(*) from r_orders where order_status = 'delivered' and recognized_at is null""",
        "select count(*) from marts.fct_orders where is_delivered and recognized_at is null",
    ),
    (
        "quarter_shift_orders",
        """select count(*) from r_orders where order_status = 'delivered' and recognized_at is not null
           and date_trunc('quarter', purchased_at) <> date_trunc('quarter', recognized_at)""",
        """select count(*) from marts.fct_orders where is_delivered and recognized_at is not null
           and date_trunc('quarter', purchased_at) <> date_trunc('quarter', recognized_at)""",
    ),
    (
        "orphan_redemptions_brl",
        """select sum(c.discount_amount) from r_red c
           left join (select distinct trim(coupon_code) cc from raw.coupons) m on m.cc = c.coupon_code
           where m.cc is null""",
        "select sum(discount_amount) from marts.fct_coupon_redemptions where is_orphan_coupon",
    ),
    (
        "duplicate_redemptions",
        "select (select count(*) from raw.order_coupons) - (select count(*) from r_red)",
        "select (select count(*) from raw.order_coupons) - (select count(*) from marts.fct_coupon_redemptions)",
    ),
    (
        "refund_quarter_shift_vs_recognition",
        """select count(*) from r_refunds f join r_orders o using (order_id)
           where f.is_settled and f.settled_at is not null
             and o.order_status = 'delivered' and o.recognized_at is not null
             and date_trunc('quarter', f.settled_at) <> date_trunc('quarter', o.recognized_at)""",
        """select count(*) from marts.fct_refunds f join marts.fct_orders o using (order_id)
           where f.is_settled and f.settled_at is not null
             and o.is_delivered and o.recognized_at is not null
             and date_trunc('quarter', f.settled_at) <> date_trunc('quarter', o.recognized_at)""",
    ),
    (
        "refunds_settled_dated_on_recognised",
        """select count(*) from r_refunds f join r_orders o using (order_id)
           where f.is_settled and f.settled_at is not null
             and o.order_status = 'delivered' and o.recognized_at is not null""",
        """select count(*) from marts.fct_refunds f join marts.fct_orders o using (order_id)
           where f.is_settled and f.settled_at is not null
             and o.is_delivered and o.recognized_at is not null""",
    ),
    (
        "refunds_naive_net_sum",
        f"select sum({money('refund_amount')}) from raw.refunds",
        None,
    ),
    (
        "delivered_orders",
        "select count(*) from r_orders where order_status = 'delivered'",
        "select count(*) from marts.fct_orders where is_delivered",
    ),
    (
        "single_order_customers",
        """select count(*) from (
             select c.customer_unique_id from r_orders o join r_customers c using (customer_id)
             group by 1 having count(*) = 1)""",
        "select count(*) from marts.dim_customers where lifetime_order_count = 1",
    ),
    (
        "returns_counted_delivered",
        f"""select count(distinct t.order_id) from raw.order_returns t join r_orders o using (order_id)
            where o.order_status = 'delivered'
              -- BR-24: 'denied' is a spelling of REJECTED; matching the literal
              -- alone silently counts 119 rejected returns as genuine returns.
              and lower(trim(t.return_status)) not in ('rejected', 'denied')""",
        """select count(distinct t.order_id) from marts.fct_returns t join marts.fct_orders o using (order_id)
           where o.is_delivered and t.return_status <> 'REJECTED'""",
    ),
    (
        "clock_skew_returns",
        f"""select count(*) from raw.order_returns
            where {ts('resolved_at')} < {ts('requested_at')}""",
        "select count(*) from marts.fct_returns where has_timestamp_inconsistency",
    ),
    (
        "geo_max_rows_per_zip",
        "select max(c) from (select geolocation_zip_code_prefix, count(*) c from raw.geolocation group by 1)",
        None,
    ),
    (
        "geo_zips",
        "select count(distinct geolocation_zip_code_prefix) from raw.geolocation",
        "select count(*) from marts.dim_geography",
    ),
    (
        "payment_fanout_orders",
        "select count(*) from (select order_id, count(*) c from raw.order_payments group by 1 having c > 1)",
        "select count(*) from marts.fct_payments where payment_row_count > 1",
    ),
    (
        "multi_seller_orders",
        """select count(*) from (
             select order_id from raw.order_items group by 1 having count(distinct seller_id) > 1)""",
        "select count(*) from marts.fct_orders where seller_count > 1",
    ),
    (
        "replacement_cost_marketplace",
        f"""select sum({money('replacement_cogs')} + {money('freight_absorbed')}) from raw.replacement_orders
            where upper(trim(cost_borne_by)) = 'MARKETPLACE'""",
        """select sum(total_replacement_cost) from marts.fct_replacements
           where cost_borne_by = 'MARKETPLACE'""",
    ),
    (
        "snapshot_orders_missing",
        """select (select count(*) from raw.orders)
                - (select count(distinct order_id) from raw.finance_order_revenue_snapshot)""",
        None,
    ),
    (
        "refund_reason_spellings",
        "select count(distinct upper(trim(refund_reason))) from raw.refunds",
        None,
    ),
    (
        "refunds_abs_sum_all",
        "select sum(refund_amount) from r_refunds",
        "select sum(refund_amount) from marts.fct_refunds",
    ),
    (
        "refunds_uppercase_processed",
        "select count(*) from raw.refunds where trim(refund_status) = 'PROCESSED'",
        None,
    ),
    (
        "duplicate_pairs_mixed_encoding",
        """select count(*) from (
             select redemption_id from raw.order_coupons group by 1
             having count(*) > 1 and count(distinct trim(discount_amount_applied)) > 1)""",
        None,
    ),
    (
        "wrong_key_churn_denominator",
        f"""select count(*) from (select customer_id, max(purchased_at) last_at from r_orders group by 1)
            where last_at <= timestamp '{AS_OF}'""",
        None,
    ),
    (
        "wrong_key_churned",
        f"""select count(*) from (select customer_id, max(purchased_at) last_at from r_orders group by 1)
            where last_at <= timestamp '{AS_OF}'
              and last_at < timestamp '{AS_OF}' - interval {CHURN_WINDOW_DAYS} day""",
        None,
    ),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true", help="print figures instead of asserting")
    args = ap.parse_args()

    con = duckdb.connect(DB, read_only=True)
    build(con)

    failures: list[str] = []
    emitted: dict[str, object] = {}

    def run(name: str, raw_sql: str, marts_sql: str | None):
        raw_v = q(con, raw_sql)[0]
        if marts_sql is not None:
            marts_v = q(con, marts_sql)[0]
            if raw_v != marts_v:
                failures.append(f"{name}: raw={raw_v!r} != marts={marts_v!r}")
        emitted[name] = raw_v
        return raw_v

    print("=== all-time (recognised basis) ===")
    vals = {}
    for name, raw_sql, marts_sql in checks(None):
        vals[name] = run(f"alltime.{name}", raw_sql, marts_sql)
        print(f"  {name:20s} {vals[name]}")
    net = vals["merchandise"] + vals["freight"] - vals["discounts"] - vals["settled_refunds"]
    print(f"  {'NET REVENUE':20s} {net}")
    emitted["alltime.net_revenue"] = net

    for period, label in [("2018-04-01", "Q2 2018"), ("2018-01-01", "Q1 2018")]:
        print(f"\n=== {label} (recognised basis) ===")
        vals = {}
        for name, raw_sql, marts_sql in checks(period):
            vals[name] = run(f"{period}.{name}", raw_sql, marts_sql)
            print(f"  {name:20s} {vals[name]}")
        net = vals["merchandise"] + vals["freight"] - vals["discounts"] - vals["settled_refunds"]
        print(f"  {'NET REVENUE':20s} {net}")
        emitted[f"{period}.net_revenue"] = net

    print("\n=== standalone ===")
    for name, raw_sql, marts_sql in STANDALONE:
        v = run(name, raw_sql, marts_sql)
        print(f"  {name:28s} {v}")

    if failures:
        print("\nRAW vs MARTS DISAGREEMENT:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 1

    print("\nraw and marts agree on all %d figures." % len(emitted))

    if not args.emit:
        bad = [f"{k}: expected {v}, got {emitted[k]}" for k, v in LOCKED.items()
               if k in emitted and str(emitted[k]) != str(v)]
        missing = [k for k in LOCKED if k not in emitted]
        if bad or missing:
            print("\nLOCKED-VALUE MISMATCH (BUSINESS_RULES.md is stale or the data moved):", file=sys.stderr)
            for b in bad:
                print(f"  {b}", file=sys.stderr)
            for m in missing:
                print(f"  {m}: not computed", file=sys.stderr)
            return 1
        print("all %d locked figures in BUSINESS_RULES.md still hold." % len(LOCKED))
    return 0


# Figures quoted in BUSINESS_RULES.md. Editing these means editing the rules.
LOCKED = {
    "alltime.merchandise": "13220248.93",
    "alltime.freight": "2198145.90",
    "alltime.discounts": "319864.16",
    "alltime.settled_refunds": "165511.06",
    "alltime.net_revenue": "14933019.61",
    "alltime.order_count": "96470",
    "alltime.units_sold": "110189",
    "2018-04-01.merchandise": "3123806.48",
    "2018-04-01.freight": "518357.87",
    "2018-04-01.discounts": "70222.75",
    "2018-04-01.settled_refunds": "44102.25",
    "2018-04-01.net_revenue": "3527839.35",
    "2018-04-01.order_count": "21790",
    "customers_people": "96096",
    "customers_order_keys": "99441",
    "churn_denominator": "96078",
    "churned_customers": "57550",
    "redemptions_deduped": "15293",
    "discount_total_all": "328743.81",
    "orphan_redemptions": "237",
    "refunds_unassignable": "257",
    "refunds_unassignable_brl": "23743.23",
    "refunds_unrecognized_orders": "198126.44",
    "free_units_shipped": "1479",
    "replacement_cogs": "112080.40",
    "orders_recognition_undated": "8",
    "quarter_shift_orders": "11638",
    "orphan_redemptions_brl": "4631.00",
    "duplicate_redemptions": "306",
    "refund_quarter_shift_vs_recognition": "725",
    "refunds_settled_dated_on_recognised": "1924",
    "refunds_naive_net_sum": "91167.57",
    "delivered_orders": "96478",
    "single_order_customers": "93099",
    "returns_counted_delivered": "4353",
    "clock_skew_returns": "53",
    "geo_max_rows_per_zip": "1146",
    "geo_zips": "19015",
    "payment_fanout_orders": "2961",
    "multi_seller_orders": "1278",
    "replacement_cost_marketplace": "43943.53",
    "snapshot_orders_missing": "12824",
    "refund_reason_spellings": "26",
    "refunds_abs_sum_all": "458616.03",
    "refunds_uppercase_processed": "450",
    "duplicate_pairs_mixed_encoding": "141",
    "wrong_key_churn_denominator": "99420",
    "wrong_key_churned": "60184",
    "2018-01-01.net_revenue": "2811785.05",
    "alltime.free_units_shipped": None,
}
LOCKED.pop("alltime.free_units_shipped")

if __name__ == "__main__":
    sys.exit(main())
