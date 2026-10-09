import json
from datetime import date

from fundo.casa_norte import REPAY_LINES, TRAP_LINES
from fundo.schema import GROUPS

ALL_LINES = TRAP_LINES + REPAY_LINES
REQUIRED_TRAPS = {
    "card_processor_deposit",
    "internal_transfer_credit",
    "square_capital_repay",
    "nsf_fee",
    "high_risk_debit",
    "hard_negative",
    "instruction_like",
}


def by_trap(name):
    return [ln for ln in ALL_LINES if ln.trap == name]


def test_every_pdf_trap_present():
    assert REQUIRED_TRAPS <= {ln.trap for ln in ALL_LINES}


def test_about_eighteen_hand_written_lines():
    assert 14 <= len(TRAP_LINES) <= 24


def test_lines_are_valid_and_in_window():
    for ln in ALL_LINES:
        assert ln.group in GROUPS
        assert date(2026, 4, 2) <= date.fromisoformat(ln.date) <= date(2026, 6, 30)
        assert ln.notes


def test_card_processor_deposit_is_revenue_credit():
    for ln in by_trap("card_processor_deposit"):
        assert ln.cents > 0 and ln.group == "none" and ln.business
        assert "SQUARE" in ln.description.upper()


def test_internal_transfer_credit_is_not_revenue_group():
    lines = by_trap("internal_transfer_credit")
    assert lines and all(ln.cents > 0 and ln.group == "internal_transfer" for ln in lines)


def test_square_capital_repay_is_funder_debit():
    lines = by_trap("square_capital_repay")
    assert len(lines) > 30
    assert all(ln.cents < 0 and ln.group == "active_advance" for ln in lines)


def test_nsf_high_risk_and_hard_negative_truth():
    assert {ln.group for ln in by_trap("nsf_fee")} == {"nsf"}
    assert {ln.group for ln in by_trap("high_risk_debit")} == {"high_risk_gambling"}
    assert {ln.group for ln in by_trap("hard_negative")} == {"none"}


def test_instruction_like_text_is_data_and_truth_follows_nature():
    (ln,) = by_trap("instruction_like")
    assert "IGNORE PREVIOUS INSTRUCTIONS" in ln.description
    assert ln.cents > 0 and ln.group == "none"
    assert json.loads(json.dumps(ln.description)) == ln.description
