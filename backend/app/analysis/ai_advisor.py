"""AI Stock Swing Trading Advisor using Google Gemini API."""
import os
from typing import Any, Generator, List, Optional
import pandas as pd

from app.analysis.assembler import TodayAnalysis
from app.config import get_gemini_api_key, has_gemini_api_key
from app.data.exceptions import AiAdvisorError, GeminiApiKeyMissingError

DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")


def build_advisor_prompt(
    stock_id: str,
    stock_name: str,
    today_analysis: TodayAnalysis,
    df_indicators: Optional[pd.DataFrame] = None,
) -> str:
    """Build structured quantitative prompt for Google Gemini AI advisor."""
    eval_date = today_analysis.evaluation_date

    # Extract technical indicators from latest row if available
    tech_info: List[str] = []
    if df_indicators is not None and not df_indicators.empty:
        latest = df_indicators.iloc[-1]
        close = latest.get("close")
        ma5 = latest.get("ma5")
        ma20 = latest.get("ma20")
        ma60 = latest.get("ma60")
        atr14 = latest.get("atr14")
        volume = latest.get("volume")

        if pd.notna(close):
            tech_info.append(f"- 最新收盤價: {close:.2f} 元")
        if pd.notna(ma5):
            tech_info.append(f"- 5日均線 (MA5): {ma5:.2f} 元")
        if pd.notna(ma20):
            tech_info.append(f"- 20日均線 (MA20): {ma20:.2f} 元")
        if pd.notna(ma60):
            tech_info.append(f"- 60日均線 (MA60): {ma60:.2f} 元")
        if pd.notna(atr14):
            tech_info.append(f"- 14日真實波動區間 (ATR14): {atr14:.2f} 元")
        if pd.notna(volume):
            tech_info.append(f"- 當日成交量: {int(volume):,} 張/股")

    tech_section = "\n".join(tech_info) if tech_info else "- 暫無完整指標明細"

    # Fundamental layer
    fund = today_analysis.fundamental
    fund_yoy_str = f"{fund.revenue_yoy:.1f}%" if fund.revenue_yoy is not None else "無資料"
    fund_eps_str = f"{fund.eps_4q_sum:.2f} 元" if fund.eps_4q_sum is not None else "無資料"
    fund_debt_str = f"{fund.debt_ratio:.1f}%" if fund.debt_ratio is not None else "無資料"
    fund_passed_str = "通過" if fund.passed else "未通過"

    # Chips layer
    chips = today_analysis.chips
    chips_net_str = f"{chips.foreign_trust_net_buy_10d:,.0f} 張" if chips.foreign_trust_net_buy_10d is not None else "無資料"
    chips_margin_str = f"{chips.margin_increase_rate_10d:.1f}%" if chips.margin_increase_rate_10d is not None else "無資料"
    chips_passed_str = "通過" if chips.passed else "未通過"

    # Factor score
    score_str = f"{today_analysis.factor_score:.1f} 分" if today_analysis.factor_score is not None else "無"
    decile_str = f"第 {today_analysis.factor_decile} 分位群" if today_analysis.factor_decile is not None else "無"
    hit_rate_str = f"{today_analysis.historical_hit_rate:.1f}%" if today_analysis.historical_hit_rate is not None else "無"
    lift_str = f"{today_analysis.historical_lift:.2f}x" if today_analysis.historical_lift is not None else "無"
    factors_str = "、".join(today_analysis.triggered_factors) if today_analysis.triggered_factors else "無命中強因子"

    # Strategies
    strat_lines: List[str] = []
    for s in today_analysis.strategies:
        entry_str = f"{s.entry_price:.2f} 元" if s.entry_price is not None else "無"
        sl_str = f"{s.stop_loss:.2f} 元" if s.stop_loss is not None else "無"
        tp_str = f"{s.take_profit:.2f} 元" if s.take_profit is not None else "無"
        days_str = f"{s.max_holding_days} 日" if s.max_holding_days is not None else "無"
        strat_lines.append(
            f"  * 策略【{s.strategy_name}】：判定狀態={s.status}（動作={s.action}，技術訊號={s.technical_signal}）\n"
            f"    - 建議進場價: {entry_str}\n"
            f"    - 建議停損價: {sl_str}\n"
            f"    - 建議停利價: {tp_str}\n"
            f"    - 最大持有天數: {days_str}\n"
            f"    - 觸發條件: {s.trigger_condition or '無'}"
        )
    strats_section = "\n".join(strat_lines) if strat_lines else "  * 無可用策略資訊"

    prompt = f"""你是一名嚴謹、專業的台股波段策略分析師與量化操盤戰略顧問。
請根據下方系統所提供的標的最新量化數值、三層濾網檢驗結果與量化交易點位，為個人操盤人撰寫一份結構嚴謹、條理分明、具備可操作性的「AI 盤後戰略解讀」。

=== 【個股基本資料與評估基準】 ===
- 標的代號與名稱: {stock_id} {stock_name}
- 評估基準日: {eval_date}

=== 【技術面型態與量價指標】 ===
{tech_section}

=== 【基本面檢驗 (第 1 層濾網)】 ===
- 狀態: {fund_passed_str}
- 月營收年增率 (YoY): {fund_yoy_str}
- 近四季累積 EPS: {fund_eps_str}
- 負債比率: {fund_debt_str}
- 系統檢驗評語: {fund.reason}

=== 【籌碼面檢驗 (第 2 層濾網)】 ===
- 狀態: {chips_passed_str}
- 外資+投信近 10 日買賣超: {chips_net_str}
- 近 10 日融資增減比率: {chips_margin_str}
- 系統檢驗評語: {chips.reason}

=== 【多因子起漲評分與歷史回測表現】 ===
- 起漲評分: {score_str} ({decile_str})
- 歷史同分位群 20 日起漲勝率: {hit_rate_str} (表現提升倍數 Lift: {lift_str})
- 觸發之強因子標籤: {factors_str}

=== 【策略檢驗與量化點位規劃 (第 3 層技術策略)】 ===
{strats_section}

=== 【輸出要求與嚴格規範】 ===
1. 嚴格遵守量化為本：請完全基於上方客觀數值與策略規劃點位進行解讀。嚴禁自行杜撰未經回測的勝率、捏造或隨意變更建議的停損與停利價位。
2. 語言與語氣：全篇使用正體中文（繁體中文），語氣專業、理性客觀，切勿給予保證獲利或誇大之詞。
3. 必須完整包含以下 4 大核心 Markdown 板塊（請精確使用三級標題 `###`）：

### 1. 【進場適宜度判定】
綜合評估基本面營收、籌碼面法人動向、多因子評分與技術面均線型態，給出明確的定性結論（例如：「目前具備波段進場契機」、「宜等待量縮拉回關鍵支撐再行介入」或「均線未糾結/基本面未過，維持空手觀望」）。

### 2. 【關鍵進出場價位規劃】
依據系統規劃之進場點、停損點與目標停利點進行剖析，說明該點位設定之技術理由（如支撐跌破、ATR 波動度限制或均線防守）以及潛在風險報酬比 (Risk/Reward Ratio)。

### 3. 【隔日進場觸發訊號】
具體提示隔日開盤或盤中操作時應觀察的觸發訊號（例如：開盤是否站上關鍵價、預估量能是否放大、回測均線是否收下影線等盤中確認特徵）。

### 4. 【防守撤退與失效訊號】
明確指出波段操作必須立刻停損或離場的失效警訊（如帶量跌破停損價、法人連續大幅調節或收盤跌破關鍵支撐），強調紀律執行防守策略。
"""
    return prompt.strip()


def stream_ai_advice(
    stock_id: str,
    stock_name: str,
    today_analysis: TodayAnalysis,
    df_indicators: Optional[pd.DataFrame] = None,
    client: Optional[Any] = None,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
) -> Generator[str, None, None]:
    """Stream AI advice chunks from Google Gemini API.

    Yields:
        Individual string tokens as they arrive.

    Raises:
        GeminiApiKeyMissingError: If GEMINI_API_KEY is not set or empty.
        AiAdvisorError: If Gemini API call fails during generation.
    """
    key = api_key or get_gemini_api_key()

    if client is None:
        if not key:
            raise GeminiApiKeyMissingError()
        try:
            from google import genai
            client = genai.Client(api_key=key)
        except Exception as e:
            raise AiAdvisorError(f"初始化 Gemini API 客戶端失敗: {str(e)}")

    prompt = build_advisor_prompt(
        stock_id=stock_id,
        stock_name=stock_name,
        today_analysis=today_analysis,
        df_indicators=df_indicators,
    )

    models_to_try = [model]
    if model != "gemini-3.5-flash":
        models_to_try.append("gemini-3.5-flash")

    last_err: Optional[Exception] = None
    for m in models_to_try:
        try:
            response_stream = client.models.generate_content_stream(
                model=m,
                contents=prompt,
            )
            for chunk in response_stream:
                text = getattr(chunk, "text", None)
                if text:
                    yield text
            return
        except Exception as e:
            last_err = e

    raise AiAdvisorError(f"Gemini API 串流生成失敗: {str(last_err)}")


def generate_ai_advice(
    stock_id: str,
    stock_name: str,
    today_analysis: TodayAnalysis,
    df_indicators: Optional[pd.DataFrame] = None,
    client: Optional[Any] = None,
    api_key: Optional[str] = None,
    model: str = DEFAULT_GEMINI_MODEL,
) -> str:
    """Generate complete AI advice text."""
    chunks = list(stream_ai_advice(
        stock_id=stock_id,
        stock_name=stock_name,
        today_analysis=today_analysis,
        df_indicators=df_indicators,
        client=client,
        api_key=api_key,
        model=model,
    ))
    return "".join(chunks)
