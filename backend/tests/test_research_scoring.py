"""Unit tests for scoring, weights, normalization, and validation."""

import numpy as np
import pandas as pd
import pytest

from app.research.config import StudyConfig
from app.research.event_study import FactorStat
from app.research.scoring import (
    evaluate_scoring_system,
    fit_weights,
    normalize_scores,
)


def _make_dummy_stat(name: str, lift: float, sample_count: int = 500, insufficient: bool = False) -> FactorStat:
    base = 0.10
    hits = int(sample_count * base * lift)
    return FactorStat(
        factor_name=name,
        sample_count=sample_count,
        hit_count=hits,
        hit_rate=hits / sample_count if sample_count > 0 else 0.0,
        base_hit_rate=base,
        lift=lift,
        ci_lower=0.08,
        ci_upper=0.12,
        lift_lower=0.8,
        lift_upper=1.2,
        sample_insufficient=insufficient,
    )


def test_fit_weights_rules():
    """Scenario: lift > 1 權重為 log(lift)，lift <= 1 或樣本不足則權重為 0."""
    stats = {
        "f_good": _make_dummy_stat("f_good", lift=2.5, sample_count=200, insufficient=False),
        "f_neutral": _make_dummy_stat("f_neutral", lift=1.0, sample_count=200, insufficient=False),
        "f_bad": _make_dummy_stat("f_bad", lift=0.8, sample_count=200, insufficient=False),
        "f_small": _make_dummy_stat("f_small", lift=3.0, sample_count=50, insufficient=True),
    }

    w = fit_weights(stats)
    assert w["f_good"] == pytest.approx(np.log(2.5), rel=1e-3)
    assert w["f_neutral"] == 0.0
    assert w["f_bad"] == 0.0
    assert w["f_small"] == 0.0


def test_weights_frozen_and_validation_verdict():
    """Scenario: 權重與正規化只由訓練期決定，測試期達成 lift >= 2 判定為 passed."""
    # 1. Create train dataset where f_good has high hit rate
    n_train = 1000
    train_df = pd.DataFrame({
        "f_good": [True if i % 2 == 0 else False for i in range(n_train)],
        "forward_hit": [True if i % 2 == 0 and i % 4 == 0 else False for i in range(n_train)],
    })
    # Base hit rate is 250 / 1000 = 0.25
    # Trigger hit rate is 250 / 500 = 0.50 -> lift = 2.0
    train_stats = {
        "f_good": _make_dummy_stat("f_good", lift=2.0, sample_count=500, insufficient=False),
    }

    # 2. Test dataset where top scored also gets lift >= 2.0
    n_test = 500
    test_df = pd.DataFrame({
        "f_good": [True if i < 50 else False for i in range(n_test)],  # Exactly top 10% (50 / 500)
        # Top 10% all hit (50 hits), others 0 hits
        "forward_hit": [True if i < 50 else False for i in range(n_test)],
    })
    # Base rate = 50 / 500 = 0.10. Top 10% hit rate = 1.0 (lift = 10.0 >= 2.0)

    cfg = StudyConfig(target_lift=2.0)
    res = evaluate_scoring_system(train_df, test_df, train_stats, config=cfg)

    assert res.passed is True
    assert res.top10_lift >= 2.0
    assert res.weights["f_good"] == pytest.approx(np.log(2.0), rel=1e-3)


def test_validation_not_passed():
    """Scenario: 測試期前 10% lift < 2.0 -> passed=False."""
    n = 500
    train_df = pd.DataFrame({
        "f_good": [True] * n,
        "forward_hit": [False] * n,
    })
    train_stats = {
        "f_good": _make_dummy_stat("f_good", lift=1.5, sample_count=500, insufficient=False),
    }

    # In test set, hit rate of top 10% is same as base (lift = 1.0 < 2.0)
    test_df = pd.DataFrame({
        "f_good": [True if i < 50 else False for i in range(n)],
        "forward_hit": [True if i % 10 == 0 else False for i in range(n)],
    })

    cfg = StudyConfig(target_lift=2.0)
    res = evaluate_scoring_system(train_df, test_df, train_stats, config=cfg)

    assert res.passed is False
    assert res.top10_lift < 2.0
