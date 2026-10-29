"""Unit tests for app.analysis.ai_advisor."""
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from app.analysis.ai_advisor import (
    build_advisor_prompt,
    generate_ai_advice,
    stream_ai_advice,
)
from app.analysis.assembler import (
    ChipsSummary,
    FundamentalSummary,
    StrategyAnalysisResult,
    TodayAnalysis,
)
from app.data.exceptions import AiAdvisorError, GeminiApiKeyMissingError


@pytest.fixture
def sample_analysis():
    return TodayAnalysis(
        stock_id="2330",
        evaluation_date="2026-03-30",
        disclaimer="免責聲明",
        fundamental=FundamentalSummary(
            passed=True,
            revenue_yoy=25.4,
            eps_4q_sum=38.5,
            debt_ratio=32.1,
            reason="基本面三項指標均符合標準",
        ),
        chips=ChipsSummary(
            passed=True,
            foreign_trust_net_buy_10d=15420.0,
            margin_increase_rate_10d=-4.2,
            reason="法人連續加碼且融資無過熱",
        ),
        strategies=[
            StrategyAnalysisResult(
                strategy_name="均線糾結突破",
                status="進場",
                action="BUY",
                technical_signal=True,
                entry_price=980.0,
                stop_loss=940.0,
                take_profit=1060.0,
                max_holding_days=15,
                trigger_condition="收盤站上 MA20 且帶量突破糾結區",
            )
        ],
        factor_score=85.2,
        factor_decile=1,
        historical_hit_rate=78.5,
        historical_lift=1.65,
        triggered_factors=["營收創歷史高", "外資投信同步買超"],
    )


@pytest.fixture
def sample_indicators():
    return pd.DataFrame([
        {
            "date": "2026-03-30",
            "close": 980.0,
            "ma5": 970.0,
            "ma20": 960.0,
            "ma60": 940.0,
            "atr14": 18.5,
            "volume": 25000,
        }
    ])


def test_build_advisor_prompt(sample_analysis, sample_indicators):
    prompt = build_advisor_prompt("2330", "台積電", sample_analysis, sample_indicators)
    # Check basic identifiers
    assert "2330 台積電" in prompt
    assert "2026-03-30" in prompt

    # Check 4 core sections
    assert "### 1. 【進場適宜度判定】" in prompt
    assert "### 2. 【關鍵進出場價位規劃】" in prompt
    assert "### 3. 【隔日進場觸發訊號】" in prompt
    assert "### 4. 【防守撤退與失效訊號】" in prompt

    # Check technicals
    assert "980.00" in prompt
    assert "ATR14" in prompt

    # Check fundamentals & chips
    assert "25.4%" in prompt
    assert "15,420" in prompt

    # Check factor score
    assert "85.2" in prompt
    assert "營收創歷史高" in prompt

    # Check strategy levels
    assert "均線糾結突破" in prompt
    assert "980.00 元" in prompt
    assert "940.00 元" in prompt
    assert "1060.00 元" in prompt


def test_stream_ai_advice_missing_api_key(sample_analysis):
    with patch("app.analysis.ai_advisor.get_gemini_api_key", return_value=""):
        with pytest.raises(GeminiApiKeyMissingError):
            list(stream_ai_advice("2330", "台積電", sample_analysis, client=None, api_key=""))


def test_stream_ai_advice_success(sample_analysis, sample_indicators):
    mock_client = MagicMock()
    chunk1 = MagicMock(text="### 1. 【進場適宜度判定】\n目前具備進場條件。")
    chunk2 = MagicMock(text="\n### 2. 【關鍵進出場價位規劃】\n建議停損940元。")
    mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]

    tokens = list(stream_ai_advice(
        "2330",
        "台積電",
        sample_analysis,
        sample_indicators,
        client=mock_client,
    ))

    assert len(tokens) == 2
    assert tokens[0] == "### 1. 【進場適宜度判定】\n目前具備進場條件。"
    assert tokens[1] == "\n### 2. 【關鍵進出場價位規劃】\n建議停損940元。"


def test_stream_ai_advice_api_error(sample_analysis):
    mock_client = MagicMock()
    mock_client.models.generate_content_stream.side_effect = RuntimeError("Quota exceeded")

    with pytest.raises(AiAdvisorError) as exc_info:
        list(stream_ai_advice("2330", "台積電", sample_analysis, client=mock_client))
    assert "Quota exceeded" in str(exc_info.value)


def test_generate_ai_advice(sample_analysis):
    mock_client = MagicMock()
    chunk1 = MagicMock(text="戰略分析：")
    chunk2 = MagicMock(text="突破買進。")
    mock_client.models.generate_content_stream.return_value = [chunk1, chunk2]

    result = generate_ai_advice("2330", "台積電", sample_analysis, client=mock_client)
    assert result == "戰略分析：突破買進。"
