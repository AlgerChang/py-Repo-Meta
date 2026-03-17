file `repometa\docs\requirements\requirement_v1.md`

--

# Python Repository Metadata Generator (PRMG) 需求與架構設計文件

## 1. 專案願景與目標

本專案旨在打造一個高效能的 Python 程式碼庫元數據生成器 (Repository Metadata Generator)。其核心目標是**從大型 Python 專案中提取「LLM 真正需要的最小有效資訊」**，大幅優化 LLM 的 Context Window 運用效率。

透過消除冗餘的實作細節，並專注於程式碼的結構與依賴關係，本工具能協助 LLM 代理 (Agents) 或程式碼輔助工具以極低的 Token 成本，建立全局的 Codebase 認知。

## 2. 核心資訊提取策略 (Token 優化導向)

為確保提取出的 Metadata 具備高語義價值且無冗餘 Token，提取邏輯需嚴格遵循以下準則：

* **必須提取 (High Value)：**
    * 模組層級的 Docstrings (Module docstrings)。
    * Class/Function 的定義與簽名 (Signatures)，包含參數名稱與預設值。
    * Type Hints (型別提示) 與 Return Types。
    * Class 的繼承關係 (Inheritance)。
    * 模組間的 Import 依賴關係圖 (Dependency Graph)。
* **必須捨棄 (Token Waste)：**
    * Function/Method 內部的具體實作邏輯 (If/Else, Loops, 變數賦值)。
    * 非文檔性質的行內註解 (Inline comments，除非帶有特定的 Plugin 標籤)。
    * 無對外暴露的 Private 內部函式 (可配置是否保留)。

## 3. 系統架構設計

系統採分層架構 (Layered Architecture) 設計，確保低耦合性與高可維護性。

1.  **解析層 (Parsing Layer)：** 負責將源碼轉換為語法樹或圖結構。
2.  **提取層 (Extraction/Analysis Layer)：** 遍歷語法樹，根據策略過濾並提取關鍵 Symbol 與 Edge。
3.  **儲存層 (Storage Layer)：** 將提取的 Metadata 進行持久化儲存，支援增量更新。
4.  **輸出層 (Formatter Layer)：** 將儲存的資料序列化為 LLM 友好的格式 (如 JSON、簡化的 Markdown，或專用的 Prompt 結構)。
5.  **擴充層 (Plugin System)：** 提供 Hook 介面，允許開發者透過自定義 Python 腳本介入 AST 遍歷過程，新增特定的 Metadata 提取規則 (例如：識別特定的 API Router 裝飾器)。

## 4. 技術選型與架構取捨 (Trade-offs)

在選擇底層解析與儲存工具時，我們針對不同的技術方案進行了評估：

### 4.1 解析器 (Parser) 選型評估

| 技術方案 | 描述 | Pros (優勢) | Cons (劣勢) | 適用場景建議 |
| :--- | :--- | :--- | :--- | :--- |
| **Python `ast`** | 標準庫內建抽象語法樹 | 執行速度快，無外部依賴，結構簡單。 | 會丟失部分排版資訊（對 LLM 影響小），無法處理語法錯誤的源碼。 | **首選**：若僅針對單一 Python 語言且追求極簡架構。 |
| **Tree-sitter** | 增量式具象語法樹解析器 | 解析極快，支援增量更新，跨語言支援強大，容錯率高。 | 需編譯 C 擴展，依賴較重，Python 綁定 API 學習曲線稍陡。 | **進階選擇**：若未來需擴展至多語言 (如 TS/Go) 或需極限效能。 |
| **LibCST** | 保留排版細節的具象語法樹 | 能完美還原源碼，適合做 Code Refactoring。 | 效能較慢，解析出的樹結構過於龐大複雜。 | **不建議**：保留格式對「精簡 LLM Context」無直接益處，徒增開銷。 |
| **Jedi** | 靜態分析與自動補全庫 | 類型推斷 (Type Inference) 能力極強，能解析動態屬性。 | 初始化慢，用於全 Repo 批量分析時效能瓶頸明顯。 | **不建議**作為基礎 Parser，但可作為 Plugin 用於深度解析特定節點。 |

**架構師建議：** 初期 MVP 優先採用標準庫 **`ast`** 進行快速迭代。若考量到未來跨語言支援或巨型 Repo 的增量解析，底層介面應設計為 Parser 抽象層，以便未來無縫切換至 **Tree-sitter**。

### 4.2 儲存與索引 (Storage & Indexing) 選型評估

| 技術方案 | 描述 | Pros (優勢) | Cons (劣勢) |
| :--- | :--- | :--- | :--- |
| **SQLite** | 輕量級關聯式資料庫 | 無伺服器，查詢靈活 (支援 SQL)，支援 Local Cache，易於除錯與打包。 | 非圖結構原生，處理複雜遞迴依賴查詢 (如 N 階調用圖) 需依賴 CTE。 |
| **SCIP** | Sourcegraph 開發的程式碼索引標準 | 專為 Code Intelligence 設計，語義關聯精準，標準化程度高。 | 協定較為複雜，生成的 Protobuf 格式需額外轉換 LLM 才能閱讀。 |

**架構師建議：** 使用 **SQLite** 作為本地快取層，能完美支援「增量更新 (Incremental Updates)」需求（透過比對檔案 Hash），並使用 JSON 欄位儲存序列化的參數資訊。

## 5. 非功能性需求 (NFRs)

* **執行效能：** 對於百萬行級別的程式碼庫，首次全局索引時間應控制在 30 秒內。
* **增量更新 (Incremental Updates)：** 必須支援檔案層級的增量解析。當開發者修改單一檔案時，僅重新解析該檔案並更新其在 SQLite 中的節點，耗時需小於 500 毫秒。
* **輸出格式化：** 提供高密度的文字輸出格式，例如類似 Python Stub 文件 (`.pyi`) 的精簡表示法，確保 Token 使用率達到最優。
