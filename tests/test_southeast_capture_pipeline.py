"""Unit tests for the 15-Agency Southeastern/Texas DOT Registry, CIP Forecaster, and Capture Engine."""

import datetime
from scrapers.southeast_dots import (
    CIPForecastItem,
    CIPForecaster,
    CaptureWorkflowEngine,
    SOUTHEAST_AND_TEXAS_DOT_REGISTRY,
)


def test_southeast_and_texas_dot_registry_coverage():
    expected = {
        "FDOT", "GDOT", "NCDOT", "SCDOT", "VDOT", "TDOT",
        "ALDOT", "MDOT", "LADOTD", "KYTC", "WVDOT", "ARDOT",
        "TXDOT", "HGAC", "HOU",
    }
    assert expected.issubset(set(SOUTHEAST_AND_TEXAS_DOT_REGISTRY.keys()))
    assert SOUTHEAST_AND_TEXAS_DOT_REGISTRY["FDOT"].state == "FL"
    assert SOUTHEAST_AND_TEXAS_DOT_REGISTRY["NCDOT"].state == "NC"
    assert len(SOUTHEAST_AND_TEXAS_DOT_REGISTRY["TXDOT"].prequalification_categories) >= 3


def test_cip_forecaster_lookahead_window():
    ref = datetime.date(2026, 10, 17)
    items = [
        CIPForecastItem("FDOT", "FM-44123", "I-4 Connected Corridor TSMO", 4500000.0, datetime.date(2027, 6, 1), ["TSMO", "ITS"]),
        CIPForecastItem("GDOT", "PI-00192", "Metro Atlanta Adaptive Signals", 3200000.0, datetime.date(2027, 11, 15), ["Signals"]),
        CIPForecastItem("SCDOT", "SC-99", "Past Due Project", 1000000.0, datetime.date(2026, 9, 1), ["ITS"]),
    ]
    forecaster = CIPForecaster()
    window = forecaster.filter_lookahead_window(items, reference_date=ref, min_months=3, max_months=24)
    assert len(window) == 2
    assert window[0].agency_code == "FDOT"
    assert window[1].agency_code == "GDOT"
    assert len(window[0].fingerprint) == 24


def test_capture_workflow_pink_red_gold_gates():
    engine = CaptureWorkflowEngine()
    schedule = engine.evaluate_and_schedule(
        solicitation_id="FDOT-RFP-2026-09",
        rfp_release_date=datetime.date(2026, 11, 1),
        submission_due_date=datetime.date(2026, 12, 11),
        criteria_scores={
            "technical_alignment": 90,
            "client_relationship": 80,
            "teaming_strength": 85,
            "incumbent_advantage": 60,
            "fee_profitability": 75,
        },
    )
    assert schedule.pink_team_date < schedule.red_team_date < schedule.gold_team_date < schedule.submission_due_date
    assert schedule.go_no_go_score == 80.5
    assert schedule.recommendation.startswith("GO")
