# Design: 自選股多群組管理、建議策略直覽與選股產業過濾強化

## Context

見 `proposal.md`。目前選股過濾與自選股追蹤機制已初步成形，但面臨三個痛點：
1. 產業選單包含幾十個細分產業，難以快速切換波段主流（科技股 vs 非科技股）。
2. 在選股掃描結果或夜間作戰清單中找到標的後，缺乏一鍵收藏機制，必須切換頁面手動輸入代號。
3. 自選股缺乏分類機制（全堆在單一清單），且清單僅有收盤價與損益，缺乏今日策略訊號與風控點位。

## Goals / Non-Goals

**Goals:**
- 提供簡潔的「全部產業 / 科技股（電子八大類） / 非科技股」篩選，修復兩階段快篩產業缺失。
- 於即時選股結果表格與夜間作戰清單每列提供 ⭐ 一鍵加入/取消自選功能。
- 自選股清單直接呈現今日動態「建議策略」（進場策略名稱、進場/停損/停利價，或觀望條件）。
- 提供本機秒開快取與手動「🔄 同步最新行情」按鈕。
- 於 SQLite 實作多群組資料模型，支援自訂群組、多標籤歸屬與群組分頁瀏覽。

**Non-Goals:**
- 不支援樹狀巢狀子群組。
- 不做盤中即時逐筆推播（維持盤後分析架構）。

## Decisions

### 1. 科技股與非科技股劃分標準
- **決策**：在 `backend/app/analysis/params.py` 定義標準集合：
  ```python
  TECH_INDUSTRIES = {
      "半導體業",
      "電腦及周邊設備業",
      "光電業",
      "通信網路業",
      "電子零組件業",
      "電子通路業",
      "資訊服務業",
      "其他電子業",
  }
  ```
  在 `resolve_scan_pool` 中：
  - `tech`: 僅保留 `industry_category in TECH_INDUSTRIES`。
  - `non_tech`: 僅保留 `industry_category not in TECH_INDUSTRIES`（且排除空字串與 ETF）。
- **兩階段快篩修正**：在證交所初篩完成後，立即呼叫 `_enrich_stock_metadata` 填入本機 `stock_info` 中的產業分類，再執行產業過濾，避免候選股因未帶產業別而被全數過濾。

### 2. 選股表格一鍵加自選連動
- **決策**：`MarketScanner.tsx` 接收 `watchlist`、`onToggleWatchlist`、`isWatchlistLoading` 屬性。
- **UI 佈局**：在「夜間作戰清單」與「即時掃描結果」最左側欄位新增 ⭐ 收藏按鈕。已在自選股清單者顯示高亮實心黃星（`⭐`），否則顯示灰色空心星號（`☆`），點擊後立即觸發加入或移除，並保持兩邊即時同步。

### 3. 自選股動態建議策略計算
- **決策**：在 `backend/app/api/watchlist.py` 的 `_enrich_watchlist_item` 中，讀取該股票最新日 K、法人、融資與財報快取，呼叫 `assemble_today_analysis`。
- **資料輸出**：
  - `suggested_strategy`: 若有策略進場，回傳觸發進場之策略名稱（如「均線拉回 20MA」）；若全為觀望則回傳 `None` 或「觀望」。
  - `entry_price`、`stop_loss`、`take_profit`：進場時填入具體風控價位。
  - `trigger_condition`：觀望時填入最近技術面距離觸發之條件或狀態說明。
- **快取秒開與手動同步**：
  - 預設直接讀取本機 SQLite 資料秒開，避免網路卡頓。
  - 新增 `POST /api/watchlist/sync` 端點，使用者點擊「🔄 同步最新行情」時，批次為自選股向 FinMind 抓取最新日 K 與籌碼數據並更新快取。

### 4. 自選股多群組 SQLite 資料庫設計
- **資料表結構**：
  ```sql
  CREATE TABLE IF NOT EXISTS watchlist_groups (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
  );

  CREATE TABLE IF NOT EXISTS watchlist_group_items (
      stock_id TEXT NOT NULL,
      group_id INTEGER NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (stock_id, group_id),
      FOREIGN KEY (stock_id) REFERENCES watchlist(stock_id) ON DELETE CASCADE,
      FOREIGN KEY (group_id) REFERENCES watchlist_groups(id) ON DELETE CASCADE
  );
  ```
- **多對多標籤機制**：
  - 「全部 (公用池)」為虛擬分頁（查詢全部 `watchlist`）。
  - 使用者可自由建立群組（如「AI概念」、「波段核心」）。
  - 一檔股票可關聯至多個 `group_id`。
  - 刪除群組時，僅刪除 `watchlist_group_items` 關聯，股票本體在公用池中保留。
  - 在自選股公用池刪除股票時，外鍵連動清除所有群組關聯。

## Risks / Trade-offs

- **[Risk] 自選股檔數較多時，動態計算策略影響 API 回應時間**
  - **Mitigation**：利用本機 SQLite 已建立好的日 K 快取，單股評估耗時 < 15ms，20 檔自選股可在 300ms 內完成；若自選股超過 50 檔，可加入短期記憶體快取（TTL 60 秒）。
- **[Risk] 新上市股票或冷門股無產業分類資料**
  - **Mitigation**：若 `industry_category` 為空，預設不列入「科技股」，但在「全部產業」中正常顯示，並於介面標示「未分類」。
