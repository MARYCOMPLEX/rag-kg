# Python 代码规范与工程约定

本文档是 **RAG-KG Copilot** 项目的代码规范与工程约定。所有参与者（含 AI 协作）必须遵循。规范以 **2026 年 Python 生态最佳实践**为基准，兼顾**长期可维护性**与**未来微服务化演进**。

> 底层准则：**接口先于实现；模块化先于优化；可测试先于便捷**。

---

## 目录

1. [语言与工具链](#1-语言与工具链)
2. [仓库与目录结构](#2-仓库与目录结构)
3. [依赖方向与架构边界](#3-依赖方向与架构边界)
4. [命名约定](#4-命名约定)
5. [类型系统](#5-类型系统)
6. [不可变性与数据建模](#6-不可变性与数据建模)
7. [模块设计与接口（Protocol）](#7-模块设计与接口protocol)
8. [错误处理](#8-错误处理)
9. [异步与并发](#9-异步与并发)
10. [配置管理](#10-配置管理)
11. [日志与可观测性](#11-日志与可观测性)
12. [数据访问与存储](#12-数据访问与存储)
13. [API 层约定](#13-api-层约定)
14. [LLM 与 Prompt 规范](#14-llm-与-prompt-规范)
15. [测试规范](#15-测试规范)
16. [文档与注释](#16-文档与注释)
17. [依赖管理](#17-依赖管理)
18. [版本控制与提交](#18-版本控制与提交)
19. [代码审查清单](#19-代码审查清单)
20. [CI/CD 红线](#20-cicd-红线)
21. [演进与抽服务准则](#21-演进与抽服务准则)

---

## 1. 语言与工具链

### 1.1 基线版本


| 项                | 版本                                                                    | 说明                                    |
| ---------------- | --------------------------------------------------------------------- | ------------------------------------- |
| Python           | **3.12+**（推荐 3.13）                                                    | 必须使用 PEP 695 泛型语法与 `type` 语句          |
| 包管理              | **uv**                                                                | 禁止混用 pip/poetry/pdm，锁文件以 `uv.lock` 为准 |
| Linter/Formatter | **ruff**                                                              | 覆盖 pyflakes/isort/black/pyupgrade     |
| 类型检查             | **pyright**（strict）                                                   | CI 必过；mypy 可作 IDE 辅助但非权威              |
| 架构校验             | **tach** 或 **import-linter**                                          | 强制依赖方向                                |
| 测试               | **pytest** + **pytest-asyncio** + **testcontainers** + **hypothesis** | &nbsp;                                |
| 任务队列             | **Arq**（Redis）                                                        | 禁止 Celery 直到规模证明必要                    |
| Web 框架           | **FastAPI**（async） + **uvicorn**                                      | &nbsp;                                |
| 数据校验             | **Pydantic v2**                                                       | &nbsp;                                |
| ORM              | **SQLAlchemy 2.0 async** + **Alembic**                                | &nbsp;                                |
| 日志               | **structlog**（JSON）                                                   | &nbsp;                                |
| 可观测              | **OpenTelemetry** Python + **Langfuse**（LLM trace）                    | &nbsp;                                |
| CLI              | **Typer**                                                             | &nbsp;                                |


### 1.2 工具锁定

- 工具版本通过 `uv.lock` 锁定；CI 使用 `uv sync --frozen`。
- `ruff`、`pyright`、`tach` 配置集中在 `pyproject.toml` 或对应配置文件，**禁止**在子包中覆盖。
- 任何新工具进入栈之前需在 ADR（Architecture Decision Record）中记录采纳理由。

---

## 2. 仓库与目录结构

### 2.1 Monorepo 骨架

```
rag-kg-copilot/
├── apps/                     # 可执行入口（多个，共享 packages）
│   ├── api/                  # FastAPI 在线服务
│   ├── worker/               # Arq 异步 worker
│   └── cli/                  # 管理命令
├── packages/                 # 领域模块（每个子目录 = 未来一个候选服务）
│   ├── core/                 # 领域模型（零外部依赖）
│   ├── eventbus/             # 进程内事件总线（预留 Kafka 切换）
│   ├── ingestion/            # L1: 解析 / chunk / dedup
│   ├── structuring/          # L2: NER / RE / EL
│   ├── indexing/             # L3: 四索引
│   ├── retrieval/            # L4: Agent 检索规划
│   ├── orchestration/        # L5: 任务模板
│   ├── embedding/            # Embedder / Reranker
│   ├── llm/                  # LLM 网关
│   └── evaluation/           # 评测
├── infra/                    # docker-compose / helm / terraform
├── tests/                    # unit / integration / e2e
├── scripts/                  # 一次性脚本（纳入 git，但明确标注）
├── docs/
│   ├── adr/                  # Architecture Decision Records
│   ├── runbook/              # 运维手册
│   └── api/                  # 对外 API 文档
├── pyproject.toml            # uv workspace 根
├── uv.lock
├── CODING_STANDARDS.md       # 本文件
├── README.md
└── Makefile
```

### 2.2 文件与模块尺寸


| 对象          | 推荐        | 硬上限       | 超限必须做的事                  |
| ----------- | --------- | --------- | ------------------------ |
| 单个 `.py` 文件 | 200–400 行 | **800 行** | 拆分成子模块                   |
| 函数/方法       | < 30 行    | **50 行**  | 抽子函数                     |
| 类           | < 150 行   | **300 行** | 分职责拆类                    |
| 函数参数        | ≤ 4       | **6**     | 引入 dataclass/Pydantic 组装 |
| 嵌套层数        | ≤ 3       | **4**     | 早返回 / 抽函数                |
| 圈复杂度        | ≤ 10      | **15**    | 重构                       |


### 2.3 每个 package 的标准结构

```
packages/<domain>/
├── __init__.py            # 只导出公开 API（见 3.3）
├── protocols.py           # 对外 Protocol 接口
├── models.py              # 该领域特有的 Pydantic 模型（引用 core.models）
├── errors.py              # 该领域特有的异常
├── service.py             # 门面（Facade）——对外唯一入口
├── adapters/              # 具体实现（DB/外部 SDK/模型）
│   └── __init__.py
├── _internal/             # 下划线前缀 = 包内私有，禁止被其他 package import
│   └── ...
└── tests/                 # 紧邻的单元测试（可选，也可全部放 /tests）
```

**硬规矩**：

- 其他 package 只 `from packages.foo import X`，不准 `from packages.foo.adapters.bar import Y`。
- `_internal/` 开头的任何路径都视为私有。违规 CI 红。

---

## 3. 依赖方向与架构边界

### 3.1 分层

```
apps  →  orchestration  →  retrieval  →  {indexing, structuring, ingestion}
                                           ↓
                                     {llm, embedding}
                                           ↓
                                       eventbus
                                           ↓
                                         core
```

**规则**：

1. 箭头所指方向只能单向 import。
2. 同层模块之间**不能**直接 import 实现，必须经由 `protocols.py` 定义的接口。
3. `core` 模块零依赖（除 `pydantic`、stdlib）。
4. `adapters/` 可以 import 第三方库；`service.py`、`protocols.py`、`models.py` 内禁止 import 第三方外部 SDK。

### 3.2 校验

- `pyproject.toml` 中配置 `tach` 或 `import-linter`。
- CI 阶段 `make arch` 校验，失败即阻塞合并。
- 新增 package 必须在 `tach.yml` 登记边界。

### 3.3 `__init__.py` 的作用

```python
# packages/indexing/__init__.py
from packages.indexing.protocols import (
    VectorIndex,
    GraphIndex,
    BM25Index,
    RetrievalCoordinator,
)
from packages.indexing.service import HybridRetrievalCoordinator

__all__ = [
    "VectorIndex",
    "GraphIndex",
    "BM25Index",
    "RetrievalCoordinator",
    "HybridRetrievalCoordinator",
]
```

- 只导出公开 API；`__all__` 必须显式写。
- 禁止在 `__init__.py` 写业务逻辑。

---

## 4. 命名约定


| 对象                  | 规则                                     | 示例                                                   |
| ------------------- | -------------------------------------- | ---------------------------------------------------- |
| 模块/包                | `snake_case`，短而准                       | `graph_index.py`, `leiden_community.py`              |
| 类 / Type / Protocol | `PascalCase`                           | `HybridRetrievalCoordinator`, `VectorIndex`          |
| 函数 / 方法 / 变量        | `snake_case`                           | `expand_entity`, `chunk_text`                        |
| 布尔值                 | `is_` / `has_` / `should_` / `can_` 前缀 | `is_ready`, `has_evidence`                           |
| 常量                  | `UPPER_SNAKE_CASE`                     | `DEFAULT_BEAM_WIDTH`                                 |
| 私有                  | 单下划线 `_foo`；包内私有放 `_internal/`         | &nbsp;                                               |
| 类型别名 / NewType      | `PascalCase`                           | `type ChunkId = str`                                 |
| 测试函数                | `test_<行为>_<场景>`                       | `test_expand_entity_returns_empty_when_no_neighbors` |
| 异常类                 | 以 `Error` 结尾                           | `ParseError`, `RetrievalTimeoutError`                |
| 事件类                 | 过去式动词                                  | `DocumentParsed`, `KGUpdated`                        |


**禁止**：

- 无意义缩写：`usr`、`mgr`、`proc`（除行业通用如 `id`, `url`, `db`）。
- 单字母变量（循环除外：`i`, `j`, `k`, `v`, `_`）。
- 形容词堆叠：`simple_fast_new_retriever` → 重命名。

---

## 5. 类型系统

### 5.1 硬要求

- **所有**函数签名必须标注参数与返回类型。
- **所有**公共类成员必须有类型。
- `from __future__ import annotations` 可选——Python 3.12+ 推迟求值已经默认足够，但若用到 `Annotated`+pydantic 时注意。
- pyright 使用 `strict` 模式：
  ```toml
  [tool.pyright]
  typeCheckingMode = "strict"
  reportMissingTypeStubs = "warning"
  ```

### 5.2 现代写法（Python 3.12+）

```python
# PEP 695 泛型语法（好）
def first[T](items: list[T]) -> T | None:
    return items[0] if items else None

# 类型别名
type ChunkId = str
type EntityId = str
type Vector = list[float]

# TypedDict 描述结构化字典
from typing import TypedDict
class EvidenceRecord(TypedDict):
    chunk_id: ChunkId
    score: float
    source: str

# Protocol 描述结构化类型（duck typing）
from typing import Protocol
class SupportsEmbed(Protocol):
    async def embed(self, texts: list[str]) -> list[Vector]: ...
```

### 5.3 禁止

- `Any` 除非注释说明为何不可避免（并加 `# type: ignore[...]` 精确抑制）。
- `Dict[str, Any]` 作为函数入参——用 TypedDict 或 Pydantic。
- `*args, **kwargs` 透传而不注释——至少写 `*args: object, **kwargs: object`。

### 5.4 异常与返回

- 不用返回 `None` 表达失败；要么抛异常，要么用 `Result` 风格（见 §8）。
- 异步函数返回类型明确写 `Coroutine` 或直接 `async def` 自动推导。

---

## 6. 不可变性与数据建模

### 6.1 原则

**能不改就不改**。修改一个对象请返回新对象。

```python
# 错
chunk.text = normalize(chunk.text)

# 对
chunk = chunk.model_copy(update={"text": normalize(chunk.text)})
```

### 6.2 数据类选择


| 场景                     | 选型                                    |
| ---------------------- | ------------------------------------- |
| 领域模型（跨边界传递、需要校验、需要序列化） | **Pydantic v2**                       |
| 内部值对象（无校验需求，追求性能）      | `@dataclass(frozen=True, slots=True)` |
| 不可变枚举                  | `enum.StrEnum` / `enum.IntEnum`       |
| 明确的值对象（ID 类）           | `NewType` / `type` 语句                 |


### 6.3 Pydantic 规范

```python
from pydantic import BaseModel, ConfigDict, Field

class Chunk(BaseModel):
    model_config = ConfigDict(
        frozen=True,          # 不可变
        extra="forbid",       # 禁止意外字段
        str_strip_whitespace=True,
    )

    library_id: str = Field(min_length=1)   # 数据分区键，见 §6.5
    chunk_id: str = Field(min_length=1)
    doc_id: str
    text: str
    page: int | None = None
    kind: Literal["text", "formula", "table", "caption"] = "text"
```

**硬要求**：

- 领域模型默认 `frozen=True`；只有明确可变对象才放开。
- `extra="forbid"`，防止错误拼写字段。
- 所有外部输入（API 请求体、文件反序列化）必须先经 Pydantic 校验。

### 6.4 集合不可变

- 公共接口返回 `Sequence[T]` / `Mapping[K, V]` 而非 `list` / `dict`，避免调用方修改。
- 常量集合用 `tuple` / `frozenset`。

### 6.5 数据分区与 Library

**Library（资料库）是数据的分区键，不是架构层级。**
系统支持横向扩展为多个 Library（一个领域 = 一个 Library），每个 Library 是一片完全独立的资料宇宙；用户在查询时显式指定 Library。Library 的存在**不增加任何包**、**不改变依赖方向**、**不引入新的层**。

**心智模型**：

> 系统不知道有几个 Library；系统只知道每条数据有 `library_id`，所有读写都按它过滤/路由。

**数据建模硬规矩**：

1. **`Library` 模型**：在 `packages/core/models.py` 定义，仅含元数据（id / 名字 / 描述 / 创建时间）。

   ```python
   class Library(BaseModel):
       model_config = ConfigDict(frozen=True, extra="forbid")
       library_id: str = Field(pattern=r"^[a-z][a-z0-9-]{2,30}$")  # slug
       name: str
       description: str | None = None
       created_at: datetime
   ```

2. **所有跨 Library 的领域模型必须带 `library_id`**：`Document` / `Chunk` / `Entity` / `Triple` / `RetrievedEvidence` / `Citation` / `RetrievalTrace` / 评测样本等，第一字段都是 `library_id: str`。

3. **唯一性约束按 `(library_id, *)`**：例如 `chunk_id` 在单个 Library 内唯一即可，不要求全局唯一。

4. **跨 Library 引用禁止**：一个 Library 中的 Triple 引用的 chunk_id 必须来自同一 Library。任何跨界引用都视为数据错误。

5. **Library 不进入 Protocol 层级**：不新增 `packages/library/`；Library 的 CRUD 是各存储适配器的薄薄一层（见 §12.5）。

**为什么不开新 package**：Library 是数据维度的命名空间，不是行为维度的模块。开包 = 给数据分区赋予虚假的架构地位，会诱导后续给 Library 写"业务逻辑"，从而污染分层。

---

## 7. 模块设计与接口（Protocol）

### 7.1 接口即契约

每个 package 对外有一个 `protocols.py`，定义所有对外行为。

```python
# packages/indexing/protocols.py
from typing import Protocol, runtime_checkable
from packages.core.models import Chunk, Entity, Triple

@runtime_checkable
class VectorIndex(Protocol):
    async def upsert(
        self,
        library_id: str,                      # 所有读写都显式带 library scope
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None: ...

    async def search(
        self,
        library_id: str,
        vector: list[float],
        k: int,
        *,
        filter: dict[str, object] | None = None,
    ) -> list[tuple[Chunk, float]]: ...

    async def init_library(self, library_id: str) -> None: ...   # 创建物理分区
    async def purge_library(self, library_id: str) -> None: ...  # 完全清除
```

**Protocol 设计准则**：所有跨 Library 的方法第一参数都是 `library_id`（位置参数，不可省）。`init_library` / `purge_library` 是适配器对 Library 生命周期的本地实现，由上层 CLI/API 编排调用 —— 不开 LibraryService。

### 7.2 门面（Facade）

每个 package 提供一个 `service.py`，聚合该包能力，对外暴露少量高层方法。
上层只调 `service`，不直接碰 `adapters/`。

```python
# packages/indexing/service.py
class HybridRetrievalCoordinator:
    def __init__(
        self,
        vector: VectorIndex,
        graph: GraphIndex,
        bm25: BM25Index,
        embedder: Embedder,
    ) -> None:
        self._vector = vector
        self._graph = graph
        self._bm25 = bm25
        self._embedder = embedder

    async def hybrid_search(
        self,
        query: str,
        k: int = 10,
    ) -> list[tuple[Chunk, float]]:
        ...
```

### 7.3 依赖注入

- 使用构造器注入（constructor injection），不用全局单例。
- `apps/api/deps.py` 集中装配；测试时替换为 fake 实现。
- 禁止在业务代码里调用 `get_settings()` 全局获取配置；由上层注入所需字段。

### 7.4 门面方法的尺寸

- 门面方法编排多个 adapter 调用，本身不写业务细节。
- 若门面方法超过 50 行，抽出策略对象（Strategy Pattern）。

---

## 8. 错误处理

### 8.1 异常层次

每个 package 有自己的 `errors.py`：

```python
# packages/ingestion/errors.py
class IngestionError(Exception):
    """Base for ingestion domain."""

class ParseError(IngestionError):
    """Parsing failed for a specific document."""

class UnsupportedFormatError(ParseError):
    pass
```

- 所有业务异常必须继承该 package 的基类。
- 异常类名以 `Error` 结尾，不用 `Exception` 后缀。

### 8.2 原则

1. **在边界捕获**：HTTP handler / CLI / worker 顶层才做兜底（转 HTTP 错误、写日志）。
2. **中间层不吞**：`except Exception: pass` 严禁。
3. **重新抛出要链**：`raise NewError("...") from e`，保留原始 traceback。
4. **外部输入失败 = `ValueError` / 自定义领域异常**；系统级问题 = `RuntimeError` 派生。
5. **重试**：幂等的外部调用加 `tenacity`，但必须声明最大次数与退避策略。

### 8.3 Result 模式（可选）

性能敏感或需要组合错误时用 `returns` 库或手写：

```python
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T"); E = TypeVar("E")

@dataclass(frozen=True, slots=True)
class Ok(Generic[T]):
    value: T

@dataclass(frozen=True, slots=True)
class Err(Generic[E]):
    error: E

type Result[T, E] = Ok[T] | Err[E]
```

默认仍以异常为主，只在批处理（不希望一条失败中断整批）时用 Result。

### 8.4 日志与异常

- 捕获异常后要么抛、要么写 `logger.exception(...)`；**不要同时**。
- 异常消息对人类可读，不暴露内部路径、密钥等。

---

## 9. 异步与并发

### 9.1 默认 async

- I/O 相关代码（HTTP、DB、向量库、LLM）**一律 async**。
- CPU 密集任务（分词、Leiden 聚类）用 `asyncio.to_thread` 或 `ProcessPoolExecutor`。
- 禁止在 async 函数中调用阻塞 I/O（如 `requests.get`）。

### 9.2 取消与超时

```python
async with asyncio.timeout(30):
    result = await retriever.search(query)
```

- 每个外部调用**必须**有超时上限。
- 响应用户的接口，总超时应低于用户可感知阈值（默认 60s）。

### 9.3 并发

```python
# 固定并发的批处理
async with asyncio.TaskGroup() as tg:
    tasks = [tg.create_task(embed(batch)) for batch in batches]
# 任一失败 → 其余自动取消
```

- 优先 `TaskGroup`（Python 3.11+）而非 `gather`。
- 需要限流用 `asyncio.Semaphore`。

### 9.4 阻塞代码隔离

- CPU 密集：`await asyncio.to_thread(heavy_cpu)` 或进程池。
- 同步库调用（少数遗留 SDK）：同上。

---

## 10. 配置管理

### 10.1 单一来源

- 所有配置通过 `**pydantic-settings**` 集中定义在 `packages/core/config.py`。
- 来源优先级：`env var > .env > 默认值`。
- **禁止**在业务代码直接读 `os.environ`。

```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    neo4j_uri: str = "bolt://localhost:7687"
    embedder_model: str = "BAAI/bge-m3"
    llm_timeout_s: int = Field(default=60, ge=1, le=600)
```

### 10.2 敏感信息

- 密钥**必须**从环境变量/密钥管理器读取。
- 仓库中禁止出现真实凭证；`.env.example` 提供占位示例。
- CI 扫描：`gitleaks` 作为 pre-commit。

### 10.3 环境分层

- `.env.dev`, `.env.staging`, `.env.prod` —— 都不入库。
- `settings.env` 字段明确区分环境相关默认（如 `debug`, `log_level`）。

---

## 11. 日志与可观测性

### 11.1 结构化日志

```python
import structlog

logger = structlog.get_logger(__name__)

await logger.ainfo(
    "chunk_embedded",
    chunk_id=chunk.chunk_id,
    doc_id=chunk.doc_id,
    vector_dim=len(vec),
    duration_ms=elapsed,
)
```

- **只用结构化日志**，不要 `f"..."` 拼字符串。
- 每条日志有 `event` + 结构化字段，便于 Loki/ES 检索。
- 禁止 `print()`。

### 11.2 日志级别


| Level    | 场景                |
| -------- | ----------------- |
| DEBUG    | 局部细节（默认生产关闭）      |
| INFO     | 重要状态变更（文档入库、检索完成） |
| WARNING  | 可恢复的异常情况（命中降级路径）  |
| ERROR    | 请求失败；需要调查         |
| CRITICAL | 系统不可用（数据损坏、熔断）    |


### 11.3 OpenTelemetry

- 所有外部调用（DB、向量库、LLM）都起一个 span。
- trace_id 贯穿请求全链路；日志自动绑定 trace_id。
- LLM 调用单独走 **Langfuse**，记录 prompt/response/token/成本。

### 11.4 指标

最少暴露：

- HTTP: `http_requests_total{route, status}`, `http_duration_seconds`
- 检索: `retrieval_hits_total{source}`, `retrieval_duration_seconds`
- LLM: `llm_tokens_total{model, type}`, `llm_cost_usd_total`
- 队列: `ingest_queue_depth`, `ingest_lag_seconds`

---

## 12. 数据访问与存储

### 12.1 Repository 模式

每种存储给一个仓库接口：

```python
class DocumentRepository(Protocol):
    async def get(self, doc_id: str) -> Document | None: ...
    async def upsert(self, doc: Document) -> None: ...
    async def list_by_hash(self, content_hash: str) -> list[Document]: ...
```

- 业务层依赖接口，不直接碰 SQLAlchemy session。
- 不暴露 ORM 对象，仓库返回领域模型（Pydantic）。

### 12.2 事务边界

- 事务由 **门面 / 用例**开启，不由仓库开启。
- SQLAlchemy session 通过 DI 传入，不用模块级全局。
- 单次请求一个 session，失败回滚。

### 12.3 迁移

- Schema 变更一律通过 **Alembic**；禁止手改库结构。
- 每个迁移文件头部注释：动机、回滚步骤、潜在影响。
- 向后兼容优先：分两步上线（先增列/表，后删旧字段）。

### 12.4 向量 / 图 写入一致性

- 多存储写入使用 **outbox 模式**：业务库写事务 → outbox 表 → 异步发事件 → 各索引 upsert。
- 写失败必须可重放；每个 upsert 必须幂等（以 `(library_id, chunk_id)` / `(library_id, entity_id)` 为键）。

### 12.5 Library 物理分区策略

每个存储后端按 `library_id` **物理隔离**，不靠 query-time filter。原则：**删除一个 Library = 一条命令清干净**。

| 后端 | 隔离方式 | 命名规则 | 备注 |
|------|---------|---------|------|
| **Qdrant** | 一个 Library 一个 collection | `chunks_<library_id>` | 删 Library = `delete_collection` |
| **Neo4j** | 一个 Library 一个 composite database | `lib_<library_id>` | 4.0+ 支持；备选用 label namespace |
| **Kuzu** | 一个 Library 一个 `.kuzu` 文件 | `data/kuzu/<library_id>.kuzu` | 嵌入式天然隔离 |
| **PostgreSQL** | `library_id` 列 + 复合索引 `(library_id, *)` | 不分 schema | RLS 可选（`USING (library_id = current_setting(...))`） |
| **OpenSearch / BM25** | 一个 Library 一个 index | `bm25_<library_id>` | 删 = `DELETE /index` |
| **MinIO / S3** | prefix 隔离 | `s3://kb/<library_id>/...` | 删 = list+delete prefix |
| **Redis** | key 前缀 | `<library_id>:...` | 缓存隔离防串扰 |

**适配器实现规矩**：

1. 每个 `*Index` / `*Repository` adapter **必须**实现 `init_library(library_id)` 与 `purge_library(library_id)`。
2. `library_id` 校验放到 adapter 边界（slug 正则）；非法 ID 直接 `raise ValueError`。
3. 删除 Library 默认走"软删除元数据 + 异步 purge 数据"两步；显式 `--purge` 走同步硬删。
4. **禁止**单个查询跨 Library —— Protocol 层不接受 `library_ids: list[str]` 参数。需要"多库联合"时由上层（CLI/Task）多次调用并合并结果。

**为什么物理隔离优先**：
- 性能：每个 Library 的索引独立优化，互不影响 ANN 召回质量
- 删除：一条命令干净，不留垃圾
- 备份：可按 Library 单独导出/恢复
- 演进：未来抽服务时，自然按 Library 分片

---

## 13. API 层约定

### 13.1 路由组织

```
apps/api/
├── main.py              # FastAPI 实例装配
├── deps.py              # 依赖注入容器
├── middleware/          # 认证 / 日志 / trace
├── routes/
│   ├── qa.py
│   ├── ingest.py
│   └── admin.py
└── schemas/             # API 请求/响应 Pydantic 模型
```

- API 层的 Pydantic 模型与 `packages/*/models.py` 的领域模型**分离**。
- 用 mapper 函数转换（`to_domain` / `from_domain`）。

### 13.2 响应格式

统一信封：

```python
class ApiResponse[T](BaseModel):
    success: bool
    data: T | None = None
    error: ApiError | None = None
    meta: dict[str, object] = Field(default_factory=dict)

class ApiError(BaseModel):
    code: str                 # "INVALID_INPUT", "NOT_FOUND", ...
    message: str              # 人类可读
    details: dict[str, object] = Field(default_factory=dict)
```

### 13.3 版本化

- URL 前缀 `/v1/...`；破坏性变更走 `/v2/...`，并行至少 6 个月。
- OpenAPI schema 每次发布产出到 `docs/api/openapi-{version}.json`，作为契约。

### 13.4 错误映射

统一异常处理器：领域异常 → HTTP 状态码 + `ApiError`。禁止在 route handler 内手写 `raise HTTPException`。

### 13.5 Library Scope 约定

所有面向数据的 API 必须显式带 Library 作用域。**禁止隐式默认**（除 CLI 个人便利层）。

**RESTful 路径**：

```
POST   /v1/libraries                       # 创建 Library
GET    /v1/libraries                       # 列表
GET    /v1/libraries/{library_id}          # 详情 + 统计
DELETE /v1/libraries/{library_id}          # 软删除（保留元数据 30 天）
DELETE /v1/libraries/{library_id}?purge=1  # 硬删除（物理清除全部数据）

POST   /v1/libraries/{library_id}/ingest
POST   /v1/libraries/{library_id}/qa
POST   /v1/libraries/{library_id}/review
GET    /v1/libraries/{library_id}/entities/{entity_id}/neighborhood
GET    /v1/libraries/{library_id}/stats
```

**CLI 风格**：

- 全局 flag `--library <id>` 或环境变量 `RKB_LIBRARY=<id>`
- 个人便利：`~/.rkb/config.toml` 可设默认 Library；CLI 在 `--library` 缺省时使用默认
- API 服务**不**支持默认 Library（必须显式）

**鉴权（v1+）**：未来若引入用户/权限，鉴权策略以 Library 为最小单位（一个用户对一个 Library 有/无某权限）。但 v1 仅单用户单进程，鉴权延后。

**审计日志**：所有 Library 级写操作（ingest / purge / schema 变更）必须落审计日志，含 `(library_id, operator, action, ts, payload_hash)`。

---

## 14. LLM 与 Prompt 规范

### 14.1 Prompt 目录化

```
packages/llm/prompts/
├── qa/
│   ├── v1.jinja
│   └── v2.jinja
└── review/
    └── v1.jinja
```

- **所有 prompt 模板纳入版本控制**，不在代码里写长字符串。
- 加载器用 Jinja2；变量清单显式声明。
- 变更 prompt 视同代码变更，需 review 并跑 eval。

### 14.2 调用规范

```python
class LLMClient(Protocol):
    async def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
        timeout_s: float = 60.0,
    ) -> LLMResponse: ...
```

- 所有 LLM 调用经过 `llm` package 的 Gateway，禁止业务模块直接调 openai / anthropic SDK。
- Gateway 统一：重试、超时、观测、成本统计、模型路由。

### 14.3 结构化输出

- 优先使用 JSON schema / function calling / Pydantic model 强约束。
- 解析失败要有**一次**降级重试（含错误反馈给模型），仍失败则抛 `LLMFormatError`。

### 14.4 成本意识

- 每个 LLM 调用记录：model、input_tokens、output_tokens、估算成本。
- 高成本任务（综述、假设生成）默认需要 `dry_run=True` 支持。

---

## 15. 测试规范

### 15.1 分层与覆盖率


| 层           | 工具                      | 最低覆盖       | 允许依赖真实服务  |
| ----------- | ----------------------- | ---------- | --------- |
| Unit        | pytest                  | **>= 80%** | 否（全 mock） |
| Integration | pytest + testcontainers | 关键路径覆盖     | 是（容器）     |
| E2E         | pytest                  | 主流程覆盖      | 是         |


### 15.2 TDD 默认工作流

1. 写测试（红）
2. 最小实现（绿）
3. 重构

新功能与 bug fix **必须**先有测试。

### 15.3 测试命名

```python
def test_hybrid_search_returns_top_k_sorted_by_score() -> None: ...
def test_expand_entity_raises_when_entity_not_found() -> None: ...
```

- 用自然语言描述行为与条件，不写 `test_1`, `test_ok`。

### 15.4 结构

严格 **Arrange-Act-Assert**：

```python
def test_rrf_fusion_merges_two_ranked_lists() -> None:
    # Arrange
    list_a = [("c1", 1), ("c2", 2)]
    list_b = [("c2", 1), ("c3", 2)]

    # Act
    merged = rrf_fuse([list_a, list_b], k=60)

    # Assert
    assert merged[0][0] == "c2"
```

### 15.5 Fixtures

- 共享 fixture 放 `tests/conftest.py` 或 `tests/fixtures/`。
- 数据库、容器通过 `testcontainers` 在 session 级 fixture 启停。
- 不在测试中 mock 被测对象内部私有方法；mock 边界。

### 15.6 属性测试

对纯函数（分块、RRF、评分）鼓励用 `hypothesis` 做属性测试（例如"任何输入都返回非空结果且分数单调"）。

### 15.7 评测集

`tests/evals/` 存放领域评测集（问答对、期望引用），由 `nightly` CI 跑 Ragas 等指标，趋势入 Grafana。

---

## 16. 文档与注释

### 16.1 注释原则

- **注释解释 "为什么"，代码说明 "是什么"。**
- 能用好名字消除的注释坚决删除。
- 当代码存在反直觉约束（bug workaround、对齐外部 API 奇怪行为）时**必须**注释。

### 16.2 Docstring（Google 风格）

所有公共函数/类/模块必须有 docstring，**不写废话**：

```python
def rrf_fuse(
    ranked_lists: list[list[tuple[str, int]]],
    *,
    k: int = 60,
) -> list[tuple[str, float]]:
    """Merge multiple ranked lists with Reciprocal Rank Fusion.

    Args:
        ranked_lists: Each inner list contains (doc_id, rank) tuples,
            with rank starting at 1 for best.
        k: Smoothing constant; 60 is the Cormack et al. (2009) default.

    Returns:
        Unique (doc_id, score) tuples sorted by descending score.

    Raises:
        ValueError: If any rank is < 1 or ranked_lists is empty.
    """
```

- 省略不重要参数说明；不要把类型再抄一遍。
- 私有函数可用一行 docstring；完全 trivial 的可省略。

### 16.3 模块级 docstring

每个 `.py` 顶部：

```python
"""Leiden-based community detection and summarization.

This module turns an entity graph into hierarchical communities
(C0 → C1 → C2) and uses an LLM to generate human-readable summaries
for each community. Summaries are persisted and serve as the "global
search" index in GraphRAG-style retrieval.
"""
```

### 16.4 ADR（架构决策记录）

- 任何架构级决策（换数据库、引入新服务、调整模块边界）**必须**写 ADR。
- 位置：`docs/adr/NNNN-title.md`。
- 模板：Context / Decision / Consequences / Alternatives。
- PR 合入时附带 ADR。

### 16.5 Runbook

运维动作（重建索引、回滚数据、处理 corrupt 文档）进 `docs/runbook/`。
内容包含：症状、诊断步骤、修复命令、回退方式、后续跟进。

---

## 17. 依赖管理

### 17.1 添加原则

加依赖前回答三个问题：

1. **必要吗**：能否用 stdlib 完成？
2. **活跃吗**：最近 6 个月有提交？>= 1k stars 或有明确背书？
3. **替代吗**：有没有更轻量的等价方案？

### 17.2 分组

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.9",
    ...
]

[dependency-groups]
dev = ["ruff", "pyright", "pytest", "pytest-asyncio", ...]
test = ["testcontainers", "hypothesis", ...]
docs = ["mkdocs", "mkdocs-material", ...]
```

### 17.3 版本策略

- 关键库用 `>=X.Y`，允许小版本升级；锁在 `uv.lock`。
- 破坏性升级走 ADR。
- 定期（每月）跑 `uv sync --upgrade`，跑完整测试后合入。

### 17.4 禁用

- 废弃或不再维护的库。
- GPL / AGPL 依赖（除非项目本身是开源且相容）。

---

## 18. 版本控制与提交

### 18.1 分支

- `main`：永远可部署。
- feature branch：`feat/<scope>-<short-desc>`，一人一事一分支。
- 不直接 push 到 `main`；都走 PR。

### 18.2 Commit Message（Conventional Commits）

```
<type>(<scope>): <subject>

<body (可选，解释 why)>

<footer (可选，关联 issue)>
```


| type     | 用途       |
| -------- | -------- |
| feat     | 新功能      |
| fix      | Bug 修复   |
| refactor | 行为不变的重构  |
| perf     | 性能优化     |
| docs     | 文档       |
| test     | 测试       |
| chore    | 构建/工具/杂项 |
| ci       | CI 配置    |


示例：`feat(indexing): add RRF fusion for hybrid retrieval`

### 18.3 PR

- 单 PR 聚焦单职责；超过 400 行 diff 就应拆分。
- PR 描述模板：背景 / 变更点 / 测试计划 / 风险 / 回滚方案。
- 必须有至少 1 人审（含 AI 审查工具）+ CI 全绿。

### 18.4 发布

- 语义化版本：`MAJOR.MINOR.PATCH`。
- CHANGELOG.md 由 `git-cliff` 或手写维护。
- Tag 触发 CI 发布镜像。

---

## 19. 代码审查清单

审查前 Checklist（作者与审查人共用）：

**架构**

- [ ] 依赖方向未违反（tach 通过）
- [ ] 新模块有 protocols.py 与 service.py
- [ ] 未在上层直接 import 下层的 adapter
- [ ] 未为 Library 新建 package 或新增层级（Library 是数据，不是模块）

**代码质量**

- [ ] 所有函数有类型标注
- [ ] 函数 < 50 行；文件 < 800 行
- [ ] 无深层嵌套；用了早返回
- [ ] 错误处理明确，未吞异常
- [ ] 无硬编码值/密钥
- [ ] 数据结构默认不可变

**Library scope（数据分区）**

- [ ] 跨 Library 模型字段第一项是 `library_id`
- [ ] 数据访问/检索方法显式接受 `library_id`，不依赖隐式上下文
- [ ] 适配器实现了 `init_library` / `purge_library`
- [ ] 唯一性约束是 `(library_id, *)` 而非全局
- [ ] 无单个查询跨 Library 的逻辑（Protocol 层不接受 `library_ids: list`）

**测试**

- [ ] 覆盖率 >= 80%（关键路径 >= 95%）
- [ ] 测试名称表达行为
- [ ] 单测不依赖网络或容器
- [ ] 新增行为有对应测试

**文档**

- [ ] 公共 API 有 docstring
- [ ] 反直觉逻辑有 "why" 注释
- [ ] 架构变更配套 ADR
- [ ] README / Runbook 如有影响已更新

**可观测性**

- [ ] 关键路径有结构化日志
- [ ] 新外部调用有 OTEL span
- [ ] LLM 调用走 Gateway

**安全**

- [ ] 输入在边界被校验
- [ ] 无日志输出敏感信息
- [ ] 有鉴权/限流（若对外暴露）

---

## 20. CI/CD 红线

必须在 CI 通过的最小集合（阻塞合并）：


| 阶段   | 命令                                                        | 说明      |
| ---- | --------------------------------------------------------- | ------- |
| 安装   | `uv sync --frozen`                                        | 锁定依赖    |
| 格式   | `ruff format --check .`                                   | 未格式化直接拒 |
| Lint | `ruff check .`                                            | 违规拒     |
| 架构   | `tach check`                                              | 依赖方向    |
| 类型   | `pyright`                                                 | strict  |
| 单测   | `pytest tests/unit -x --cov=packages --cov-fail-under=80` | 覆盖率门槛   |
| 集成   | `pytest tests/integration`                                | PR 必过   |
| 安全   | `gitleaks detect`                                         | 扫泄密     |
| 依赖   | `uv pip check` + `pip-audit`                              | 漏洞扫描    |


**Nightly / 周期性**：

- E2E 完整跑
- Ragas / LitQA 评测集
- 依赖升级演练（`uv sync --upgrade`）

---

## 21. 演进与抽服务准则

本项目**现在是单体**，但结构必须随时允许抽服务。抽的时机：


| 信号                               | 动作                |
| -------------------------------- | ----------------- |
| 某 package GPU/CPU 使用长期撑满单机       | 抽该 package 为独立服务  |
| 不同 package 的迭代节奏严重不一致（每周 vs 每季度） | 抽快者为独立仓/服务        |
| 需要多租户或多部署拓扑                      | 抽 api + retrieval |
| 上游突发流量长期阻塞在线                     | 抽 ingestion       |
| 团队增加到 > 2 个方向并行开发                | 按模块抽              |


抽服务步骤（模板化）：

1. 在该 package 新增 `protocols.py` 的 **远程实现**（gRPC/HTTP client）。
2. 将 `adapters/` 与 `service.py` 迁至新仓或新目录 `services/<name>/`。
3. 原单体保留 client adapter；其余代码零改动。
4. 部署新服务；灰度切流。
5. 下线旧的 in-process 实现。

因本文件的模块化约束到位，一次抽服务的工作量通常控制在 **1–3 天**。

---

## 附录 A — `pyproject.toml` 参考模板

```toml
[project]
name = "rag-kg-copilot"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.9",
    "pydantic-settings>=2.5",
    "structlog>=24.4",
    "httpx>=0.27",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "typer>=0.12",
    "uvicorn>=0.32",
    "arq>=0.26",
    "opentelemetry-api>=1.27",
    "opentelemetry-sdk>=1.27",
]

[dependency-groups]
dev = [
    "ruff>=0.8",
    "pyright>=1.1.385",
    "tach>=0.20",
    "pre-commit>=4.0",
]
test = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "pytest-cov>=5.0",
    "testcontainers>=4.8",
    "hypothesis>=6.115",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E", "F", "I", "N", "UP", "B", "A", "C4", "PT",
    "RET", "SIM", "TCH", "PTH", "PL", "RUF",
]
ignore = ["PLR0913"]  # 参数数量由人工把关

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["PLR2004", "S101"]  # 允许魔法值与 assert

[tool.pyright]
include = ["apps", "packages"]
typeCheckingMode = "strict"
reportMissingTypeStubs = "warning"
reportUnknownMemberType = "none"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.coverage.run]
source = ["packages"]
branch = true
```

---

## 附录 B — `tach.yml` 参考

```yaml
modules:
  - path: packages.core
    depends_on: []
  - path: packages.eventbus
    depends_on: [packages.core]
  - path: packages.embedding
    depends_on: [packages.core, packages.eventbus]
  - path: packages.llm
    depends_on: [packages.core, packages.eventbus]
  - path: packages.ingestion
    depends_on: [packages.core, packages.eventbus]
  - path: packages.structuring
    depends_on: [packages.core, packages.eventbus, packages.llm]
  - path: packages.indexing
    depends_on:
      [packages.core, packages.eventbus, packages.embedding]
  - path: packages.retrieval
    depends_on:
      [packages.core, packages.indexing, packages.llm, packages.embedding]
  - path: packages.orchestration
    depends_on: [packages.core, packages.retrieval, packages.llm]
  - path: apps.api
    depends_on: [packages.orchestration, packages.ingestion]
  - path: apps.worker
    depends_on: [packages.ingestion, packages.structuring, packages.indexing]
  - path: apps.cli
    depends_on: [packages.orchestration, packages.ingestion, packages.indexing]

exclude:
  - tests
  - scripts
```

---

## 最后

本文件是**活文档**。任何规则落地后发现"阻碍超过收益"，在 ADR 中记录修订理由并更新此文件。但**原则轴**（依赖方向、不可变、接口先于实现、类型严格、测试先行）是红线，修订需慎重。

> 代码会被读的次数远多于被写的次数。把今天的 5 分钟额外规范，换成未来半年的 5 小时省心，是划算的。

&nbsp;