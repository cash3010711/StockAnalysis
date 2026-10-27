import pytest
from app.data.twse_client import TWSEClient, DailyQuote, _clean_number


def test_clean_number():
    assert _clean_number("1,234.56") == 1234.56
    assert _clean_number("+5.20") == 5.2
    assert _clean_number("-3.14") == -3.14
    assert _clean_number("--") is None
    assert _clean_number("") is None
    assert _clean_number(None) is None
    assert _clean_number("<span>+1.5</span>") == 1.5


def test_parse_twse_response():
    mock_twse_json = {
        "stat": "OK",
        "date": "20261026",
        "tables": [
            {
                "title": "每日收盤行情",
                "fields": [
                    "證券代號", "證券名稱", "成交股數", "成交筆數", "成交金額",
                    "開盤價", "最高價", "最低價", "收盤價", "漲跌(+/-)", "漲跌價差",
                    "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量", "本益比"
                ],
                "data": [
                    # 2330: Valid common stock
                    ["2330", "台積電", "25,000,000", "15,000", "25,000,000,000", "1,000.00", "1,020.00", "995.00", "1,015.00", "+", "15.00", "1010", "10", "1015", "5", "25.0"],
                    # 0050: ETF - should be filtered out
                    ["0050", "元大台灣50", "10,000,000", "5,000", "1,500,000,000", "150.00", "152.00", "149.00", "151.00", "+", "1.00", "150.5", "10", "151", "5", "0.0"],
                    # 2881A: Preferred stock - should be filtered out
                    ["2881A", "富邦特", "500,000", "200", "30,000,000", "60.00", "60.50", "59.80", "60.00", " ", "0.00", "60", "1", "60.1", "1", "15.0"],
                    # 2317: Valid common stock with negative change
                    ["2317", "鴻海", "30,000,000", "18,000", "4,500,000,000", "155.00", "156.00", "152.00", "153.00", "-", "2.00", "152.5", "50", "153", "20", "12.0"]
                ]
            }
        ]
    }

    quotes = TWSEClient.parse_twse_response(mock_twse_json, "2026-10-26")
    assert len(quotes) == 2
    
    q_2330 = next(q for q in quotes if q.stock_id == "2330")
    assert q_2330.stock_name == "台積電"
    assert q_2330.date == "2026-10-26"
    assert q_2330.open == 1000.0
    assert q_2330.high == 1020.0
    assert q_2330.low == 995.0
    assert q_2330.close == 1015.0
    assert q_2330.change == 15.0
    assert q_2330.volume == 25_000_000
    assert q_2330.volume_lots == 25000.0
    assert q_2330.market == "TWSE"
    assert q_2330.change_pct == 1.5

    q_2317 = next(q for q in quotes if q.stock_id == "2317")
    assert q_2317.change == -2.0
    assert q_2317.volume_lots == 30000.0


def test_parse_tpex_response():
    mock_tpex_data = {
        "aaData": [
            # 6488: Valid TPEx common stock
            ["6488", "環球晶", "520.00", "+10.00", "515.00", "525.00", "510.00", "3,500,000", "1,820,000,000", "2,100"],
            # 00679B: ETF - should be excluded
            ["00679B", "元大美債20年", "30.50", "-0.10", "30.60", "30.65", "30.45", "15,000,000", "450,000,000", "4,000"],
        ]
    }

    quotes = TWSEClient.parse_tpex_response(mock_tpex_data, "2026-10-26")
    assert len(quotes) == 1
    q = quotes[0]
    assert q.stock_id == "6488"
    assert q.stock_name == "環球晶"
    assert q.close == 520.0
    assert q.open == 515.0
    assert q.high == 525.0
    assert q.low == 510.0
    assert q.change == 10.0
    assert q.volume == 3_500_000
    assert q.volume_lots == 3500.0
    assert q.market == "TPEx"


def test_filter_candidates():
    quotes = [
        # Candidate 1: High volume, strong rise -> Should pass
        DailyQuote("2330", "台積電", "2026-10-26", 1000.0, 1050.0, 1000.0, 1050.0, 50.0, 5.0, 50_000_000, 50_000.0, "TWSE"),
        # Candidate 2: Low volume (< 1000 lots) -> Should fail
        DailyQuote("1234", "低量股", "2026-10-26", 20.0, 22.0, 20.0, 22.0, 2.0, 10.0, 500_000, 500.0, "TWSE"),
        # Candidate 3: Penny stock (< 10 TWD) -> Should fail
        DailyQuote("5678", "水餃股", "2026-10-26", 5.0, 5.5, 4.9, 5.5, 0.5, 10.0, 5_000_000, 5_000.0, "TWSE"),
        # Candidate 4: Moderate volume, great percentage gain -> Should pass & rank top
        DailyQuote("3008", "大立光", "2026-10-26", 2500.0, 2750.0, 2500.0, 2750.0, 250.0, 10.0, 2_000_000, 2_000.0, "TWSE"),
        # Candidate 5: High volume, but bearish (open 100, close 95, change -5) -> Should fail
        DailyQuote("9999", "弱勢股", "2026-10-26", 100.0, 100.0, 95.0, 95.0, -5.0, -5.0, 10_000_000, 10_000.0, "TWSE"),
    ]

    # Default: volume descending, allows consolidation stocks through
    candidates = TWSEClient.filter_candidates(quotes, min_volume_lots=1000.0, min_price=10.0, top_n=2)
    assert len(candidates) == 2
    assert candidates[0].stock_id == "2330"  # 50,000 lots
    assert candidates[1].stock_id == "9999"  # 10,000 lots

    # Legacy mode: change_pct descending + require_bullish
    legacy = TWSEClient.filter_candidates(
        quotes, min_volume_lots=1000.0, min_price=10.0, top_n=2,
        sort_by="change_pct", require_bullish=True,
    )
    assert len(legacy) == 2
    assert legacy[0].stock_id == "3008"  # +10%
    assert legacy[1].stock_id == "2330"  # +5%
