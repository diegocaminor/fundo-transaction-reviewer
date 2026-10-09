"""Seeded synthetic data generator.

Ground truth is assigned per line template, never derived from keywords.
`revenue` and `risk_signal` always come from the shared schema functions.
Amounts are integer cents internally; credit > 0, debit < 0.
"""

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from . import casa_norte
from .schema import (
    is_revenue,
    risk_signal_for,
    validate_business,
    validate_transaction,
    validate_truth_covers,
)

END_DATE = date(2026, 6, 30)

PFC = {
    "income": ("INCOME", "INCOME_OTHER_INCOME"),
    "transfer_in": ("TRANSFER_IN", "TRANSFER_IN_ACCOUNT_TRANSFER"),
    "transfer_out": ("TRANSFER_OUT", "TRANSFER_OUT_ACCOUNT_TRANSFER"),
    "food": ("FOOD_AND_DRINK", "FOOD_AND_DRINK_RESTAURANT"),
    "payroll": ("GENERAL_SERVICES", "GENERAL_SERVICES_OTHER_GENERAL_SERVICES"),
    "rent": ("RENT_AND_UTILITIES", "RENT_AND_UTILITIES_RENT"),
    "utility": ("RENT_AND_UTILITIES", "RENT_AND_UTILITIES_GAS_AND_ELECTRICITY"),
    "bank_fees": ("BANK_FEES", "BANK_FEES_INSUFFICIENT_FUNDS"),
    "loan": ("LOAN_PAYMENTS", "LOAN_PAYMENTS_OTHER_PAYMENT"),
    "gambling": ("ENTERTAINMENT", "ENTERTAINMENT_CASINOS_AND_GAMBLING"),
    "general": ("GENERAL_MERCHANDISE", "GENERAL_MERCHANDISE_OTHER_GENERAL_MERCHANDISE"),
    "transport": ("TRANSPORTATION", "TRANSPORTATION_GAS"),
    "medical": ("MEDICAL", "MEDICAL_OTHER_MEDICAL"),
    "travel": ("TRAVEL", "TRAVEL_FLIGHTS"),
}
NOISE_PFC = tuple(PFC.values())
NOISE_RATE = 0.08


@dataclass(frozen=True)
class LineSpec:
    descriptions: tuple
    lo: float  # dollars, magnitude
    hi: float
    credit: bool = False
    rate: float | None = None  # per-day probability
    every: int | None = None  # fixed interval in days, random phase
    count: int | None = None  # exactly this many random days
    days: tuple | None = None  # explicit day indices
    from_day: int = 0
    weekdays: bool = False
    channel: str = "other"
    merchant: str | None = None
    group: str = "none"
    business: bool = True
    notes: str = ""
    trap: str | None = None
    pfc: str = "general"


@dataclass(frozen=True)
class Archetype:
    business_id: str
    name: str
    type: str
    history_days: int
    bank_charges_nsf_fee: bool
    routine: tuple
    traps: tuple = ()
    fixed: tuple = ()


def L(descriptions, lo, hi, credit=False, **kw):
    if isinstance(descriptions, str):
        descriptions = (descriptions,)
    return LineSpec(tuple(descriptions), lo, hi, credit, **kw)


R_SALES = "Customer sales payment; operating revenue."
SAVINGS_OUT = "Sweep to the owner's own savings account; internal transfer."
FEE_NOTE = "Routine operating expense."


def sweep(count):
    return L(("ONLINE TRANSFER TO SAVINGS {n}", "ONLINE TRANSFER TO SAV {n}"),
             1500, 4000, count=count, channel="online", group="internal_transfer",
             notes=SAVINGS_OUT, pfc="transfer_out")


def opex(descs, lo, hi, pfc="general", **kw):
    return L(descs, lo, hi, notes=FEE_NOTE, pfc=pfc, **kw)


def sales(descs, lo, hi, **kw):
    kw.setdefault("pfc", "income")
    return L(descs, lo, hi, credit=True, notes=R_SALES, **kw)


def payroll(descs, lo, hi, every=14):
    return opex(descs, lo, hi, pfc="payroll", every=every, channel="online")


def monthly(descs, lo, hi, pfc="utility"):
    return opex(descs, lo, hi, pfc=pfc, every=30, channel="online")


def trap(descs, lo, hi, trap_name, group, notes, credit=False, **kw):
    return L(descs, lo, hi, credit=credit, group=group, notes=notes, trap=trap_name, **kw)


ARCHETYPES = (
    Archetype(
        "biz_01", "Casa Norte Restaurant", "restaurant", 90, True,
        routine=(
            sales(("SQUARE INC {n} DEPOSIT", "SQ *CASA NORTE {n} DEPOSIT"), 900, 1900,
                  rate=1.0, merchant="Square"),
            sales(("DOORDASH INC PAYOUT", "UBER EATS PAYOUT {n}"), 150, 600, rate=0.25),
            opex(("SYSCO FOODSERVICE {n}", "US FOODS INC {n}", "RESTAURANT DEPOT #{n}"),
                 300, 1800, pfc="food", rate=0.55),
            payroll(("GUSTO PAYROLL {n}", "ADP PAYROLL {n}"), 6000, 7500),
            monthly("ACH RENT 123 MAIN ST LLC", 4800, 4800, "rent"),
            monthly(("CON EDISON UTILITY {n}", "NATIONAL GRID GAS {n}"), 650, 900),
            monthly("STATE FARM INSURANCE PREMIUM", 480, 480, "general"),
            monthly("TOAST INC SOFTWARE", 165, 165, "general"),
            monthly("MONTHLY MAINTENANCE FEE", 25, 25, "bank_fees"),
            opex(("POS DEBIT HOME DEPOT #{n}", "POS PURCHASE WALMART #{n}",
                  "POS PURCHASE COSTCO WHSE #{n}"), 40, 350, rate=0.2,
                 channel="in store"),
            sweep(3),
        ),
        fixed=casa_norte.TRAP_LINES + casa_norte.REPAY_LINES,
    ),
    Archetype(
        "biz_02", "Glow Hair Studio", "hair salon", 90, False,
        routine=(
            sales("SQUARE INC {n} DEPOSIT", 250, 700, rate=1.0, weekdays=True,
                  merchant="Square"),
            sales(("ZELLE PAYMENT FROM CLIENT {n}", "VENMO CASHOUT {n}"), 60, 200,
                  rate=0.7, channel="online"),
            payroll("GUSTO PAYROLL {n}", 2400, 3200),
            monthly("ACH SUITE 4 RENT", 2200, 2200, "rent"),
            monthly(("DUKE ENERGY {n}", "COMCAST BUSINESS {n}"), 120, 260),
            opex(("SALLY BEAUTY SUPPLY #{n}", "SALONCENTRIC ORDER {n}"), 80, 400,
                 rate=0.15, channel="in store"),
            opex(("POS PURCHASE TARGET #{n}", "POS PURCHASE AMAZON MKTPL"), 20, 150,
                 rate=0.15, channel="in store"),
            monthly("MONTHLY SERVICE FEE", 15, 15, "bank_fees"),
            sweep(2),
        ),
        traps=(
            trap("ITEM PAID INTO OD", 40, 300, "item_paid_into_od", "overdraft",
                 "Item paid into overdraft; overdraft event (this bank charges no NSF fee).",
                 count=7, pfc="bank_fees"),
        ),
    ),
    Archetype(
        "biz_03", "Ridgeline Freight LLC", "trucking", 61, True,
        routine=(
            sales(("CH ROBINSON FREIGHT PMT {n}", "XPO LOGISTICS ACH {n}",
                   "COYOTE LOGISTICS PAYMENT {n}"), 2500, 6500, rate=0.5,
                  channel="online"),
            opex(("LOVES TRAVEL STOP #{n}", "PILOT FLYING J #{n}", "COMDATA FUEL CARD {n}"),
                 300, 900, pfc="transport", rate=0.7, channel="in store"),
            payroll("ADP DRIVER SETTLEMENT {n}", 1800, 2600, every=7),
            monthly("PENSKE TRUCK LEASING ACH", 3100, 3100, "loan"),
            monthly("PROGRESSIVE COMMERCIAL INS", 1250, 1250, "general"),
            opex(("TA TRAVEL CENTER REPAIR #{n}", "FLEETPRIDE PARTS {n}"), 150, 1200,
                 rate=0.1, channel="in store"),
            opex("E-ZPASS REPLENISH", 100, 100, pfc="transport", rate=0.12,
                 channel="online"),
            opex(("POS PURCHASE DOLLAR GENERAL #{n}", "POS PURCHASE WALMART #{n}"), 20, 120,
                 rate=0.6, channel="in store"),
            sweep(2),
        ),
    ),
    Archetype(
        "biz_04", "Maple & Main Boutique", "retail store", 90, True,
        routine=(
            sales("SQUARE INC {n} DEPOSIT", 700, 1800, rate=1.0, merchant="Square"),
            sales("AMERICAN EXPRESS MERCH SETTLE {n}", 200, 700, rate=0.3),
            opex(("FASHION DISTRIBUTORS INV {n}", "FAIRE WHOLESALE {n}"), 300, 1500,
                 rate=0.35, channel="online"),
            payroll("PAYCHEX PAYROLL {n}", 3200, 4200),
            monthly("ACH RETAIL PLAZA LEASE", 3600, 3600, "rent"),
            monthly(("PSE&G UTILITY {n}", "VERIZON BUSINESS {n}"), 180, 420),
            monthly("HARTFORD BUSINESS INSURANCE", 310, 310, "general"),
            monthly("MONTHLY SERVICE FEE", 20, 20, "bank_fees"),
            opex(("POS PURCHASE STAPLES #{n}", "USPS POSTAGE {n}"), 15, 140, rate=0.25,
                 channel="in store"),
            sweep(2),
        ),
        traps=(
            trap("NORTHSTAR FUNDING DISB", 40000, 40000, "funder_disbursement",
                 "active_advance", "Merchant cash advance disbursement; loan proceeds, not revenue.",
                 credit=True, days=(20,), channel="online", pfc="transfer_in"),
            trap("NORTHSTAR MCA-PMT", 310, 310, "mca_daily_payment", "active_advance",
                 "Daily merchant cash advance repayment; funder debit.",
                 from_day=21, rate=1.0, weekdays=True, channel="online", pfc="loan"),
        ),
    ),
    Archetype(
        "biz_05", "Keystone Contracting", "contractor", 90, True,
        routine=(
            sales(("ACH CREDIT HOMEOWNER PROGRESS PMT {n}", "MOBILE CHECK DEPOSIT {n}"),
                  1500, 6000, rate=0.45, channel="online"),
            opex(("HOME DEPOT #{n}", "LOWES #{n}", "FERGUSON SUPPLY {n}"), 150, 2200,
                 rate=0.8, channel="in store"),
            payroll("ADP PAYROLL CREW {n}", 3800, 5200, every=7),
            monthly("STORAGE YARD RENT", 900, 900, "rent"),
            monthly("FORD CREDIT ACH", 1150, 1150, "loan"),
            monthly("NEXT INSURANCE PREMIUM", 420, 420, "general"),
            opex(("SHELL OIL {n}", "CHEVRON {n}"), 60, 140, pfc="transport", rate=0.3,
                 channel="in store"),
            sweep(2),
        ),
        traps=(
            L("ZELLE FROM M LOPEZ PERSONAL", 800, 3000, credit=True, count=8,
              channel="online", business=False, trap="owner_personal_credit",
              notes="Owner's personal funds deposited to the business account; not business revenue.",
              pfc="transfer_in"),
        ),
    ),
    Archetype(
        "biz_06", "The Rail Sports Bar", "sports bar", 90, True,
        routine=(
            sales("TOAST INC {n} DEPOSIT", 1100, 3200, rate=1.0, merchant="Toast"),
            sales("ZELLE EVENT BOOKING DEPOSIT {n}", 200, 900, rate=0.12, channel="online"),
            opex(("SOUTHERN GLAZERS BEVERAGE {n}", "BREAKTHRU BEVERAGE {n}",
                  "SYSCO FOODSERVICE {n}"), 400, 2600, pfc="food", rate=0.45),
            payroll("GUSTO PAYROLL {n}", 4200, 5600),
            monthly("ACH SPORTS PLAZA LEASE", 5200, 5200, "rent"),
            monthly("DIRECTV FOR BUSINESS", 1200, 1200),
            monthly(("XCEL ENERGY {n}", "COMCAST BUSINESS {n}"), 480, 760),
            monthly("STATE LIQUOR LICENSE FEE", 150, 150, "general"),
            opex(("POS PURCHASE COSTCO WHSE #{n}", "POS PURCHASE HOME DEPOT #{n}"), 40, 400,
                 rate=0.15, channel="in store"),
            sweep(3),
        ),
        traps=(
            trap(("HARRAHS CASINO #{n}", "POKER STARS ONLINE {n}"), 300, 1500,
                 "casino_debit", "high_risk_gambling", "Casino or poker debit; gambling risk signal.",
                 count=4, pfc="gambling"),
            trap("LUCKY DRAGON CHINESE BUFFET", 40, 160, "lucky_dragon_hard_negative", "none",
                 "Restaurant meal for staff; the name only resembles gambling.",
                 count=6, channel="in store", pfc="food"),
        ),
    ),
    Archetype(
        "biz_07", "Precision Auto Care", "auto repair shop", 90, True,
        routine=(
            sales("SQUARE INC {n} DEPOSIT", 400, 1600, rate=1.0, weekdays=True,
                  merchant="Square"),
            sales("ACH CREDIT FLEET ACCOUNT {n}", 800, 3000, rate=0.35, channel="online"),
            opex(("NAPA AUTO PARTS #{n}", "ADVANCE AUTO PARTS B2B {n}",
                  "OREILLY AUTO PARTS #{n}"), 120, 1400, rate=0.8, channel="online"),
            payroll("PAYCHEX PAYROLL {n}", 3800, 4800),
            monthly("ACH SHOP BAY LEASE", 3400, 3400, "rent"),
            monthly(("WASTE MANAGEMENT {n}", "DTE ENERGY {n}"), 190, 520),
            monthly("EMPLOYERS MUTUAL INSURANCE", 640, 640, "general"),
            opex(("SNAP-ON TOOLS {n}", "POS PURCHASE HARBOR FREIGHT #{n}"), 60, 600,
                 rate=0.1, channel="in store"),
            sweep(2),
        ),
        traps=(
            trap("NATIONAL DEBT-SETTLEMENT SVCS", 300, 900, "debt_settlement_punctuated",
                 "high_risk_debt_settlement", "Debt settlement program payment; high-risk signal.",
                 count=3, channel="online"),
            trap("WAGE GARNISH.ORDER", 250, 700, "garnishment_punctuated",
                 "high_risk_garnishment", "Court-ordered wage garnishment payment; high-risk signal.",
                 count=3, channel="online"),
            trap("ACCREDITED DEBT SETTLEMENT PMT", 300, 900, "debt_settlement_plain",
                 "high_risk_debt_settlement", "Debt settlement program payment; high-risk signal.",
                 count=2, channel="online"),
            trap("STATE WAGE GARNISHMENT", 250, 700, "garnishment_plain",
                 "high_risk_garnishment", "Court-ordered wage garnishment payment; high-risk signal.",
                 count=2, channel="online"),
        ),
    ),
    Archetype(
        "biz_08", "Brightcart Online", "ecommerce", 90, True,
        routine=(
            sales("PAYPAL INST XFER {n}", 100, 500, rate=0.4, channel="online"),
            opex(("FACEBK ADS {n}", "GOOGLE ADS {n}"), 100, 400, rate=0.7, channel="online"),
            opex(("UPS SHIPPING {n}", "USPS POSTAGE {n}"), 80, 450, rate=0.6),
            opex(("ALIBABA.COM SUPPLIER {n}", "GLOBAL SOURCES ORDER {n}"), 1000, 4000,
                 rate=0.1, channel="online"),
            payroll("GUSTO PAYROLL {n}", 2800, 3600),
            monthly("ACH WAREHOUSE RENT", 2400, 2400, "rent"),
            monthly("SHOPIFY* SUBSCRIPTION", 299, 299, "general"),
            monthly("AMAZON WEB SERVICES", 140, 260, "general"),
            sweep(2),
        ),
        traps=(
            trap("STRIPE TRANSFER ST-{n}", 400, 1800, "stripe_transfer_payout", "none",
                 "Stripe payout of online sales; operating revenue.", credit=True,
                 rate=1.0, channel="online", merchant="Stripe", pfc="income"),
        ),
    ),
    Archetype(
        "biz_09", "Lakeside Family Clinic", "medical clinic", 90, True,
        routine=(
            sales(("BLUE CROSS BLUE SHIELD EFT {n}", "AETNA HEALTH EFT {n}",
                   "UNITEDHEALTHCARE CLAIM PMT {n}", "CIGNA CLAIM PAYMENT {n}"),
                  800, 4500, rate=0.9, weekdays=True, channel="online"),
            sales("SQUARE INC PATIENT PAYMENT {n}", 40, 300, rate=1.0, weekdays=True,
                  merchant="Square"),
            opex(("HENRY SCHEIN MEDICAL #{n}", "MCKESSON MEDICAL {n}"), 200, 1800,
                 pfc="medical", rate=0.2, channel="online"),
            payroll("ADP PAYROLL {n}", 9000, 12000),
            monthly("ACH MEDICAL PLAZA LEASE", 5600, 5600, "rent"),
            monthly("MEDPRO INSURANCE", 880, 880, "general"),
            monthly("ATHENAHEALTH SERVICES", 740, 740, "general"),
            monthly(("DUKE ENERGY {n}", "AT&T BUSINESS {n}"), 260, 540),
            sweep(2),
        ),
        traps=(
            trap("NSF RETURN ITEM FEE", 35, 35, "nsf_fee_plain", "nsf",
                 "Bank fee for a returned item; NSF event.", count=5, pfc="bank_fees"),
            trap("N.S.F. RETURN ITEM FEE", 35, 35, "nsf_fee_punctuated", "nsf",
                 "Bank fee for a returned item written with punctuation; NSF event.",
                 count=1, pfc="bank_fees"),
        ),
    ),
    Archetype(
        "biz_10", "Northwind Consulting", "consulting", 90, True,
        routine=(
            sales(("ACH CREDIT ACME CORP INV {n}", "ACH CREDIT BRIDGEPOINT LLC INV {n}",
                   "QUICKBOOKS PAYMENTS DEPOSIT {n}"), 4000, 12000, rate=0.1,
                  channel="online"),
            opex(("ADOBE SYSTEMS {n}", "ZOOM.US {n}", "LINKEDIN PREMIUM {n}"), 20, 160,
                 rate=0.25, channel="online"),
            monthly("ACH COWORKING MEMBERSHIP", 650, 650, "rent"),
            opex(("UBER *TRIP {n}", "DELTA AIR LINES {n}", "MARRIOTT HOTEL {n}"), 30, 700,
                 pfc="travel", rate=0.35, channel="in store"),
            opex(("POS PURCHASE STARBUCKS #{n}", "POS PURCHASE STAPLES #{n}"), 8, 90,
                 rate=0.95, channel="in store"),
            opex("AMERICAN EXPRESS ACH PAYMENT", 1500, 3200, pfc="general", every=30,
                 channel="online"),
            monthly("IRS USATAXES EST TAX", 5500, 5500, "general"),
            monthly("MONTHLY SERVICE FEE", 15, 15, "bank_fees"),
            sweep(2),
        ),
    ),
)


def _eligible(spec, history_days, start):
    return [
        d for d in range(spec.from_day, history_days)
        if not spec.weekdays or (start + timedelta(days=d)).weekday() < 5
    ]


def _days_for(spec, history_days, start, rng):
    if spec.days is not None:
        return list(spec.days)
    eligible = _eligible(spec, history_days, start)
    if spec.count is not None:
        return sorted(rng.sample(eligible, spec.count))
    if spec.every is not None:
        phase = rng.randrange(spec.every)
        return [d for d in eligible if (d - phase) % spec.every == 0]
    return [d for d in eligible if rng.random() < spec.rate]


def _pfc(rng, key):
    pair = PFC[key]
    if rng.random() < NOISE_RATE:
        pair = rng.choice(NOISE_PFC)
    return {"primary": pair[0], "detailed": pair[1]}


def _row(rng, arch, day, desc, cents, channel, merchant, pfc_key, group, business, notes, trap):
    return {
        "business_id": arch.business_id,
        "account_id": f"acct_{arch.business_id}",
        "date": day,
        "description": desc,
        "amount": round(cents / 100, 2),
        "iso_currency_code": "USD",
        "payment_channel": channel,
        "merchant_name": merchant,
        "pending": day == END_DATE.isoformat() and rng.random() < 0.5,
        "transaction_type": "credit" if cents > 0 else "debit",
        "personal_finance_category": _pfc(rng, pfc_key),
        "_group": group,
        "_business": business,
        "_notes": notes,
        "_trap": trap,
    }


def _rows_for(arch, rng):
    start = END_DATE - timedelta(days=arch.history_days - 1)
    rows = []
    for ln in arch.fixed:
        rows.append(_row(rng, arch, ln.date, ln.description, ln.cents, ln.channel,
                         ln.merchant, ln.pfc, ln.group, ln.business, ln.notes, ln.trap))
    for spec in arch.routine + arch.traps:
        for d in _days_for(spec, arch.history_days, start, rng):
            desc = rng.choice(spec.descriptions).replace("{n}", str(rng.randint(1000, 9999)))
            cents = rng.randint(round(spec.lo * 100), round(spec.hi * 100))
            rows.append(_row(
                rng, arch, (start + timedelta(days=d)).isoformat(), desc,
                cents if spec.credit else -cents, spec.channel, spec.merchant,
                spec.pfc, spec.group, spec.business, spec.notes, spec.trap,
            ))
    return rows


def build(seed=42):
    rng = random.Random(seed)
    rows = []
    for arch in ARCHETYPES:
        rows.extend(_rows_for(arch, rng))
    rows.sort(key=lambda r: (r["business_id"], r["date"], r["description"], r["amount"]))
    counters = {}
    txns, truth, traps = [], {}, {}
    for r in rows:
        n = counters[r["business_id"]] = counters.get(r["business_id"], 0) + 1
        tid = f"txn_{r['business_id']}_{n:04d}"
        group, business = r.pop("_group"), r.pop("_business")
        notes, trap = r.pop("_notes"), r.pop("_trap")
        txn = {"transaction_id": tid, **r}
        validate_transaction(txn)
        txns.append(txn)
        truth[tid] = {
            "group": group,
            "business": business,
            "revenue": is_revenue(txn, group, business),
            "risk_signal": risk_signal_for(group),
            "notes": notes,
        }
        if trap:
            traps[tid] = trap
    businesses = [
        {
            "business_id": a.business_id,
            "name": a.name,
            "type": a.type,
            "account_id": f"acct_{a.business_id}",
            "history_days": a.history_days,
            "bank_charges_nsf_fee": a.bank_charges_nsf_fee,
        }
        for a in ARCHETYPES
    ]
    for b in businesses:
        validate_business(b)
    validate_truth_covers(txns, truth)
    return businesses, txns, truth, traps


def _dump(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, indent=2) + "\n")


def generate(seed=42, out_dir="data"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    businesses, txns, truth, traps = build(seed)
    _dump(out / "businesses.json", businesses)
    _dump(out / "transactions.json", txns)
    _dump(out / "ground_truth.json", truth)
    _dump(out / "traps.json", traps)
