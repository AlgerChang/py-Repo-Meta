# py-Repo-Meta

[English Version](#english-version) | [繁體中文版](#繁體中文版)

---

## English Version

**py-Repo-Meta** (or `repometa`) is a local Python repository metadata extractor. It parses Python files in a given repository using an AST parser and stores rich metadata (such as classes, functions, variables, and dependencies) in a local SQLite database. It also provides an extensible plugin system and powerful export capabilities, including generating `.pyi` type stubs for your repository.

### Features

- **AST-Based Parsing**: Efficiently scans and parses Python files to extract structural metadata.
- **Local SQLite Storage**: Stores repository metadata locally in a `repometa.db` database for fast, offline querying.
- **Extensible Plugin System**: Enrich extracted metadata with framework-specific details. (For example, a FastAPI plugin is included).
- **Export & Formatting**: Generate `.pyi` type hints for the entire repository or focus on a single specific file.
- **Caller & Consumer Querying**: Query direct callers (`callers`) or complete references and dependents (`consumers`) across code, tests, and CI/workflows with role and edge classification.
- **Command-Line Interface (CLI)**: An easy-to-use Typer CLI for building the database, querying relations, and exporting metadata.

### Structure

The core extraction logic and CLI are located in the `repometa/` directory, managed by Poetry.

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/)

### Installation

Clone the repository and install the dependencies using Poetry:

```bash
git clone <your-repo-url>
cd py-Repo-Meta/repometa
poetry install
```

### Usage

#### Command-Line Interface (CLI)

The CLI tool `repometa` allows you to build the metadata database, query symbols, and export views.

**1. Build the Database**

Parse the Python files in a target repository and store the metadata in a `.repometa/repometa.db` SQLite database:

```bash
# From within the repometa/ directory
poetry run repometa build /path/to/your/python/project
```

Build indexes every defined class, function, and method—including names that
start with `_`—so navigation queries can locate implementation symbols. To
produce an explicit public-only summary instead, add this to the target
repository's `pyproject.toml`:

```toml
[tool.prmg]
include_private = false
```

**2. Export Metadata**

Export the metadata using PRMG engine formatters (e.g., as `.pyi` files).

- **Export entire repository context:**
  ```bash
  poetry run repometa export all --repo-path /path/to/your/python/project
  ```

- **Export context for a specific target file:**
  ```bash
  poetry run repometa export file_focus --target /path/to/your/python/project/some_module.py --repo-path /path/to/your/python/project
  ```

**3. Query Metadata (Callers & Consumers)**

Query relationships and dependents directly from the built metadata database in JSON format.

- **Query Callers (`callers`):**
  Find all locations that directly invoke a target function, method, class, or module. Results include the calling symbol, file path, line numbers, and edge kind (`call`, `test_call`, `smoke_call`).
  ```bash
  # Query callers by symbol qualname or unambiguous short name
  poetry run repometa query callers my_package.module.my_function

  # Query callers using --name or numeric --id
  poetry run repometa query callers --name my_function
  poetry run repometa query callers --id 42
  ```

- **Query Consumers (`consumers`):**
  Find all references and dependents across the codebase. In addition to direct calls, it tracks imports (`import`), data/variable references (`data_dependency`), and external invocations from CI workflows or scripts (`command_dependency`). It also classifies consumer roles (`production`, `test`, `smoke`, `ci`).
  ```bash
  # Query all consumers for a function, class, data constant, or module
  poetry run repometa query consumers my_package.module.my_function
  poetry run repometa query consumers my_package.module.MY_CONSTANT
  poetry run repometa query consumers my_package.module

  # Query consumers using --name or numeric --id
  poetry run repometa query consumers --name MY_CONSTANT
  poetry run repometa query consumers --id 42
  ```

#### Programmatic Usage

You can also use the PRMG (Python Repo Meta Graph) engine programmatically. Check `repometa/main.py` for a complete example of how to:
1. Initialize the `DatabaseManager` and `ASTParser`.
2. Run the `RepoScanner` to parse the repository incrementally.
3. Run the `PluginManager`'s global phase to enrich the data.
4. Use `QueryEngine` and `PyiFormatter` to output the results.

---

## 繁體中文版

**py-Repo-Meta**（或稱 `repometa`）是一個本機端的 Python repository metadata（元資料）截取工具。它會使用 AST parser 解析給定 repository 中的 Python 檔案，並將豐富的 metadata（例如 classes, functions, variables 以及 dependencies）儲存在本機的 SQLite database 中。本專案也提供了一個可擴充的 plugin 系統和強大的 export 功能，包含為你的 repository 產生 `.pyi` type stubs。

### 核心功能 (Features)

- **AST-Based Parsing**：高效率掃描並解析 Python 檔案，以截取結構化的 metadata。
- **Local SQLite Storage**：將 repository metadata 儲存在本機的 `repometa.db` database 中，以便進行快速、離線的 querying（查詢）。
- **Extensible Plugin System**：透過框架專屬的細節來豐富截取到的 metadata。（例如：內建 FastAPI plugin）。
- **Export & Formatting**：為整個 repository 產生 `.pyi` type hints，或是聚焦於單一特定的檔案進行產生。
- **Caller 與 Consumer 查詢**：精確查詢呼叫指定符號的呼叫者（`callers`），或查詢跨程式碼、測試與 CI/工作流程的引用與依賴者（`consumers`），並支援角色分類與邊類型標註。
- **Command-Line Interface (CLI)**：提供易於使用的 Typer CLI，用於建置 database、查詢關聯與 export metadata。

### 專案結構 (Structure)

核心的截取邏輯與 CLI 位於 `repometa/` 目錄中，並由 Poetry 進行套件管理。

### 系統需求 (Prerequisites)

- Python 3.10+
- [Poetry](https://python-poetry.org/)

### 安裝方式 (Installation)

Clone 這個 repository，並使用 Poetry 安裝 dependencies：

```bash
git clone <your-repo-url>
cd py-Repo-Meta/repometa
poetry install
```

### 使用方式 (Usage)

#### Command-Line Interface (CLI)

CLI 工具 `repometa` 可以讓您建置 metadata database、查詢符號關聯並輸出指定的 view。

**1. Build the Database (建置資料庫)**

解析目標 repository 中的 Python 檔案，並將 metadata 儲存至 SQLite database (`.repometa/repometa.db`) 內：

```bash
# 請在 repometa/ 目錄下執行
poetry run repometa build /path/to/your/python/project
```

Build 預設會索引所有已定義的 class、function 與 method（包含 `_` 開頭的名稱），
讓導航查詢可以定位實作符號。若需要明確的僅公開 API 摘要，請在目標 repository 的
`pyproject.toml` 加入：

```toml
[tool.prmg]
include_private = false
```

**2. Export Metadata (輸出元資料)**

使用 PRMG engine formatters 來 export metadata（例如輸出為 `.pyi` 檔案）。

- **Export 整個 repository context：**
  ```bash
  poetry run repometa export all --repo-path /path/to/your/python/project
  ```

- **Export 特定目標檔案的 context：**
  ```bash
  poetry run repometa export file_focus --target /path/to/your/python/project/some_module.py --repo-path /path/to/your/python/project
  ```

**3. Query Metadata (查詢元資料 - Callers 與 Consumers)**

直接從已建置的 metadata 資料庫中以 JSON 格式查詢符號的呼叫者與依賴關係。

- **查詢呼叫者 (`callers`)：**
  找出直接呼叫指定符號（函式、方法、類別或模組）的所有位置。回傳結果包含呼叫者符號名稱、檔案路徑、起始行號/列號，並區分呼叫情境（一般呼叫 `call`、測試呼叫 `test_call`、冒煙測試呼叫 `smoke_call`）。
  ```bash
  # 透過符號 qualname 或唯一名稱查詢呼叫者
  poetry run repometa query callers my_package.module.my_function

  # 使用 --name 或符號數值 --id 查詢
  poetry run repometa query callers --name my_function
  poetry run repometa query callers --id 42
  ```

- **查詢依賴與使用者 (`consumers`)：**
  找出整個專案中引用或依賴目標符號的所有位置。除了函式呼叫外，亦涵蓋模組匯入（`import`）、常數/資料相依（`data_dependency`）與外部 CI/Workflow 腳本指令依賴（`command_dependency`），並自動標記消費者角色來源（`production`、`test`、`smoke`、`ci`）。
  ```bash
  # 查詢函式、類別、資料常數或模組的所有 Consumers
  poetry run repometa query consumers my_package.module.my_function
  poetry run repometa query consumers my_package.module.MY_CONSTANT
  poetry run repometa query consumers my_package.module

  # 使用 --name 或符號數值 --id 查詢
  poetry run repometa query consumers --name MY_CONSTANT
  poetry run repometa query consumers --id 42
  ```

#### 程式化使用方式 (Programmatic Usage)

您也可以在程式碼中直接呼叫 PRMG (Python Repo Meta Graph) engine。請參考 `repometa/main.py` 了解完整的範例，包含如何：
1. 初始化 `DatabaseManager` 與 `ASTParser`。
2. 執行 `RepoScanner` 來增量（incrementally）解析 repository。
3. 執行 `PluginManager` 的 global phase 來豐富資料。
4. 使用 `QueryEngine` 與 `PyiFormatter` 輸出結果。
