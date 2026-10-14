import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import Quote, find_surebet
from executor import Executor
from providers import SimulatedProvider, BettingProvider


def qs(a, b): return [Quote("p", "e", "A", a), Quote("p", "e", "B", b)]


def test_detects_and_none():
    assert find_surebet(qs(2.1, 2.1), 100).margin > 0
    assert find_surebet(qs(1.9, 1.9), 100) is None


def test_commission_kills_thin_margin():
    assert find_surebet(qs(2.04, 2.04), 100, commission=0.05) is None


def test_dry_run_sends_nothing(tmp_path):
    p = SimulatedProvider("p", qs(2.1, 2.1))
    r = Executor([p], ledger=tmp_path / "l").execute(find_surebet(qs(2.1, 2.1), 40))
    assert not r["ok"] and p.orders == []


def test_live_needs_env(tmp_path, monkeypatch):
    monkeypatch.delenv("SUREBET_LIVE", raising=False)
    p = SimulatedProvider("p", qs(2.1, 2.1))
    ex = Executor([p], live=True, confirm=lambda _: "SI", ledger=tmp_path / "l")
    assert not ex.execute(find_surebet(qs(2.1, 2.1), 40))["ok"] and p.orders == []


def test_second_leg_failure_reports_exposure(tmp_path, monkeypatch):
    monkeypatch.setenv("SUREBET_LIVE", "1")
    ok = SimulatedProvider("p", [], balance=1000)
    poor = SimulatedProvider("q", [], balance=0)
    legs = [Quote("p", "e", "A", 2.0), Quote("q", "e", "B", 2.4)]
    ex = Executor([ok, poor], live=True, confirm=lambda _: "SI", ledger=tmp_path / "l")
    r = ex.execute(find_surebet(legs, 40))
    assert not r["ok"] and r["exposed"] is True
