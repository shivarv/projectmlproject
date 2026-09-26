"""Every injected defect must be RECOVERABLE. This asserts that:
   - every money string parses back to a number
   - every timestamp string parses back to a date in the Olist era
   - no FK dangles except the ones we injected deliberately
Fails loudly if the generator ever produces lossy dirt."""
import duckdb, sys

# If a comma is present it is the decimal separator (BR locale) and dots are
# thousands separators; otherwise the dot is the decimal separator.
MONEY = """
  try_cast(
    case when position(',' in replace(replace({c},'R$',''),' ','')) > 0
         then replace(replace(replace(replace({c},'R$',''),' ',''),'.',''),',','.')
         else replace(replace({c},'R$',''),' ','')
    end as double)"""

TS = """
  coalesce(
    try_strptime(trim({c}), '%Y-%m-%d %H:%M:%S'),
    try_strptime(trim({c}), '%Y-%m-%dT%H:%M:%SZ'),
    try_strptime(trim({c}), '%d/%m/%Y %H:%M'),
    try_strptime(trim({c}), '%Y-%m-%d'),
    case when regexp_matches(trim({c}),'^[0-9]{{9,11}}$')
         then to_timestamp(try_cast(trim({c}) as bigint)) end
  )"""

CHECKS = [
    ("order_coupons", "discount_amount_applied", MONEY),
    ("order_coupons", "redeemed_at", TS),
    ("order_returns", "item_price_at_purchase", MONEY),
    ("order_returns", "freight_at_purchase", MONEY),
    ("order_returns", "requested_at", TS),
    ("order_returns", "received_at", TS),
    ("order_returns", "resolved_at", TS),
    ("refunds", "refund_amount", MONEY),
    ("refunds", "requested_at", TS),
    ("refunds", "processed_at", TS),
    ("replacement_orders", "replacement_cogs", MONEY),
    ("replacement_orders", "freight_absorbed", MONEY),
    ("replacement_orders", "shipped_at", TS),
    ("replacement_orders", "delivered_at", TS),
    ("coupons", "valid_from", TS),
    ("coupons", "valid_to", TS),
]

d = duckdb.connect("data/olist_dirty.duckdb", read_only=True)
bad = 0
print(f"{'table.column':<45} {'non-null':>9} {'unparsed':>9}")
print("-" * 66)
for tbl, col, expr in CHECKS:
    e = expr.format(c=col)
    nn, un = d.execute(f"""
        select count(*) filter (where {col} is not null),
               count(*) filter (where {col} is not null and ({e}) is null)
        from raw.{tbl}""").fetchone()
    flag = "" if un == 0 else "  <-- LOSSY"
    if un: bad += 1
    print(f"{tbl + '.' + col:<45} {nn:>9,} {un:>9,}{flag}")

print("\nFK integrity (deliberate orphans noted):")
fks = [
 ("order_coupons -> orders", "raw.order_coupons oc", "oc.order_id", "raw.orders o", "o.order_id", 0),
 ("order_returns -> orders", "raw.order_returns r", "r.order_id", "raw.orders o", "o.order_id", 0),
 ("refunds -> orders", "raw.refunds f", "f.order_id", "raw.orders o", "o.order_id", 0),
 ("replacement_orders -> orders", "raw.replacement_orders p", "p.original_order_id", "raw.orders o", "o.order_id", 0),
 ("replacement_orders -> returns", "raw.replacement_orders p", "p.return_id", "raw.order_returns r", "r.return_id", 0),
]
for name, lt, lk, rt, rk, expect in fks:
    n = d.execute(f"select count(*) from {lt} where not exists "
                  f"(select 1 from {rt} where {rk}={lk})").fetchone()[0]
    ok = "ok" if n == expect else f"UNEXPECTED (expected {expect})"
    if n != expect: bad += 1
    print(f"  {name:<40} dangling={n:<6} {ok}")

n = d.execute("""select count(*) from raw.order_coupons oc where not exists
 (select 1 from raw.coupons c where trim(c.coupon_code)=trim(oc.coupon_code))""").fetchone()[0]
print(f"  {'order_coupons -> coupons':<40} dangling={n:<6} deliberate orphan FKs")

print("\nRESULT:", "FAIL" if bad else "PASS - all injected dirt is reversible")
sys.exit(1 if bad else 0)
