File: `repometa\docs\requirements\requirements_2.md`

---

# py-Repo-Meta 導航強化 P0 需求文件（草稿）

## 1. 文件目的

本文件定義 **py-Repo-Meta 在「導航（navigation）」目的下的 P0 強化需求**。
目標不是擴大成完整靜態分析平台，而是先把目前的「摘要輸出工具」提升為**可供 LLM / Agent / 人類共同使用的正式導航系統**。

本文件只涵蓋 P0，不處理後續 query CLI、ranking、change-aware navigation 等延伸議題。

---

## 2. 背景與現況

目前 py-Repo-Meta 已能從 Python AST 擷取相對豐富的 metadata，包括：

* module-level `imports`
* `classes`
* `functions`
* function `args`
* `return_type`
* `decorators`
* class `bases`
* `metadata_tags`
* `parse_status` / `error_msg` 

但這些資訊沒有被完整保留下來。現行簡化版 SQLite schema 只落庫：

* `filepath`
* `name`
* `qualname`
* `symbol_type`
* `docstring`

且註解直接標明 `start_line` / `end_line` 已被移除。

同時，現有 `file_focus` view 也只輸出：

* file path
* symbol prefix / qualname
* docstring

沒有 line span、imports、bases、decorators、args、return type、依賴關係。

此外，README 與 CLI 說明目前的主流程仍是：

* `build`：建立 `.repometa/repometa.db`
* `export all`
* `export file_focus`

並透過 formatter 輸出 `.pyi` 風格結果。 

**結論：**
目前系統較接近「可讀摘要生成器」，尚未形成真正可跳轉、可縮放、可作為 SSOT 的導航系統。

---

## 3. 問題定義

現況在導航用途上有四個核心缺陷：

### 3.1 缺乏跳轉座標

symbol 沒有正式 line span，導航輸出無法精準指向原始碼位置。

### 3.2 rich metadata 被中途丟失

parser 已抽到的 args / return_type / decorators / bases / imports / metadata_tags 等資訊，未被正式保留到 DB 或正式 artifact。 

### 3.3 沒有單一正式導航 artifact

目前存在 build/export 流程與 markdown-ish file_focus / `.pyi` formatter 路線，導航 authority 不清楚。  

### 3.4 缺乏正式 dependency graph

雖然 parser 會擷取 imports，但沒有正式 file edge / import edge artifact，導致無法穩定支援「相關檔案導覽」。

---

## 4. 目標

P0 的目標是把 py-Repo-Meta 升級為：

> **一個以 JSON repo navigation artifact 為 SSOT、可保留精準跳轉座標與核心結構 metadata，並具備 file-level dependency edges 的 Python repo 導航系統。**

### 具體目標

1. 導航輸出必須能支援 **精準跳轉**
2. parser 已擷取的重要 metadata 不可在中途無故丟失
3. 導航必須有 **單一正式 SSOT artifact**
4. 導航必須能表達 **module/file-level 關聯**
5. 舊輸出可暫時保留，但不得與正式導航 SSOT 競爭 authority

---

## 5. 非目標（P0 不做）

以下不在本次範圍：

* 自然語言搜尋
* callers / shortest path / dependents query CLI
* ranking / importance scoring
* change-aware / git-aware navigation
* 多語言支援
* 完整 symbol-level call graph
* LSP / IDE 即時整合
* 外部套件解析或 import resolution 完整求值

---

## 6. P0 範圍

### 6.1 必做項目

#### A. 補回 symbol line spans

每個 symbol 至少要有：

* `line_start`
* `line_end`

若可穩定取得，建議同步保留：

* `col_start`
* `col_end`

#### B. 保留 richer metadata

至少正式保留以下欄位：

**Module level**

* `file_path`
* `parse_status`
* `error_msg`
* `docstring`
* `imports`

**Class level**

* `name`
* `bases`
* `docstring`
* `metadata_tags`
* `line_start`
* `line_end`

**Function / Method level**

* `name`
* `qualname`
* `args`
* `return_type`
* `is_async`
* `decorators`
* `docstring`
* `metadata_tags`
* `line_start`
* `line_end`

#### C. 定義 JSON repo navigation artifact 為正式 SSOT

新增正式 artifact，例如：

* `repo_map.json`

此 artifact 為**唯一正式導航 authority**。

#### D. 補 file-level dependency edges

至少保存：

* module imports raw strings
* file-to-file dependency edges（即使一開始只做到 best-effort）

---

## 7. 功能需求

## 7.1 Parser / Extractor 契約需求

### FR-1

系統必須對每個成功解析的 class / function / method 產出 line span。

### FR-2

系統必須將 parser 已擷取的核心 metadata 傳遞到正式 artifact，不可只在中間物件存在、最終輸出消失。

### FR-3

對於 unparsable file，系統不得靜默略過；必須在正式 artifact 中保留：

* `parse_status = "UNPARSABLE"`
* `error_msg`

### FR-4

系統必須清楚區分：

* module-level functions
* class methods

且 method 應保有可辨識 parent 的 `qualname` 或等價 parent linkage。

---

## 7.2 Storage / DB 契約需求

### FR-5

SQLite DB 可以保留為 implementation detail，但不得再成為資訊裁剪點。
也就是說，DB 若存在，schema 必須足以保存 P0 所需 metadata。

### FR-6

若 DB 與正式 JSON artifact 並存，**JSON artifact 為導航 SSOT**，DB 僅作快取或查詢加速用途，不得反過來凌駕正式 artifact。

---

## 7.3 Artifact 契約需求

### FR-7

系統必須輸出一份正式 JSON artifact，建議名稱：

* `.repometa/repo_map.json`

### FR-8

正式 JSON artifact 必須包含至少以下 top-level blocks：

* `schema_version`
* `generated_at`
* `repo_root`
* `files`
* `symbols`
* `edges`
* `stats`

### FR-9

正式 JSON artifact 必須是 deterministic-friendly：

* stable ordering
* stable field names
* path normalization rules 明確
* schema 可版本化

### FR-10

正式 JSON artifact 必須能單獨支撐導航，不依賴 README 解釋或 DB 補完。

---

## 7.4 Dependency Edge 契約需求

### FR-11

系統必須至少保存 raw import statements。

### FR-12

系統必須嘗試建立 file-level edges：

* `source_file -> target_file`

### FR-13

若 target 無法解析為 repo 內檔案，必須顯式標記 unresolved，而不是直接丟棄。

---

## 8. 資料模型需求（草案）

以下是 P0 建議的正式 artifact 資料模型草案。

## 8.1 RepoMap

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-03-31T00:00:00Z",
  "repo_root": "/abs/path/to/repo",
  "files": [],
  "symbols": [],
  "edges": [],
  "stats": {}
}
```

---

## 8.2 FileRow

```json
{
  "file_id": "src/repometa/parser.py",
  "file_path": "src/repometa/parser.py",
  "module_name": "repometa.parser",
  "parse_status": "SUCCESS",
  "error_msg": null,
  "docstring": "...",
  "imports": [
    "import ast",
    "from pathlib import Path"
  ]
}
```

### 欄位要求

* `file_id`: 建議採 stable path-based ID
* `file_path`: repo-relative normalized path
* `module_name`: best-effort canonical module name
* `parse_status`: `SUCCESS | UNPARSABLE | SKIPPED`
* `imports`: raw import strings 保留

---

## 8.3 SymbolRow

```json
{
  "symbol_id": "src/repometa/parser.py::RepositoryParser.parse_file",
  "file_id": "src/repometa/parser.py",
  "name": "parse_file",
  "qualname": "RepositoryParser.parse_file",
  "symbol_type": "method",
  "parent_qualname": "RepositoryParser",
  "line_start": 120,
  "line_end": 156,
  "docstring": "...",
  "args": ["self", "file_path: str"],
  "return_type": "ModuleNode",
  "is_async": false,
  "decorators": [],
  "bases": [],
  "metadata_tags": {}
}
```

### 欄位要求

* `symbol_type`: 至少支援 `class | function | method`
* `parent_qualname`: module-level function 可為 `null`
* `bases`: 只對 class 有意義，其餘可空陣列
* `decorators`: function/method/class 視需求保存
* `metadata_tags`: plugin enrich 結果正式保存

---

## 8.4 EdgeRow

```json
{
  "edge_type": "file_import",
  "source_file_id": "src/repometa/cli.py",
  "target_file_id": "src/repometa/parser.py",
  "raw_import": "from repometa.parser import RepositoryParser",
  "is_resolved": true
}
```

### 欄位要求

* `edge_type`: P0 先固定 `file_import`
* `is_resolved`: `true/false`
* unresolved edge 也必須保留 `raw_import`

---

## 9. SSOT 與 authority 規則

### Rule-1

`.repometa/repo_map.json` 為正式導航 SSOT。

### Rule-2

SQLite DB 不是導航 authority，只能作為 internal cache / acceleration layer。

### Rule-3

現有 `export all` / `export file_focus` 可作為 view layer 保留，但其內容必須由正式導航資料推導，不得另走平行 truth。

### Rule-4

若 `repo_map.json` 與 DB / legacy view 不一致，以 `repo_map.json` 為準。

---

## 10. 相容性策略

### 10.1 舊 CLI 相容

現有：

* `build`
* `export all`
* `export file_focus`

可保留，但 `build` 後除了 DB，也應產生 `repo_map.json`。

### 10.2 舊 view 相容

`file_focus` 與 `.pyi` formatter 可暫時保留，但應改為：

* 從正式 navigation model 輸出
* 不再各自重建另一套資料來源

### 10.3 遷移原則

新舊路徑在過渡期間可並存，但不得形成雙 authority。

---

## 11. 驗收標準

## 11.1 功能驗收

### AC-1

對一個成功解析的 Python repo，正式 artifact 中每個 symbol 都具備：

* `file_id`
* `qualname`
* `symbol_type`
* `line_start`
* `line_end`

### AC-2

對至少一個 class，artifact 中可看到：

* `bases`
* `docstring`
* `line_start`
* `line_end`

### AC-3

對至少一個 function/method，artifact 中可看到：

* `args`
* `return_type`
* `decorators`
* `is_async`

### AC-4

對 unparsable file，artifact 中可看到：

* `parse_status = UNPARSABLE`
* `error_msg`

### AC-5

對 repo 內 import，至少能產出部分 resolved `file_import` edges。

### AC-6

對無法 resolve 的 import，不會直接消失，而是以 `is_resolved = false` 保留。

### AC-7

`file_focus` 或等價 view 能顯示 line spans 與 richer metadata，而不再只是 qualname + docstring。

---

## 11.2 非功能驗收

### NFR-1

輸出欄位名稱穩定，不得每次 build 漂移。

### NFR-2

同一 repo 狀態重跑，artifact ordering 應穩定。

### NFR-3

P0 實作不得破壞現有基本 build/export 可用性。

### NFR-4

遇到 parse 失敗必須誠實暴露，不得靜默吞掉。

---

## 12. 風險與限制

### 12.1 Import resolution 可能不完整

P0 只要求 file-level best-effort，不要求完整 Python import resolver。

### 12.2 line span 需依賴 AST 節點位置

若某些節點資訊不足，需定義 fallback 行為，但不得假造。

### 12.3 歷史相容 wrapper 可能成為污染源

目前 `parse_file(filepath: Path) -> list[dict]` 的 backward compatibility wrapper 會把 rich metadata 壓扁。
P0 需要避免正式 artifact 再走這種壓扁路徑。

---

## 13. 開放問題

1. `symbol_id` 是否採 path+qualname deterministic string 即可，還是需要 hash ID
2. `module_name` 是否需要正式 canonicalization 規則
3. `SKIPPED` 的定義是否納入 P0，或暫只處理 `SUCCESS / UNPARSABLE`
4. DB schema 是否要一步到位擴充，還是先以 artifact 為主、DB minimal 跟上
5. `.pyi` formatter 是否在 P0 內同步升級，還是只要求正式 JSON SSOT 先落地

---

# 設計卡草稿

以下是附在需求文件中的**設計卡草稿**。這不是小 PR 切分，只是先把整體實作設計框起來。

---

## 設計卡草稿：PRD-NAV-P0

**名稱：** py-Repo-Meta Navigation Foundation Closure
**層級：** 單一需求設計卡草稿
**目的：** 建立正式導航 SSOT 與 P0 基礎能力

---

## A. 問題陳述

py-Repo-Meta 目前已具備 AST metadata 擷取能力，但在導航產品層缺乏正式 SSOT、精準跳轉座標與依賴關聯，使其更像摘要生成器而非導航系統。
本設計卡要補齊導航最小閉環：

* 能指到哪個 symbol、哪幾行
* 能看到足夠 metadata 判斷是否該讀
* 能知道檔案之間的基本依賴
* 有唯一正式 artifact，避免雙真相

---

## B. 設計目標

1. 建立 `.repometa/repo_map.json` 作為正式導航 SSOT
2. 將 parser rich metadata 正式保留到 artifact
3. 補回 symbol line spans
4. 建立 file-level import edges
5. 讓 legacy export views 成為正式導航資料的派生 view，而不是平行資料源

---

## C. 設計原則

### C-1. JSON artifact first

正式導航資料以 JSON artifact 為主，不以 DB schema 或 markdown view 為 authority。

### C-2. No silent metadata loss

parser 已經拿到的重要欄位，不可在中途無故遺失。

### C-3. Honest parsing state

parse failure 必須保留在 artifact 中，不可偽裝成不存在。

### C-4. Best-effort dependency closure

P0 只做 file-level dependency best-effort，不追求完整 import semantics。

### C-5. Legacy view derives from SSOT

`file_focus` / `.pyi` formatter 後續都應從 repo_map 推導。

---

## D. 實作輪廓

## D.1 Parser 層

調整 AST extractor，讓 class/function/method 都保留 line span。

### 預期新增/調整欄位

* `line_start`
* `line_end`
* `parent_qualname`
* 視需要補 `col_start`
* 視需要補 `col_end`

---

## D.2 Canonical navigation model

新增一組正式 navigation model，與 legacy wrapper 脫鉤。

### 建議模型

* `RepoMap`
* `FileRow`
* `SymbolRow`
* `EdgeRow`

此層直接承接 parser rich metadata，不再先壓成最舊版 `list[dict] symbols` 格式。

---

## D.3 Artifact writer

新增 repo_map writer，在 build 階段輸出：

* `.repometa/repo_map.json`

### writer 要求

* stable ordering
* stable schema_version
* deterministic path normalization
* 顯式保留 unparsable rows

---

## D.4 DB 層

DB 可繼續存在，但需擴充以承載 P0 所需欄位，或至少不阻礙 artifact 生成。

### 最低要求

不得再以「token optimization」為由刪除導航必要欄位，例如 line spans。現行 `db.py` 直接拿掉 `start_line / end_line` 的作法，不適用於正式導航層。

---

## D.5 Dependency edge builder

新增 file-level edge builder：

輸入：

* file path
* raw imports
* repo root

輸出：

* `file_import` edges
* `is_resolved`
* `raw_import`

P0 允許 unresolved，但不允許直接丟失。

---

## D.6 View 層

現有 `file_focus` 重新改寫為 consume formal navigation model。

### 升級後 file_focus 至少應顯示

* file path
* parse status
* imports
* symbol list
* symbol line spans
* class bases
* function args / return type
* decorators
* metadata tags（如有）

而不是只剩 qualname + docstring。現行 view 過薄。

---

## E. 介面變更草案

## E.1 Build

現有 `build(repo_path)` 行為擴充為：

1. parse repo
2. 寫 DB（可選）
3. 寫 `.repometa/repo_map.json`

## E.2 Export

現有 `export all` / `export file_focus` 改為讀取正式 navigation model 或 repo_map，而非另行從裁剪後 schema 重組。

---

## F. 測試策略草案

### F-1. Parser metadata retention tests

驗證 args / return_type / decorators / bases / metadata_tags / line spans 能進入正式 artifact。

### F-2. Unparsable honesty tests

壞掉的 Python 檔案必須在 artifact 中留下 `UNPARSABLE + error_msg`。

### F-3. Edge resolution tests

針對：

* repo internal import
* relative import
* unresolved third-party import
  驗證 edge rows 行為正確。

### F-4. Stable output tests

同一 fixture 重跑兩次，除 timestamp 外 ordering 與內容一致。

### F-5. Legacy view derivation tests

`file_focus` 必須由正式 navigation model 推導，且含 richer metadata。

---

## G. 驗收裁定草案

P0 完成的條件不是「能輸出更多字」，而是：

1. `repo_map.json` 成為明確導航 SSOT
2. symbol 具備 line span
3. rich metadata 被正式保留
4. file-level edges 存在
5. parse failure 誠實可見
6. legacy view 不再形成第二套 truth

---

## H. 明確不做

本設計卡不處理：

* query CLI
* ranking
* shortest path / callers
* git diff aware navigation
* 多語言支援
* 完整 import resolver

---

## I. 建議後續延伸方向（非本卡範圍）

P0 完成後，下一步才值得考慮：

* query CLI
* related files / dependents / path
* symbol importance ranking
* changed-files focused navigation
* prompt-oriented stage outputs（pre-scout / scout / check 專用 view）
