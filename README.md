

# Sea Traces Python SDK

## Installation

```
pip install git+https://github.com/SeaArt-Infra/sea-traces-sdk-py.git
```

## 适用版本

支持以下配置的 SDK 版本可使用本文档中的方式：

- 外部用户环境变量：`SEA_TRACES_API_KEY`、`SEA_TRACES_BASE_URL`、`SEA_TRACES_PROJECT_ID`
- 构造参数：`api_key`、`base_url`、`project_id`
- 内部用户直连环境变量：`SEATRACES_PUBLIC_KEY`、`SEATRACES_SECRET_KEY`、`SEATRACES_BASE_URL`

外部用户使用 Sea Traces 三件套走网关鉴权。内部用户如果已经拿到项目公钥、秘钥和上报地址，可以直接使用 Sea Traces 直连上传模式。

## 外部用户推荐配置

生产和测试环境都必须显式配置 `SEA_TRACES_BASE_URL`。不要只配置 API Key，因为同一个 API Key 可能同时用于不同环境，SDK 需要根据 Sea Traces 服务地址解析项目凭证并确定最终上报地址。

```bash
export SEA_TRACES_API_KEY="sea-traces-api-key"
export SEA_TRACES_BASE_URL="https://your-sea-traces.example.com"
export SEA_TRACES_PROJECT_ID="your-project-id"
```

## 快速开始

```python
from sea_traces import SeaTraces

client = SeaTraces()

with client.start_as_current_observation(name="python-sdk-demo") as span:
    span.update(
        input={"prompt": "ping"},
        output={"answer": "pong"},
        metadata={"source": "sea-traces-auth-demo"},
    )

client.flush()
client.shutdown()
```

上面的代码会从环境变量读取 `SEA_TRACES_API_KEY`、`SEA_TRACES_BASE_URL` 和 `SEA_TRACES_PROJECT_ID`。SDK 初始化时会向网关 `POST {base_url}/hub/sea-traces-api-key` 解析一次项目凭证，之后用凭证返回的上报地址发送数据。

## 显式传参

如果配置来自配置中心或运行时上下文，可以在构造函数中传入：

```python
from sea_traces import SeaTraces

client = SeaTraces(
    api_key="sea-traces-api-key",
    base_url="https://your-sea-traces.example.com",
    project_id="your-project-id",
)
```

显式传参和环境变量等价，且显式传参优先级更高。

## 内部用户直连上传

内部用户如果已经拿到项目公钥、秘钥和上报地址，可以直接上传，不需要配置 Sea Traces 三件套：

```bash
export SEATRACES_PUBLIC_KEY="pk-..."
export SEATRACES_SECRET_KEY="sk-..."
export SEATRACES_BASE_URL="https://your-sea-traces-ingestion.example.com"
```

也可以显式传参：

```python
from sea_traces import SeaTraces

client = SeaTraces(
    public_key="pk-...",
    secret_key="sk-...",
    base_url="https://your-sea-traces-ingestion.example.com",
)
```

## 上报方式

SDK 有两种上报模式：每次创建独立 trace，或在同一个 trace 里追加子 observation。

### 独立 trace

每次在 `with` 块外部独立调用 `start_as_current_observation`，会各自创建新的 trace：

```python
from sea_traces import SeaTraces

client = SeaTraces()

# 第一个独立 trace
with client.start_as_current_observation(name="task-a") as span:
    span.update(input={"step": "a"}, output={"ok": True})

# 第二个独立 trace
with client.start_as_current_observation(name="task-b") as span:
    span.update(input={"step": "b"}, output={"ok": True})

client.flush()
client.shutdown()
```

### 在同一个 trace 里追加

在 `with` 块内部嵌套调用，所有子 observation 归属同一个 trace：

```python
from sea_traces import SeaTraces

client = SeaTraces()

with client.start_as_current_observation(
    name="checkout-flow",
    as_type="span",
) as span:
    span.update(input={"step": "start"})

    with span.start_as_current_observation(
        name="llm-call",
        as_type="generation",
        model="demo-model",
    ) as generation:
        generation.update(
            input=[{"role": "user", "content": "ping"}],
            output=[{"role": "assistant", "content": "pong"}],
            usage_details={
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "total_tokens": 2,
            },
        )

    span.score_trace(name="quality", value=1.0)
    span.update(output={"ok": True})

client.flush()
client.shutdown()
```

## 与装饰器一起使用

`@observe` 会使用当前全局 Sea Traces 客户端。只要环境变量已配置，就不需要在业务函数里处理底层项目凭证。

```python
from sea_traces import observe


@observe(name="answer-question")
def answer_question(question: str) -> str:
    return "pong"


answer_question("ping")
```

## 配置优先级

SDK 按以下顺序选择配置：

1. 完整的直连构造参数：`public_key`、`secret_key`、`base_url`
2. 完整的直连环境变量：`SEATRACES_PUBLIC_KEY`、`SEATRACES_SECRET_KEY`、`SEATRACES_BASE_URL`
3. 显式传入 Sea Traces 三件套：`api_key`、`base_url`、`project_id`
4. Sea Traces 环境变量：`SEA_TRACES_API_KEY`、`SEA_TRACES_BASE_URL`、`SEA_TRACES_PROJECT_ID`

## 缓存和并发

SDK 不会每次上报都查询 resolver。凭证只会在 SDK 初始化阶段解析，并且有进程内缓存。

缓存 key 为：

```text
(api_key, project_id, credentials_url)
```

同一进程内多个客户端并发使用相同 API Key、Project ID 和 resolver 地址时，SDK 会合并并发请求，只有第一个调用实际访问 resolver，其他调用等待同一个结果。

## 错误处理

常见错误和处理方式：


| 错误                         | 原因                     | 处理                                                 |
| -------------------------- | ---------------------- | -------------------------------------------------- |
| `SEA_TRACES_API_KEY` 缺失    | 未配置 Sea Traces API Key | 设置 `SEA_TRACES_API_KEY` 或显式传 `api_key`             |
| `SEA_TRACES_BASE_URL` 缺失   | 未指定 Sea Traces 服务地址    | 设置 `SEA_TRACES_BASE_URL` 或显式传 `base_url`           |
| `SEA_TRACES_PROJECT_ID` 缺失 | 未指定项目 ID               | 设置 `SEA_TRACES_PROJECT_ID` 或显式传 `project_id`       |
| resolver 返回非 2xx           | 凭证查询接口不可达或服务异常         | 检查 `SEA_TRACES_BASE_URL`、网络和 Sea Traces 服务状态       |
| 查询不到 trace                 | 数据未 flush 或服务地址指向错误环境  | 调用 `flush()`/`shutdown()`，确认 `SEA_TRACES_BASE_URL` |


日志和异常信息会对 API Key 做脱敏处理，不会输出完整 API Key、`publicKey` 或 `secretKey`。

## 从旧配置迁移

外部用户从旧方式迁移后只需要配置：

```bash
export SEA_TRACES_API_KEY="sea-traces-api-key"
export SEA_TRACES_BASE_URL="https://your-sea-traces.example.com"
export SEA_TRACES_PROJECT_ID="your-project-id"
```

业务代码建议改为使用 `sea_traces` 入口：

```python
from sea_traces import SeaTraces

client = SeaTraces()
```

如果代码里原来显式传入底层项目凭证，可以改为：

```python
client = SeaTraces(
    api_key="sea-traces-api-key",
    base_url="https://your-sea-traces.example.com",
    project_id="your-project-id",
)
```

内部用户可以使用直连配置：

```bash
export SEATRACES_PUBLIC_KEY="pk-..."
export SEATRACES_SECRET_KEY="sk-..."
export SEATRACES_BASE_URL="https://your-sea-traces-ingestion.example.com"
```

## 安全建议

- 不要把 `SEA_TRACES_API_KEY`、`SEATRACES_PUBLIC_KEY` 或 `SEATRACES_SECRET_KEY` 提交到 Git。
- 不要在日志里打印完整 API Key、`publicKey` 或 `secretKey`。
- 测试环境和生产环境都显式配置 `SEA_TRACES_BASE_URL`。
- 容器或函数计算环境中，在启动时注入环境变量，避免在代码中硬编码。

