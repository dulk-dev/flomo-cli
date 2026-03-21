# Flomo CLI 架构设计

> 参考小红书 CLI 架构，结合 Flomo API 特点和 Agent 调用场景设计。
> 本设计结论基于 [`docs/flomo-api-analysis.md`](./flomo-api-analysis.md)（2026-03-16 逆向分析版本）。

---

## 一、小红书 CLI 架构优点分析

### 值得借鉴的设计

| 设计点 | 具体做法 | 借鉴理由 |
|--------|---------|---------|
| **分层解耦** | `commands/` → `client.py` → `signing.py` → `cookies.py`，每层只做一件事 | 改签名不影响命令，改命令不影响传输 |
| **Mixin 拆分端点** | `client_mixins.py` 按业务分 6 个 Mixin，client 本体只做传输 | 端点多时不会让 client 变成上千行巨文件 |
| **`_common.py` 命令公共层** | `handle_command()` 统一处理：认证 → 执行 → 格式化输出/错误处理 | 每个命令只写业务逻辑，不重复写 try/catch 和输出格式 |
| **`--json`/`--yaml` 结构化输出** | `structured_output_options` 装饰器 + `maybe_print_structured()` | Agent 调用时加 `--json` 即得结构化数据，人类用默认彩色表格 |
| **语义化异常 + 错误码映射** | 每种失败场景一个 Exception 类，`error_codes.py` 映射为稳定字符串 | Agent 可靠地判断错误类型，不靠解析人类消息 |
| **formatter 三文件拆分** | `formatter.py`(门面) → `formatter_renderers.py`(渲染) + `formatter_utils.py`(工具) | 渲染逻辑和工具函数分离，各自职责清晰 |
| **常量集中管理** | `constants.py` 统一管理 Host、UA、版本号、配置路径 | 魔法字符串零散布满意味着难维护 |
| **Context 传递认证** | Click ctx.obj 传递 cookie_source，命令函数不感知认证细节 | 命令层干净，认证策略可在一处切换 |

### 不需要照搬的部分

| 设计点 | 小红书的做法 | Flomo 不需要的原因 |
|--------|------------|-----------------|
| 复杂签名层 | 独立的 `signing.py` + 第三方库 `xhshow` | Flomo 签名只是 MD5，内联到 client 即可 |
| 浏览器 Cookie 提取 | `browser-cookie3` + 多浏览器并发探测 + Camoufox | Flomo 用账号密码登录，直接拿 Bearer Token |
| xsec_token 缓存体系 | 多级 token 缓存 + HTML 正则提取 + 失效回滚 | Flomo 无此机制 |
| 防反爬机制 | Gaussian 抖动、验证码退避、IP 封禁处理 | Flomo 无明显反爬，保留基本限速即可 |
| 请求头仿真 | 大量 sec-* 头模拟真实浏览器 | Flomo 只需 Authorization + 基础 headers |

---

## 二、Flomo CLI 架构设计

### 目录结构

```
flomo-cli/
├── pyproject.toml              # 项目配置、依赖、CLI 入口
├── flomo_cli/
│   ├── __init__.py             # 版本号
│   ├── __main__.py             # python -m flomo_cli 入口
│   ├── cli.py                  # Click 命令组入口
│   ├── commands/               # 命令层（按业务分文件）
│   │   ├── __init__.py
│   │   ├── _common.py          # 命令公共逻辑（认证、输出格式、错误处理）
│   │   ├── auth.py             # login / logout / status / whoami
│   │   ├── memo.py             # list / get / new / edit / delete / search / related
│   │   └── tag.py              # tag rename
│   ├── client.py               # API 客户端（传输层 + 签名 + 重试）
│   ├── auth.py                 # 认证管理（Token 获取、缓存、刷新）
│   ├── constants.py            # 常量（Host、API key、secret、配置路径）
│   ├── exceptions.py           # 语义化异常类
│   ├── error_codes.py          # 异常 → 稳定错误码字符串映射
│   ├── formatter.py            # 输出格式化门面（re-export）
│   ├── formatter_renderers.py  # Rich 渲染函数（彩色表格、卡片式输出）
│   └── formatter_utils.py      # 输出工具（JSON/YAML/错误格式化）
└── tests/
    └── ...
```

### 与小红书 CLI 的对比

| 模块 | 小红书 CLI | Flomo CLI | 变化原因 |
|------|-----------|-----------|---------|
| 命令分组 | 6 个文件（auth/reading/interactions/creator/social/notifications） | **2 个文件**（auth + memo） | Flomo 功能集中在 memo 操作上 |
| 签名层 | 独立 `signing.py` + `creator_signing.py` | **内联到 `client.py`** | MD5 签名仅 10 行代码，不值得独立模块 |
| 认证层 | `cookies.py`（浏览器提取 + QR 登录 + 缓存） | **`auth.py`**（账密登录 + Token 缓存） | 认证机制完全不同 |
| Mixin | `client_mixins.py`（6 个 Mixin） | **不用 Mixin** | Flomo 端点少（~10个），全放 client 也不到 200 行 |
| 格式化 | formatter 三文件 | **同样三文件** | 这个拆分方式很好，直接复用 |
| 错误码映射 | `error_codes.py`（异常→字符串） | **保留** | Agent 消费 JSON 错误时必须有稳定码 |
| 公共命令层 | `_common.py`（handle_command 模式） | **直接复用** | 最值得借鉴的设计，消除命令层重复代码 |

---

## 三、各模块职责

### `cli.py` — 入口层

- Click group 定义，全局选项：`--verbose`、`--json`、`--version`
- 注册所有子命令
- 不含业务逻辑

### `commands/auth.py` — 认证命令

| 命令 | 用途 |
|------|------|
| `flomo login` | 账密登录，获取并缓存 Bearer Token |
| `flomo logout` | 清除本地 Token |
| `flomo status` | 显示当前登录状态（是否有效、用户名、PRO 过期时间） |

### `commands/memo.py` — 笔记命令

| 命令 | 用途 | 对应 API |
|------|------|---------|
| `flomo list` | 列出最近笔记 | `GET /memo/updated/` |
| `flomo get <slug>` | 查看单条笔记 | `GET /memo/{slug}` |
| `flomo new "内容"` | 创建笔记 | `PUT /memo` |
| `flomo edit <slug> "新内容"` | 更新笔记 | `PUT /memo/{slug}` |
| `flomo delete <slug>` | 删除笔记 | `DELETE /memo/{slug}` |
| `flomo search "关键词"` | 搜索笔记（实时拉取全量 + 内存过滤） | `GET /memo/updated/`（分页遍历全量） |
| `flomo related <slug>` | 查看相关笔记 | `GET /memo/{slug}/recommended` |
| `flomo tags` | 查看标签树 | `GET /tag/tree` |

### `commands/tag.py` — 标签管理命令

| 命令 | 用途 | 对应 API |
|------|------|---------|
| `flomo tag rename <old> <new>` | 重命名标签（服务端原子操作） | `POST /tag/rename` |

### `commands/_common.py` — 命令公共层

核心函数（借鉴小红书 CLI 的 `handle_command` 模式）：

```python
def handle_command(ctx, *, action, render, as_json):
    """统一流程：认证 → 执行 action → 格式化输出/错误处理"""
    try:
        client = get_client(ctx)
        data = action(client)
        if as_json:
            print_json(data)
        elif render:
            render(data)
        return data
    except FlomoApiError as exc:
        exit_for_error(exc, as_json=as_json)
```

每个命令只需写：

```python
@click.command()
@click.argument("slug")
@output_options
@click.pass_context
def get(ctx, slug, as_json):
    """查看单条笔记"""
    handle_command(
        ctx,
        action=lambda client: client.get_memo(slug),
        render=render_memo,
        as_json=as_json,
    )
```

### `client.py` — API 客户端

职责：
- 签名参数拼装（MD5）
- HTTP 请求发送（httpx）
- 响应 code 检查 + 异常映射
- 基本限速（简单 sleep，不需要 Gaussian 抖动）
- 重试逻辑（指数退避，最多 3 次）

暴露的方法：

```python
class FlomoClient:
    def get_me(self) -> dict
    def get_memo(self, slug: str) -> dict
    def list_memos(self, limit=200, latest_updated_at=0, latest_slug="") -> list[dict]
    def create_memo(self, content: str, **kwargs) -> dict
    def update_memo(self, slug: str, content: str, **kwargs) -> dict
    def delete_memo(self, slug: str) -> dict
    def get_related_memos(self, slug: str) -> list[dict]
    def get_tag_tree(self) -> dict
    def rename_tag(self, old_tag: str, new_tag: str) -> dict
    def login(self, email: str, password: str) -> dict
```

### `auth.py` — 认证管理

```
Token 获取优先级（高 → 低）：
  --token 参数 > FLOMO_TOKEN 环境变量 > ~/.flomo-cli/token.json 缓存 > 提示用户执行 flomo login

  1. CLI 参数 --token（最高优先，适合 Agent 临时注入）
  2. 环境变量 FLOMO_TOKEN（CI/Agent 非交互场景）
  3. 本地缓存 ~/.flomo-cli/token.json（权限 0o600，首次 login 后写入）
  4. 全部缺失 → NotAuthenticatedError，提示 flomo login
```

### `exceptions.py` — 语义化异常

```python
class FlomoApiError(Exception): ...            # 基础异常
class NotAuthenticatedError(FlomoApiError): ... # Token 无效/过期（code=-10）
class NotFoundError(FlomoApiError): ...        # 笔记不存在（404）
class ValidationError(FlomoApiError): ...      # 参数校验失败
```

### `error_codes.py` — 异常 → 错误码映射

将异常类映射为稳定的字符串错误码，Agent 可靠判断失败类型，不依赖解析错误文案：

```python
def error_code_for_exception(exc: Exception) -> str:
    if isinstance(exc, NotAuthenticatedError):
        return "not_authenticated"
    if isinstance(exc, NotFoundError):
        return "not_found"
    if isinstance(exc, ValidationError):
        return "validation_error"
    if isinstance(exc, FlomoApiError):
        return "api_error"
    return "unknown_error"
```

JSON 错误输出统一使用此映射：
```json
{ "ok": false, "error": "not_authenticated", "message": "Token 已过期，请重新登录: flomo login" }
```

### `constants.py` — 常量

```python
API_HOST = "https://flomoapp.com/api/v1"
API_KEY = "flomo_web"
APP_VERSION = "4.0"
PLATFORM = "web"
SIGN_SECRET = "dbbc3dd73364b4084c3a69346e0ce2b2"
CONFIG_DIR = ".flomo-cli"
TOKEN_FILE = "token.json"
```

---

## 四、数据流

### 标准查询路径（list / get / related）

```
用户/Agent
    │  flomo list --json
    ▼
cli.py → commands/memo.py → commands/_common.py
    │  auth.py: --token | FLOMO_TOKEN | token.json | login
    │  action(client) → client.list_memos()
    ▼
client.py: _sign_params() → _request() → _handle_response()
    ▼
Flomo API GET /memo/updated/
```

### 搜索路径（search）

Flomo 无服务端搜索 API，搜索通过**实时分页拉取全量 + 内存过滤**实现：

```
flomo search "关键词"
    ▼
commands/memo.py (search 命令)
    │  循环调用 client.list_memos(latest_slug=cursor) 直到 has_more=false
    │  在内存中对 content_text 做关键词匹配
    ▼
输出过滤结果
```

> 注：Flomo 笔记量通常在千条级别，全量拉取耗时约 3-5 次 API 请求，可接受。

### 认证路径（login）

```
flomo login
    ▼
commands/auth.py → client.login(email, password)
    ▼
POST /user/login_by_email → 返回 access_token
    ▼
auth.py: 写入 ~/.flomo-cli/token.json（chmod 0o600）
```

---

## 五、输出格式设计

### 默认模式（人类友好）

```
$ flomo list

  #  时间                 标签                内容摘要
  1  2026-03-16 19:30     -                   我发现如果心里不用去琢磨记录的时候要打什么...
  2  2026-03-16 19:28     -                   最近还发现自己一个毛病，就是在推进Agent化...
  3  2026-03-16 19:05     #awake              最近这两天，我在看得到他们出的一款录音卡...

共 822 条笔记，显示最近 20 条
```

### JSON 模式（Agent 友好）

```
$ flomo list --json

{
  "ok": true,
  "data": [
    {
      "slug": "MjI2MzM0MzYx",
      "content": "我发现如果心里不用去琢磨...",
      "content_text": "纯文本版本（去除HTML标签）",
      "tags": [],
      "created_at": "2026-03-16 19:30:09",
      "updated_at": "2026-03-16 19:30:17",
      "has_files": true
    }
  ],
  "total": 822,
  "has_more": true
}
```

### 错误输出

```
$ flomo list --json
{
  "ok": false,
  "error": "not_authenticated",
  "message": "Token 已过期，请重新登录: flomo login"
}
```

---

## 六、技术选型

| 模块 | 选型 | 理由 |
|------|------|------|
| CLI 框架 | Click | 声明式、group/command 模式成熟 |
| HTTP 客户端 | httpx | 同步模式，API 简洁 |
| 终端输出 | Rich | 表格、颜色、Markdown 渲染 |
| 构建后端 | hatchling | 轻量，与 uv 配合好 |
| 包管理 | uv + pyproject.toml | 零环境残留 |
| Python 版本 | >= 3.10 | match/case + 类型注解 |

---

## 七、实现顺序

| 阶段 | 内容 | 交付物 |
|------|------|--------|
| 1 | 项目骨架 + constants + exceptions + error_codes | 可运行的 `flomo --version` |
| 2 | client.py（签名 + 请求 + 响应处理） | 可跑通 API 调用的基础层 |
| 3 | auth.py + commands/auth.py | `flomo login` / `flomo status`，支持 `--token` 与 `FLOMO_TOKEN` |
| 4 | commands/memo.py — 查询类 | `flomo list` / `flomo get` / `flomo search` / `flomo related` |
| 5 | commands/memo.py — 写入类 | `flomo new` / `flomo edit` / `flomo delete` |
| 6 | formatter 输出美化 | Rich 表格渲染 + `--json` 结构化输出 |
| 7 | tags 命令 | `flomo tags` |
