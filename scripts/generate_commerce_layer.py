"""
Generate the commerce-lifecycle tables Olist does not ship with:
coupons, redemptions, returns/RMA, refunds, free replacements, and a
finance revenue snapshot.

Everything is keyed to REAL Olist order_ids / product_ids / timestamps.
The nine original Olist CSVs are never modified.

Data hygiene issues are injected ON PURPOSE -- this is the "dirty warehouse"
half of the semantic-layer experiment. Every defect is recoverable with
enough care; none of them destroy information.
"""
import numpy as np
import pandas as pd
import duckdb
import hashlib
from pathlib import Path

SEED = 20181017
rng = np.random.default_rng(SEED)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_olist"
OUT = ROOT / "data" / "raw_commerce"
OUT.mkdir(parents=True, exist_ok=True)

con = duckdb.connect()
q = lambda s: con.execute(s).df()

orders = q(f"""
    select order_id, customer_id, order_status,
           order_purchase_timestamp, order_approved_at,
           order_delivered_customer_date, order_estimated_delivery_date
    from read_csv_auto('{RAW}/olist_orders_dataset.csv')
""")
items = q(f"""
    select order_id, order_item_id, product_id, seller_id, price, freight_value
    from read_csv_auto('{RAW}/olist_order_items_dataset.csv')
""")
pay = q(f"""
    select order_id, sum(payment_value) as paid
    from read_csv_auto('{RAW}/olist_order_payments_dataset.csv') group by 1
""")
rev = q(f"""
    select order_id, min(review_score) as review_score
    from read_csv_auto('{RAW}/olist_order_reviews_dataset.csv') group by 1
""")

orders = orders.merge(pay, on="order_id", how="left").merge(rev, on="order_id", how="left")
order_totals = items.groupby("order_id").agg(
    item_total=("price", "sum"), freight_total=("freight_value", "sum"),
    n_items=("order_item_id", "count")).reset_index()
orders = orders.merge(order_totals, on="order_id", how="left")

def sid(prefix, i):
    """Olist-style 32-char hex surrogate key, stable across runs."""
    return hashlib.md5(f"{prefix}:{SEED}:{i}".encode()).hexdigest()

# ---------------------------------------------------------------- dirt helpers
def messy_ts(series, frac_alt=0.18, frac_null=0.0):
    """Mixed timestamp encodings: ISO-T, BR dd/mm/yyyy, date-only, epoch."""
    s = pd.to_datetime(series, errors="coerce")
    out = s.dt.strftime("%Y-%m-%d %H:%M:%S").astype(object)
    u = rng.random(len(s))
    alt = u < frac_alt
    style = rng.integers(0, 4, len(s))
    iso   = alt & (style == 0)
    br    = alt & (style == 1)
    donly = alt & (style == 2)
    epoch = alt & (style == 3)
    out[iso]   = s[iso].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out[br]    = s[br].dt.strftime("%d/%m/%Y %H:%M")
    out[donly] = s[donly].dt.strftime("%Y-%m-%d")
    # explicit second resolution: pandas>=3 may infer us/ms and silently
    # produce epochs that are 1000x off (unrecoverable dirt, not messy dirt)
    out[epoch] = s[epoch].astype("datetime64[s]").astype("int64").astype("string")
    out[s.isna()] = None
    if frac_null:
        out[rng.random(len(s)) < frac_null] = None
    return out

def messy_money(vals, frac_brl=0.15, frac_comma=0.12, frac_null=0.0):
    """Mixed money encodings: 12.5 / 'R$ 12,50' / '12,50' -- BR locale reality."""
    v = np.round(np.asarray(vals, dtype=float), 2)
    out = np.array([f"{x:.2f}" for x in v], dtype=object)
    u = rng.random(len(v))
    brl = u < frac_brl
    com = (u >= frac_brl) & (u < frac_brl + frac_comma)
    out[brl] = [f"R$ {x:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".") for x in v[brl]]
    out[com] = [f"{x:.2f}".replace(".", ",") for x in v[com]]
    out[np.isnan(v)] = None
    if frac_null:
        out[rng.random(len(v)) < frac_null] = None
    return out

def messy_case(values, variants):
    """Swap a canonical code for one of its real-world spelling variants."""
    values = np.asarray(values, dtype=object)
    out = values.copy()
    for canon, alts in variants.items():
        m = values == canon
        n = int(m.sum())
        if n:
            out[m] = rng.choice([canon] + alts, size=n, p=[0.55] + [0.45/len(alts)]*len(alts))
    return out

def add_whitespace(arr, frac=0.04):
    arr = np.asarray(arr, dtype=object).copy()
    m = rng.random(len(arr)) < frac
    arr[m] = [f"  {x} " if x is not None else None for x in arr[m]]
    return arr

# =============================================================== 1. COUPONS
# Trap: coupon_type vocabulary is inconsistent, and for percent coupons the
# discount_value is sometimes 15 (meaning 15%) and sometimes 0.15. The only
# way to disambiguate is the magnitude + the type string.
CAMPAIGNS = [
    ("WELCOME",  "New customer acquisition"), ("BLACKFRIDAY", "Black Friday"),
    ("NATAL",    "Christmas"),                ("FRETEGRATIS", "Free shipping push"),
    ("VOLTA",    "Win-back lapsed buyer"),    ("APP",         "Mobile app install"),
    ("CARNAVAL", "Carnaval promo"),           ("MAESDIA",     "Mothers Day"),
    ("CLEARANCE","Inventory clearance"),      ("VIP",         "Loyalty tier"),
]
coupon_rows = []
for i in range(64):
    camp, desc = CAMPAIGNS[i % len(CAMPAIGNS)]
    code = f"{camp}{10 + (i * 7) % 90}"
    kind = rng.choice(["PCT", "FIXED", "FREESHIP"], p=[0.55, 0.32, 0.13])
    if kind == "PCT":
        pct = int(rng.choice([5, 10, 12, 15, 20, 25, 30]))
        # half the percent coupons are stored as a fraction instead
        as_fraction = rng.random() < 0.5
        value = round(pct / 100, 4) if as_fraction else float(pct)
        ctype = rng.choice(["PCT", "percent", "PERCENTAGE", "%"])
        min_spend = float(rng.choice([0, 0, 50, 100, 150]))
        max_disc = float(rng.choice([0, 0, 50, 100]))
    elif kind == "FIXED":
        value = float(rng.choice([10, 15, 20, 25, 30, 40, 50]))
        ctype = rng.choice(["FIXED", "BRL", "amount", "fixed_amount"])
        min_spend = float(rng.choice([0, 80, 120, 200]))
        max_disc = 0.0
    else:
        value = 0.0
        ctype = rng.choice(["FREESHIP", "free_shipping", "FRETE"])
        min_spend = float(rng.choice([0, 99, 149]))
        max_disc = 0.0
    start = pd.Timestamp("2016-09-01") + pd.Timedelta(days=int(rng.integers(0, 700)))
    end = start + pd.Timedelta(days=int(rng.choice([14, 30, 45, 60, 90, 180])))
    coupon_rows.append(dict(
        coupon_code=code, campaign_name=camp, campaign_description=desc,
        coupon_type=ctype, discount_value=value,
        min_order_value=min_spend, max_discount_cap=max_disc,
        valid_from=start, valid_to=end,
        is_active=rng.choice(["Y", "N", "1", "0", "true", "TRUE", "false"]),
        applies_to=rng.choice(["ORDER_TOTAL", "ITEMS_ONLY", "FREIGHT", "order_total"]),
        stackable=rng.choice(["Y", "N", "N", "N"]),
    ))
coupons = pd.DataFrame(coupon_rows).drop_duplicates(subset=["coupon_code"]).reset_index(drop=True)
coupons["valid_from"] = messy_ts(coupons["valid_from"], frac_alt=0.30)
coupons["valid_to"]   = messy_ts(coupons["valid_to"],   frac_alt=0.30, frac_null=0.06)
coupons["coupon_code"] = add_whitespace(coupons["coupon_code"], 0.05)

# ======================================================= 2. COUPON REDEMPTIONS
# Traps: (a) ~2% duplicated rows from an ETL replay -> naive SUM double-counts;
#        (b) ~1.5% orphan coupon_codes not in the master;
#        (c) discount amounts stored in three different string encodings.
elig = orders[orders["item_total"].notna()].copy()
n_redeem = int(len(elig) * 0.155)
pick = rng.choice(len(elig), size=n_redeem, replace=False)
red = elig.iloc[pick].reset_index(drop=True)

clean_codes = coupons["coupon_code"].str.strip().values
cidx = rng.integers(0, len(coupons), n_redeem)
cm = coupons.iloc[cidx].reset_index(drop=True)

disc = np.zeros(n_redeem)
ctype_l = cm["coupon_type"].str.lower().values
dval = cm["discount_value"].values
is_pct = np.isin(ctype_l, ["pct", "percent", "percentage", "%"])
pct_rate = np.where(dval <= 1.0, dval, dval / 100.0)
disc = np.where(is_pct, red["item_total"].values * pct_rate, disc)
is_fixed = np.isin(ctype_l, ["fixed", "brl", "amount", "fixed_amount"])
disc = np.where(is_fixed, np.minimum(dval, red["item_total"].values), disc)
is_ship = np.isin(ctype_l, ["freeship", "free_shipping", "frete"])
disc = np.where(is_ship, red["freight_total"].fillna(0).values, disc)
cap = cm["max_discount_cap"].values
disc = np.where(cap > 0, np.minimum(disc, cap), disc)
disc = np.round(np.maximum(disc, 0), 2)

redeemed_at = pd.to_datetime(red["order_purchase_timestamp"])
order_coupons = pd.DataFrame({
    "redemption_id": [sid("redeem", i) for i in range(n_redeem)],
    "order_id": red["order_id"].values,
    "customer_id": red["customer_id"].values,
    "coupon_code": clean_codes[cidx],
    "discount_amount_applied": disc,
    "discount_applies_to": cm["applies_to"].values,
    "redeemed_at": redeemed_at.values,
    "channel": rng.choice(["web", "WEB", "app", "APP", "mobile_web", None], n_redeem,
                          p=[.34, .10, .28, .09, .14, .05]),
})
# (b) orphan FKs
orph = rng.random(n_redeem) < 0.015
order_coupons.loc[orph, "coupon_code"] = [
    f"LEGACY{k}" for k in rng.integers(100, 999, int(orph.sum()))]
# (a) ETL replay duplicates -- same redemption_id. NOTE: messy_money runs
# after this, so duplicate pairs may end up with DIFFERENT encodings of the
# same value; dedupe must key on redemption_id, not on the rendered amount.
dupes = order_coupons.sample(frac=0.02, random_state=7)
order_coupons = pd.concat([order_coupons, dupes], ignore_index=True)
order_coupons = order_coupons.sample(frac=1.0, random_state=11).reset_index(drop=True)
# (c) encodings
order_coupons["redeemed_at"] = messy_ts(order_coupons["redeemed_at"], frac_alt=0.20)
order_coupons["discount_amount_applied"] = messy_money(
    order_coupons["discount_amount_applied"], frac_brl=0.16, frac_comma=0.13)
order_coupons["coupon_code"] = add_whitespace(order_coupons["coupon_code"], 0.03)

# ============================================================== 3. RETURNS / RMA
# Return propensity is driven by the REAL review score, so the table carries
# genuine signal rather than noise.
deliv = orders[orders["order_status"] == "delivered"].copy()
deliv = deliv[deliv["item_total"].notna()]
rate = deliv["review_score"].map({1: .22, 2: .14, 3: .07, 4: .03, 5: .018}).fillna(.04).values
late = (pd.to_datetime(deliv["order_delivered_customer_date"])
        > pd.to_datetime(deliv["order_estimated_delivery_date"])).fillna(False).values
rate = np.clip(rate + late * 0.03, 0, 1)
ret_mask = rng.random(len(deliv)) < rate
ret_orders = deliv[ret_mask].reset_index(drop=True)
n_ret = len(ret_orders)

# one returned line item per RMA, chosen from that order's real items
first_item = items.sort_values(["order_id", "order_item_id"]).groupby("order_id").first().reset_index()
ret_orders = ret_orders.merge(
    first_item[["order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"]],
    on="order_id", how="left")

REASONS = ["DAMAGED_IN_TRANSIT", "DEFECTIVE", "WRONG_ITEM", "NOT_AS_DESCRIBED",
           "MISSING_PARTS", "SIZE_FIT", "LATE_DELIVERY", "NO_LONGER_WANTED"]
rp = np.array([.19, .16, .12, .15, .07, .09, .10, .12])
reason = rng.choice(REASONS, n_ret, p=rp / rp.sum())

# Resolution depends on reason: damage/defect mostly becomes a FREE REPLACEMENT.
resolution = np.empty(n_ret, dtype=object)
for r in REASONS:
    m = reason == r
    k = int(m.sum())
    if not k:
        continue
    if r in ("DAMAGED_IN_TRANSIT", "DEFECTIVE", "MISSING_PARTS"):
        p = {"REPLACEMENT": .52, "REFUND": .33, "STORE_CREDIT": .09, "REJECTED": .06}
    elif r in ("WRONG_ITEM", "NOT_AS_DESCRIBED"):
        p = {"REPLACEMENT": .34, "REFUND": .48, "STORE_CREDIT": .11, "REJECTED": .07}
    elif r == "SIZE_FIT":
        p = {"REPLACEMENT": .30, "REFUND": .52, "STORE_CREDIT": .12, "REJECTED": .06}
    else:
        p = {"REPLACEMENT": .05, "REFUND": .58, "STORE_CREDIT": .14, "REJECTED": .23}
    resolution[m] = rng.choice(list(p), k, p=list(p.values()))

status = np.where(resolution == "REJECTED", "rejected",
         rng.choice(["completed", "approved", "requested", "in_transit"],
                    n_ret, p=[.72, .14, .08, .06]))

delivered_at = pd.to_datetime(ret_orders["order_delivered_customer_date"])
requested_at = delivered_at + pd.to_timedelta(rng.integers(1, 30, n_ret), unit="D") \
                            + pd.to_timedelta(rng.integers(0, 86400, n_ret), unit="s")
received_at  = requested_at + pd.to_timedelta(rng.integers(2, 21, n_ret), unit="D")
resolved_at  = received_at  + pd.to_timedelta(rng.integers(0, 14, n_ret), unit="D")
received_at  = received_at.where(~np.isin(status, ["requested", "in_transit"]))
resolved_at  = resolved_at.where(np.isin(status, ["completed", "rejected"]))

order_returns = pd.DataFrame({
    "return_id": [sid("rma", i) for i in range(n_ret)],
    "order_id": ret_orders["order_id"].values,
    "order_item_id": ret_orders["order_item_id"].values,
    "product_id": ret_orders["product_id"].values,
    "seller_id": ret_orders["seller_id"].values,
    "customer_id": ret_orders["customer_id"].values,
    "return_reason_code": reason,
    "return_status": status,
    "resolution": resolution,
    "quantity_returned": rng.choice([1, 1, 1, 2], n_ret, p=[.88, .05, .04, .03]),
    "item_price_at_purchase": ret_orders["price"].values,
    "freight_at_purchase": ret_orders["freight_value"].values,
    "requested_at": requested_at.values,
    "received_at": received_at.values,
    "resolved_at": resolved_at.values,
    "inspection_notes": rng.choice(
        ["caixa amassada", "produto quebrado", "cliente desistiu", "item errado enviado",
         "sem avarias", "embalagem violada", None, None, None], n_ret),
})

# --- dirt ---------------------------------------------------------------
# free-text reason variants mixed in with the codes (PT + EN + snake_case)
order_returns["return_reason_code"] = messy_case(order_returns["return_reason_code"], {
    "DAMAGED_IN_TRANSIT": ["damaged", "Produto danificado", "damaged_in_transit", "DAMAGED"],
    "DEFECTIVE": ["defeito", "defective", "Defective"],
    "WRONG_ITEM": ["wrong item", "item_errado", "WRONG-ITEM"],
    "NOT_AS_DESCRIBED": ["nao conforme anuncio", "not_as_described"],
    "NO_LONGER_WANTED": ["arrependimento", "changed_mind", "no longer wanted"],
    "LATE_DELIVERY": ["atraso na entrega", "late"],
    "SIZE_FIT": ["tamanho", "size/fit"],
    "MISSING_PARTS": ["faltando pecas", "missing_parts"],
})
order_returns["return_status"] = messy_case(order_returns["return_status"], {
    "completed": ["COMPLETED", "Completed", "closed"],
    "approved": ["APPROVED"], "rejected": ["REJECTED", "denied"],
    "requested": ["REQUESTED", "open"], "in_transit": ["IN_TRANSIT", "shipping_back"],
})
# ~0.8% clock-skew rows where resolved_at precedes requested_at
skew = rng.random(n_ret) < 0.008
order_returns.loc[skew, "resolved_at"] = (
    pd.to_datetime(order_returns.loc[skew, "requested_at"]) - pd.Timedelta(days=3)).values
order_returns["requested_at"] = messy_ts(order_returns["requested_at"], frac_alt=0.17)
order_returns["received_at"]  = messy_ts(order_returns["received_at"],  frac_alt=0.17)
order_returns["resolved_at"]  = messy_ts(order_returns["resolved_at"],  frac_alt=0.17)
order_returns["item_price_at_purchase"] = messy_money(order_returns["item_price_at_purchase"])
order_returns["freight_at_purchase"]    = messy_money(order_returns["freight_at_purchase"])

# ================================================================= 4. REFUNDS
# Traps: (a) refund_amount sign is INCONSISTENT (some +, some -);
#        (b) failed/pending refunds must be excluded from net revenue;
#        (c) canceled orders refund outside the RMA flow (return_id is NULL);
#        (d) SHIPPING_ONLY refunds touch freight, not item revenue.
rr = order_returns.copy()
rr["_price"] = ret_orders["price"].values
rr["_freight"] = ret_orders["freight_value"].values
rr["_res"] = resolution
rr["_status_clean"] = pd.Series(status).values
# clean (pre-dirtied) resolution timestamps for downstream date math
rr["_resolved_clean"] = pd.Series(resolved_at).values

refund_src = rr[(rr["_res"] == "REFUND") & (rr["_status_clean"].isin(["completed", "approved"]))]
n_rf = len(refund_src)
rtype = rng.choice(["FULL", "PARTIAL", "SHIPPING_ONLY"], n_rf, p=[.66, .26, .08])
amt = np.where(rtype == "FULL", refund_src["_price"].values + refund_src["_freight"].values,
      np.where(rtype == "PARTIAL", refund_src["_price"].values * rng.uniform(.2, .8, n_rf),
               refund_src["_freight"].values))
refunds_rma = pd.DataFrame({
    "order_id": refund_src["order_id"].values,
    "return_id": refund_src["return_id"].values,
    "refund_type": rtype,
    "refund_amount": np.round(amt, 2),
    "refund_reason": refund_src["return_reason_code"].values,
    "requested_at": pd.to_datetime(refund_src["_resolved_clean"], errors="coerce").values,
})

# (c) cancellations -> refunds with no RMA at all
canc = orders[(orders["order_status"].isin(["canceled", "unavailable"]))
              & (orders["paid"].notna()) & (orders["paid"] > 0)].copy()
canc = canc[rng.random(len(canc)) < 0.82]
refunds_canc = pd.DataFrame({
    "order_id": canc["order_id"].values,
    "return_id": None,
    "refund_type": "FULL",
    "refund_amount": np.round(canc["paid"].values, 2),
    "refund_reason": "ORDER_CANCELED",
    "requested_at": (pd.to_datetime(canc["order_purchase_timestamp"])
                     + pd.to_timedelta(rng.integers(1, 12, len(canc)), unit="D")).values,
})

# goodwill credits with neither a return nor a cancellation
gw_pool = deliv[(deliv["review_score"] <= 2)].sample(frac=0.06, random_state=3)
refunds_gw = pd.DataFrame({
    "order_id": gw_pool["order_id"].values,
    "return_id": None,
    "refund_type": "GOODWILL",
    "refund_amount": np.round(np.minimum(
        gw_pool["item_total"].values * rng.uniform(.05, .25, len(gw_pool)), 60), 2),
    "refund_reason": rng.choice(["LATE_DELIVERY", "customer_complaint", "service_recovery"],
                                len(gw_pool)),
    "requested_at": (pd.to_datetime(gw_pool["order_delivered_customer_date"])
                     + pd.to_timedelta(rng.integers(1, 20, len(gw_pool)), unit="D")).values,
})

refunds = pd.concat([refunds_rma, refunds_canc, refunds_gw], ignore_index=True)
refunds = refunds.sample(frac=1.0, random_state=5).reset_index(drop=True)
n_all = len(refunds)
refunds.insert(0, "refund_id", [sid("refund", i) for i in range(n_all)])
refunds["refund_status"] = rng.choice(
    ["processed", "PROCESSED", "pending", "failed", "reversed"],
    n_all, p=[.72, .12, .08, .055, .025])
refunds["refund_method"] = rng.choice(
    ["credit_card_reversal", "boleto_transfer", "store_credit", "pix", "CREDIT_CARD_REVERSAL"],
    n_all, p=[.52, .18, .14, .08, .08])
refunds["processed_at"] = (pd.to_datetime(refunds["requested_at"])
                           + pd.to_timedelta(rng.integers(1, 15, n_all), unit="D"))
refunds.loc[refunds["refund_status"].isin(["pending", "failed"]), "processed_at"] = pd.NaT
refunds["gateway_reference"] = [sid("gw", i)[:16] for i in range(n_all)]

# (a) THE sign trap: ~40% of rows store the refund as a negative number
neg = rng.random(n_all) < 0.40
refunds["refund_amount"] = np.where(neg, -refunds["refund_amount"], refunds["refund_amount"])
refunds["requested_at"] = messy_ts(refunds["requested_at"], frac_alt=0.16)
refunds["processed_at"] = messy_ts(refunds["processed_at"], frac_alt=0.16)
refunds["refund_amount"] = messy_money(refunds["refund_amount"], frac_brl=0.14, frac_comma=0.11)

# ================================================== 5. FREE REPLACEMENT ORDERS
# Damaged/defective -> a brand-new unit ships at zero charge.
# Trap: these are real fulfilled shipments with units > 0 and revenue == 0.
# Counting them as orders destroys AOV; counting their units as sales
# overstates volume; their COGS is a real cost that never hits revenue.
rep_src = rr[(rr["_res"] == "REPLACEMENT")
             & (rr["_status_clean"].isin(["completed", "approved"]))].reset_index(drop=True)
n_rep = len(rep_src)
orig_price = rep_src["_price"].values
ship_at = pd.to_datetime(rep_src["_resolved_clean"], errors="coerce") \
          + pd.to_timedelta(rng.integers(1, 8, n_rep), unit="D")

replacement_orders = pd.DataFrame({
    "replacement_order_id": [sid("repl", i) for i in range(n_rep)],
    "original_order_id": rep_src["order_id"].values,
    "return_id": rep_src["return_id"].values,
    "customer_id": rep_src["customer_id"].values,
    "product_id": rep_src["product_id"].values,
    "seller_id": rep_src["seller_id"].values,
    "quantity_shipped": rep_src["quantity_returned"].values,
    "charged_to_customer": 0.00,
    "replacement_cogs": np.round(orig_price * rng.uniform(.45, .72, n_rep), 2),
    "freight_absorbed": np.round(rep_src["_freight"].values * rng.uniform(.8, 1.1, n_rep), 2),
    "cost_borne_by": rng.choice(["SELLER", "MARKETPLACE", "CARRIER_INSURANCE"],
                                n_rep, p=[.55, .30, .15]),
    "replacement_status": rng.choice(["shipped", "delivered", "SHIPPED", "pending_stock"],
                                     n_rep, p=[.22, .62, .10, .06]),
    "shipped_at": ship_at.values,
})
replacement_orders["delivered_at"] = (
    ship_at + pd.to_timedelta(rng.integers(2, 25, n_rep), unit="D"))
replacement_orders.loc[
    replacement_orders["replacement_status"].str.lower() == "pending_stock", "shipped_at"] = pd.NaT
replacement_orders.loc[
    ~replacement_orders["replacement_status"].str.lower().isin(["delivered"]),
    "delivered_at"] = pd.NaT
replacement_orders["shipped_at"]   = messy_ts(replacement_orders["shipped_at"], frac_alt=0.15)
replacement_orders["delivered_at"] = messy_ts(replacement_orders["delivered_at"], frac_alt=0.15)
replacement_orders["replacement_cogs"] = messy_money(replacement_orders["replacement_cogs"])
replacement_orders["freight_absorbed"] = messy_money(replacement_orders["freight_absorbed"])

# ============================================== 6. FINANCE REVENUE SNAPSHOT
# A plausible-looking BI export that is SUBTLY WRONG. It is the red herring:
# an LLM that grabs `net_revenue` because the name matches the question will
# be confidently incorrect. Its documented flaws:
#   - stale: cut off at 2018-06-30, missing the final ~12.8k orders
#   - double-counts the duplicated coupon redemptions
#   - ignores goodwill refunds entirely
#   - counts pending/failed refunds as if they had settled
#   - ignores replacement COGS
def to_num(s):
    return pd.to_numeric(
        pd.Series(s, dtype="object").astype("string")
          .str.replace(r"R\$\s*", "", regex=True).str.strip()
          .str.replace(r"\.(?=\d{3}(?:\D|$))", "", regex=True)
          .str.replace(",", ".", regex=False),
        errors="coerce")

oc = order_coupons.copy()
oc["_d"] = to_num(oc["discount_amount_applied"])
disc_naive = oc.groupby("order_id")["_d"].sum()          # duplicates included

rf = refunds.copy()
rf["_a"] = to_num(rf["refund_amount"]).abs()
rf_naive = rf[rf["refund_reason"] != "service_recovery"]  # goodwill partially dropped
rf_naive = rf_naive.groupby("order_id")["_a"].sum()

snap = orders[["order_id", "order_purchase_timestamp", "item_total", "freight_total"]].copy()
snap = snap[pd.to_datetime(snap["order_purchase_timestamp"]) < pd.Timestamp("2018-07-01")]
snap["gross_merchandise_value"] = snap["item_total"].fillna(0).round(2)
snap["freight_revenue"] = snap["freight_total"].fillna(0).round(2)
snap["discount_total"] = snap["order_id"].map(disc_naive).fillna(0).round(2)
snap["refund_total"] = snap["order_id"].map(rf_naive).fillna(0).round(2)
snap["net_revenue"] = (snap["gross_merchandise_value"] + snap["freight_revenue"]
                       - snap["discount_total"] - snap["refund_total"]).round(2)
snap["currency"] = "BRL"
snap["snapshot_date"] = "2018-07-01"
snap["source_system"] = "FIN_DW_EXPORT_v2"
finance_snapshot = snap[["order_id", "snapshot_date", "currency",
                         "gross_merchandise_value", "freight_revenue", "discount_total",
                         "refund_total", "net_revenue", "source_system"]]

# ==================================================================== WRITE
tables = {
    "coupons": coupons,
    "order_coupons": order_coupons,
    "order_returns": order_returns.drop(columns=[c for c in order_returns.columns
                                                 if c.startswith("_")]),
    "refunds": refunds,
    "replacement_orders": replacement_orders,
    "finance_order_revenue_snapshot": finance_snapshot,
}
for name, df in tables.items():
    path = OUT / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"  {name:<34} {len(df):>7,} rows  {path.stat().st_size/1e6:>6.2f} MB")

# ================================================================= DUCKDB
db = ROOT / "data" / "olist_dirty.duckdb"
if db.exists():
    db.unlink()
d = duckdb.connect(str(db))
d.execute("create schema if not exists raw;")
for f in sorted(RAW.glob("*.csv")):
    t = f.stem.replace("olist_", "").replace("_dataset", "")
    d.execute(f"create or replace table raw.{t} as select * from read_csv_auto('{f}');")
for name in tables:
    f = OUT / f"{name}.csv"
    # all_varchar keeps the injected encoding mess intact instead of silently
    # coercing or nulling it at load time
    d.execute(f"""create or replace table raw.{name} as
                  select * from read_csv('{f}', all_varchar=true, header=true);""")
print("\nraw schema:")
for t, n in d.execute("""select table_name, estimated_size from duckdb_tables()
                         where schema_name='raw' order by table_name""").fetchall():
    print(f"  raw.{t:<38} {int(n):>9,}")
d.close()
print(f"\nDuckDB -> {db}")
