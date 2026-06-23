<img width="2400" height="600" alt="hero-b" src="https://github.com/user-attachments/assets/4005eb1b-539d-4d35-9683-3a61ec9d9301" />

# Sea Traces Python SDK

[![MIT License](https://img.shields.io/badge/License-MIT-red.svg?style=flat-square)](https://opensource.org/licenses/MIT)

## Installation

```
pip install git+https://github.com/SeaArt-Infra/sea-traces-sdk-py.git
```

## 适用版本

支持以下配置的 SDK 版本可使用本文档中的方式：

- 环境变量：`SEA_TEAM_KEY`、`SEA_TRACES_BASE_URL`
- 构造参数：`api_key`、`base_url`

这两个参数是必填项。没有配置时，SDK 不能正常初始化，也不会上报 trace、span、score、prompt 等数据。

## 推荐配置

生产和测试环境都必须显式配置 `SEA_TRACES_BASE_URL`。不要只配置 Team Key，因为同一个 Team Key 可能同时用于不同环境，SDK 需要根据 Sea Traces 服务地址解析项目凭证并确定最终上报地址。

```bash
export SEA_TEAM_KEY="sea-team-key"
export SEA_TRACES_BASE_URL="https://your-sea-traces.example.com"
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

上面的代码会从环境变量读取 `SEA_TEAM_KEY` 和 `SEA_TRACES_BASE_URL`。SDK 初始化时会解析一次项目凭证，后续调用继续走 SDK 原有上报链路。

## 显式传参

如果配置来自配置中心或运行时上下文，可以在构造函数中传入：

```python
from sea_traces import SeaTraces

client = SeaTraces(
    api_key="sea-team-key",
    base_url="https://your-sea-traces.example.com",
)
```

显式传参和环境变量等价，且显式传参优先级更高。

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

SDK 按以下顺序选择 Sea Traces 配置：

1. 显式传入 `api_key`、`base_url`
2. 环境变量 `SEA_TEAM_KEY`、`SEA_TRACES_BASE_URL`

## 缓存和并发

SDK 不会每次上报都查询 resolver。凭证只会在 SDK 初始化阶段解析，并且有进程内缓存。

缓存 key 为：

```text
(team_key, credentials_url)
```

同一进程内多个客户端并发使用相同 Team Key 和 resolver 地址时，SDK 会合并并发请求，只有第一个调用实际访问 resolver，其他调用等待同一个结果。

## 错误处理

常见错误和处理方式：


| 错误                       | 原因                    | 处理                                                 |
| ------------------------ | --------------------- | -------------------------------------------------- |
| `SEA_TEAM_KEY` 缺失        | 未配置 Team Key          | 设置 `SEA_TEAM_KEY` 或显式传 `api_key`                   |
| `SEA_TRACES_BASE_URL` 缺失 | 未指定 Sea Traces 服务地址   | 设置 `SEA_TRACES_BASE_URL` 或显式传 `base_url`           |
| resolver 返回非 2xx         | 凭证查询接口不可达或服务异常        | 检查 `SEA_TRACES_BASE_URL`、网络和 Sea Traces 服务状态       |
| `status` 不是 `ACTIVE`     | Team Key 未启用或映射不可用    | 检查 Team Key 和项目凭证状态                                |
| 查询不到 trace               | 数据未 flush 或服务地址指向错误环境 | 调用 `flush()`/`shutdown()`，确认 `SEA_TRACES_BASE_URL` |


日志和异常信息会对 Team Key 做脱敏处理，不会输出完整 Team Key、`publicKey` 或 `secretKey`。

## 从旧配置迁移

旧方式通常需要直接配置 public key 和 secret key。迁移后只需要配置：

```bash
export SEA_TEAM_KEY="sea-team-key"
export SEA_TRACES_BASE_URL="https://your-sea-traces.example.com"
```

业务代码建议改为使用 `sea_traces` 入口：

```python
from sea_traces import SeaTraces

client = SeaTraces()
```

如果代码里原来显式传入底层项目凭证，可以改为：

```python
client = SeaTraces(
    api_key="sea-team-key",
    base_url="https://your-sea-traces.example.com",
)
```

## 安全建议

- 不要把 `SEA_TEAM_KEY` 提交到 Git。
- 不要在日志里打印完整 Team Key、`publicKey` 或 `secretKey`。
- 测试环境和生产环境都显式配置 `SEA_TRACES_BASE_URL`。
- 容器或函数计算环境中，在启动时注入环境变量，避免在代码中硬编码。
