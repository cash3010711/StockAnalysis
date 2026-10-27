import pytest
from unittest.mock import MagicMock
from app.analysis import params
from app.analysis.scanner import (
    ScanFilterConfig,
    matches_industry_filter,
    resolve_scan_pool,
)
from app.data.twse_client import DailyQuote


def test_tech_industries_definition():
    expected = {
        "半導體業",
        "電腦及周邊設備業",
        "光電業",
        "通信網路業",
        "電子零組件業",
        "電子通路業",
        "資訊服務業",
        "其他電子業",
    }
    assert params.TECH_INDUSTRIES == expected


def test_matches_industry_filter():
    # None or empty filter matches everything
    assert matches_industry_filter("半導體業", None) is True
    assert matches_industry_filter("半導體業", "") is True
    assert matches_industry_filter("水泥工業", "  ") is True

    # Tech filters
    for tf in ["tech", "科技股", "科技股（電子八大類）"]:
        assert matches_industry_filter("半導體業", tf) is True
        assert matches_industry_filter("電腦及周邊設備業", tf) is True
        assert matches_industry_filter("水泥工業", tf) is False
        assert matches_industry_filter("金融保險業", tf) is False
        assert matches_industry_filter("", tf) is False
        assert matches_industry_filter(None, tf) is False

    # Non-tech filters
    for ntf in ["non_tech", "非科技股"]:
        assert matches_industry_filter("水泥工業", ntf) is True
        assert matches_industry_filter("金融保險業", ntf) is True
        assert matches_industry_filter("半導體業", ntf) is False
        assert matches_industry_filter("光電業", ntf) is False
        assert matches_industry_filter("ETF", ntf) is False
        assert matches_industry_filter("", ntf) is False
        assert matches_industry_filter(None, ntf) is False

    # Specific category filter
    assert matches_industry_filter("水泥工業", "水泥工業") is True
    assert matches_industry_filter("半導體業", "水泥工業") is False


def test_resolve_scan_pool_tw50_tech_and_non_tech():
    mock_service = MagicMock()
    mock_service.repo.get_stock_metadata.return_value = None

    # Tech filter on tw50
    cfg_tech = ScanFilterConfig(pool="tw50", industry_category="tech")
    tech_stocks = resolve_scan_pool(mock_service, cfg_tech)
    assert len(tech_stocks) > 0
    for s in tech_stocks:
        assert s["industry_category"] in params.TECH_INDUSTRIES

    # Non-tech filter on tw50
    cfg_non_tech = ScanFilterConfig(pool="tw50", industry_category="non_tech")
    non_tech_stocks = resolve_scan_pool(mock_service, cfg_non_tech)
    assert len(non_tech_stocks) > 0
    for s in non_tech_stocks:
        assert s["industry_category"] not in params.TECH_INDUSTRIES
        assert s["industry_category"] != ""

    # Check known stocks
    tech_ids = {s["stock_id"] for s in tech_stocks}
    non_tech_ids = {s["stock_id"] for s in non_tech_stocks}
    assert "2330" in tech_ids  # 台積電 (半導體業)
    assert "2454" in tech_ids  # 聯發科 (半導體業)
    assert "1101" in non_tech_ids  # 台泥 (水泥工業)
    assert "2881" in non_tech_ids  # 富邦金 (金融保險業)


def test_two_stage_scan_industry_enrichment():
    mock_service = MagicMock()

    def get_meta(stock_id: str):
        if stock_id == "2330":
            return {
                "stock_id": "2330",
                "stock_name": "台積電",
                "type": "twse",
                "industry_category": "半導體業",
            }
        elif stock_id == "1101":
            return {
                "stock_id": "1101",
                "stock_name": "台泥",
                "type": "twse",
                "industry_category": "水泥工業",
            }
        return None

    mock_service.repo.get_stock_metadata.side_effect = get_meta

    mock_twse = MagicMock()
    mock_twse.fetch_all_quotes.return_value = []
    mock_twse.filter_candidates.return_value = [
        DailyQuote(
            stock_id="2330",
            stock_name="台積電",
            date="2026-10-21",
            open=890.0,
            high=905.0,
            low=888.0,
            close=900.0,
            change=10.0,
            change_pct=1.12,
            volume=10000000,
            volume_lots=10000.0,
            market="TWSE",
        ),
        DailyQuote(
            stock_id="1101",
            stock_name="台泥",
            date="2026-10-21",
            open=34.5,
            high=35.5,
            low=34.2,
            close=35.0,
            change=0.5,
            change_pct=1.45,
            volume=5000000,
            volume_lots=5000.0,
            market="TWSE",
        ),
    ]

    # Two stage with tech filter
    cfg_tech = ScanFilterConfig(two_stage=True, industry_category="tech")
    tech_stocks = resolve_scan_pool(mock_service, cfg_tech, twse_client=mock_twse)
    assert len(tech_stocks) == 1
    assert tech_stocks[0]["stock_id"] == "2330"
    assert tech_stocks[0]["industry_category"] == "半導體業"

    # Two stage with non-tech filter
    cfg_non_tech = ScanFilterConfig(two_stage=True, industry_category="non_tech")
    non_tech_stocks = resolve_scan_pool(mock_service, cfg_non_tech, twse_client=mock_twse)
    assert len(non_tech_stocks) == 1
    assert non_tech_stocks[0]["stock_id"] == "1101"
    assert non_tech_stocks[0]["industry_category"] == "水泥工業"
