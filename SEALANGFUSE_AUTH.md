# Sealangfuse API Key 使用指南

本文档说明如何在 Python SDK 中使用 `sa-xxx` 形式的 Sealangfuse API Key 上报数据。用户不需要再传 `LANGFUSE_PUBLIC_KEY` 和 `LANGFUSE_SECRET_KEY`，SDK 会在初始化时根据 `sa key` 和 `base_url` 自动解析出 Langfuse 项目凭证。

## 适用版本

支持以下配置的 SDK 版本可使用本文档中的方式：

- 环境变量：`SEALANGFUSE_API_KEY`、`LANGFUSE_BASE_URL`
- 构造参数：`api_key`、`base_url`
- 可选 resolver 覆盖：`SEALANGFUSE_CREDENTIALS_URL`

旧的 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL` 仍然兼容。

## 推荐配置

生产和测试环境都必须显式传入 `LANGFUSE_BASE_URL`。不要只传 `sa key`，因为同一个 `sa key` 可能在测试环境和生产环境中相同，SDK 需要根据 `base_url` 判断要向哪个 Sealangfuse 服务解析凭证并上报数据。

```bash
export SEALANGFUSE_API_KEY="sa-xxx"
export LANGFUSE_BASE_URL="https://sealangfuse-web.example.com"
```

如果部署环境的凭证查询接口不是默认路径，可以额外指定：

```bash
export SEALANGFUSE_CREDENTIALS_URL="https://sealangfuse-web.example.com/api/public/sea-project-api-credentials"
```

默认情况下 SDK 会请求：

```text
GET {LANGFUSE_BASE_URL}/api/public/sea-project-api-credentials?key={SEALANGFUSE_API_KEY}
```

## 快速开始

```python
from langfuse import Langfuse

langfuse = Langfuse()

with langfuse.start_as_current_observation(name="python-sdk-demo") as span:
    span.update(
        input={"prompt": "ping"},
        output={"answer": "pong"},
        metadata={"source": "sealangfuse-auth-demo"},
    )

langfuse.flush()
langfuse.shutdown()
```

上面的代码会从环境变量读取 `SEALANGFUSE_API_KEY` 和 `LANGFUSE_BASE_URL`。SDK 初始化时会解析一次凭证，后续 trace、span、score、prompt 等 API 调用继续走原有 Langfuse 上报链路。

## 显式传参

如果不想依赖环境变量，可以在构造函数中传入：

```python
from langfuse import Langfuse

langfuse = Langfuse(
    api_key="sa-xxx",
    base_url="https://sealangfuse-web.example.com",
)
```

这种方式适合配置中心或多租户服务在运行时动态注入配置。

## 创建 trace、observation 和 score

```python
from langfuse import Langfuse

langfuse = Langfuse()

with langfuse.start_as_current_observation(
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

langfuse.flush()
langfuse.shutdown()
```

## 与装饰器一起使用

`@observe` 会使用当前全局 Langfuse 客户端。只要环境变量已配置，就不需要在业务函数里处理 public key 或 secret key。

```python
from langfuse import observe


@observe(name="answer-question")
def answer_question(question: str) -> str:
    return "pong"


answer_question("ping")
```

## 配置优先级

SDK 按以下顺序选择认证方式：

1. 显式传入 `public_key`、`secret_key`、`base_url`
2. 环境变量 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL`
3. 显式传入 `api_key`、`base_url`
4. 环境变量 `SEALANGFUSE_API_KEY`、`LANGFUSE_BASE_URL`

只要 public key 和 secret key 已经存在，SDK 不会调用 Sealangfuse 凭证查询接口。

## SDK 内部流程

初始化时 SDK 会执行以下步骤：

1. 读取 `api_key` 或 `SEALANGFUSE_API_KEY`
2. 读取 `base_url` 或 `LANGFUSE_BASE_URL`
3. 拼出默认 resolver 地址，或使用 `SEALANGFUSE_CREDENTIALS_URL`
4. 请求 resolver 获取 `publicKey`、`secretKey`、`baseUrl`、`status`
5. 校验 `status == "ACTIVE"`，并要求 `publicKey`、`secretKey`、`baseUrl` 非空
6. 使用解析出的 `publicKey` 和 `secretKey` 初始化原有 Langfuse API client 和 OTEL exporter
7. 最终上报地址仍使用用户传入的 `base_url`

resolver 返回的 `baseUrl` 只用于校验，不会覆盖用户传入的 `base_url`。

## 缓存和并发

SDK 不会每次上报都查询 resolver。凭证只会在 SDK 初始化阶段解析，并且有进程内缓存。

缓存 key 为：

```text
(sa_key, credentials_url)
```

同一进程内多个客户端并发使用相同 `sa key` 和 resolver 地址时，SDK 会合并并发请求，只有第一个调用实际访问 resolver，其他调用等待同一个结果。

## 错误处理

常见错误和处理方式：

| 错误                       | 原因                                  | 处理                                                  |
| -------------------------- | ------------------------------------- | ----------------------------------------------------- |
| `SEALANGFUSE_API_KEY` 缺失 | 未配置 sa key                         | 设置 `SEALANGFUSE_API_KEY` 或显式传 `api_key`         |
| `LANGFUSE_BASE_URL` 缺失   | 使用 sa key 时没有指定环境            | 设置 `LANGFUSE_BASE_URL` 或显式传 `base_url`          |
| resolver 返回非 2xx        | 凭证查询接口不可达或服务异常          | 检查 `LANGFUSE_BASE_URL`、网络和 Sealangfuse 服务状态 |
| `status` 不是 `ACTIVE`     | sa key 未启用或映射不可用             | 检查 Sealangfuse 项目凭证状态                         |
| 查询不到 trace             | 数据未 flush 或 base URL 指向错误环境 | 调用 `flush()`/`shutdown()`，确认 `LANGFUSE_BASE_URL` |

日志和异常信息会对 `sa key` 做脱敏处理，不会输出完整 `sa key` 或 `secretKey`。

## 从旧配置迁移

旧方式：

```bash
export LANGFUSE_PUBLIC_KEY="pk-lf-xxx"
export LANGFUSE_SECRET_KEY="sk-lf-xxx"
export LANGFUSE_BASE_URL="https://sealangfuse-web.example.com"
```

新方式：

```bash
export SEALANGFUSE_API_KEY="sa-xxx"
export LANGFUSE_BASE_URL="https://sealangfuse-web.example.com"
```

业务代码通常不需要修改。如果代码里显式传了 `public_key` 和 `secret_key`，可以改为：

```python
langfuse = Langfuse(
    api_key="sa-xxx",
    base_url="https://sealangfuse-web.example.com",
)
```

## 安全建议

- 不要把 `SEALANGFUSE_API_KEY` 提交到 Git。
- 不要在日志里打印完整 `sa key`、`publicKey`、`secretKey`。
- 测试环境和生产环境都显式配置 `LANGFUSE_BASE_URL`。
- 容器或函数计算环境中，在启动时注入环境变量，避免在代码中硬编码。
