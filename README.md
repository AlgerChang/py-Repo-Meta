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
- **Command-Line Interface (CLI)**: An easy-to-use Typer CLI for building the database and exporting metadata.

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

The CLI tool `repometa` allows you to build the metadata database and export views.

**1. Build the Database**

Parse the Python files in a target repository and store the metadata in a `.repometa/repometa.db` SQLite database:

```bash
# From within the repometa/ directory
poetry run repometa build /path/to/your/python/project
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
- **Command-Line Interface (CLI)**：提供易於使用的 Typer CLI，用於建置 database 或 export metadata。

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

CLI 工具 `repometa` 可以讓您建置 metadata database 並輸出指定的 view。

**1. Build the Database (建置資料庫)**

解析目標 repository 中的 Python 檔案，並將 metadata 儲存至 SQLite database (`.repometa/repometa.db`) 內：

```bash
# 請在 repometa/ 目錄下執行
poetry run repometa build /path/to/your/python/project
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

#### 程式化使用方式 (Programmatic Usage)

您也可以在程式碼中直接呼叫 PRMG (Python Repo Meta Graph) engine。請參考 `repometa/main.py` 了解完整的範例，包含如何：
1. 初始化 `DatabaseManager` 與 `ASTParser`。
2. 執行 `RepoScanner` 來增量（incrementally）解析 repository。
3. 執行 `PluginManager` 的 global phase 來豐富資料。
4. 使用 `QueryEngine` 與 `PyiFormatter` 輸出結果。