# flomo-cli

通过逆向 Flomo Web API 实现的命令行工具，同时面向**人类**和 **AI Agent** 两种使用场景。

- 人类使用：Rich 彩色表格输出，交互式确认
- Agent 使用：`--json` 结构化输出 + 稳定错误码，管道模式自动切换 JSON

## 安装

需要 Python >= 3.10，推荐使用 [uv](https://github.com/astral-sh/uv)：

```bash
# 克隆项目
git clone <repo-url> && cd flomo-cli

# 安装（uv 会自动创建虚拟环境）
uv sync

# 验证
uv run flomo --version
```

或通过 pip：

```bash
pip install -e .
flomo --version
```

## 认证

### 交互式登录

```bash
flomo login
# 输入账号（邮箱/手机号）和密码
# Token 自动保存到 ~/.flomo-cli/token.json（权限 0600）
```

也可以非交互式传参：

```bash
flomo login --email your-phone-or-email --password yourpassword
```

### 环境变量（CI / Agent 场景）

```bash
export FLOMO_TOKEN="your-access-token"
flomo list --json
```

### CLI 参数注入

```bash
flomo --token "your-access-token" list --json
```

### 优先级

```
--token 参数 > FLOMO_TOKEN 环境变量 > ~/.flomo-cli/token.json > 提示 flomo login
```

## 命令一览

### 认证

| 命令 | 说明 |
|------|------|
| `flomo login` | 账密登录，缓存 Token |
| `flomo logout` | 清除本地 Token |
| `flomo status` | 查看登录状态和用户信息 |

### 笔记操作

| 命令 | 说明 |
|------|------|
| `flomo list [--limit N] [--sort newest/oldest]` | 列出笔记（默认 20 条，新→旧） |
| `flomo get <slug>` | 查看单条笔记详情 |
| `flomo new "内容" [-f file.txt]` | 创建笔记（支持参数、文件、stdin） |
| `flomo edit <slug> "新内容"` | 更新笔记 |
| `flomo delete <slug> [-y]` | 删除笔记（软删除，`-y` 跳过确认） |
| `flomo search "关键词" [--tag TAG]` | 全文搜索（本地过滤） |
| `flomo related <slug>` | 查看语义相关笔记 |
| `flomo tags` | 查看标签列表 |
| `flomo review` | 每日回顾（今日推荐的历史笔记） |

所有命令均支持 `--json` 标志输出结构化 JSON。

## 使用示例

### 列出笔记

```bash
# 默认新→旧
$ flomo list --limit 3

  #  时间              标签            内容
  1  2026-03-17 10:30  #AI编程技巧     Playwright做E2E自动化测试…
  2  2026-03-17 09:22  #生活观察家     昨天找老爸要一个不常用的手机号…
  3  2026-03-17 09:08  -               关联自：…

# 旧→新
$ flomo list --limit 3 --sort oldest
```

### 创建笔记

标签通过内容中的 `#标签名` 语法自动提取。支持三种输入方式：

```bash
# 1. 直接传参
$ flomo new "今天完成了 CLI 工具的开发 #开发/flomo-cli"
✓ 笔记已创建（slug: MjI2MzcyMjgw）
ℹ 自动提取标签：#开发/flomo-cli

# 2. 从文件读取
$ flomo new -f notes/today.md

# 3. 从 stdin 管道
$ echo "来自管道的笔记 #inbox" | flomo new
$ cat meeting-notes.md | flomo new
```

### 搜索笔记

```bash
$ flomo search "认知觉醒"

搜索结果 "认知觉醒" 共 50 条
  #  时间              标签            内容
  1  2024-02-21 08:46  #读书/认知觉醒  人的学习分为被动学习和主动学习两个层次…
  ...
```

### 查看相关笔记

```bash
$ flomo related MTA1MDM5OTgy

  #  相似度  时间              标签            内容
  1   90.1%  2025-02-06 10:14  #读书           你必须动用已有的知识去解释新知识…
  2   85.3%  2025-01-15 09:22  #awake          学习不是收集，是连接…
  ...
```

### 每日回顾

```bash
$ flomo review

每日回顾 共 12 条

╭─ #1 MTA3NzAzNTYx ──────────────────────────╮
│ 2024-03-08 18:15:23  #读书/认知驱动          │
│                                              │
│ 那些看起来有强大自控能力的人并非真的比常人更…  │
╰──────────────────────────────────────────────╯
...
```

## Agent 集成

### JSON 输出格式

所有命令加 `--json` 即得标准 envelope 格式：

```json
{
  "ok": true,
  "data": [ ... ],
  "has_more": true
}
```

错误时：

```json
{
  "ok": false,
  "error": "not_authenticated",
  "message": "Token 已过期，请重新登录: flomo login"
}
```

### 管道自动检测

当 stdout 不是 TTY（被管道或重定向捕获）时，自动输出 JSON，无需手动加 `--json`：

```bash
# 以下两者等价
flomo list --json | jq '.data[0].slug'
flomo list | jq '.data[0].slug'
```

### 错误码

Agent 通过 `error` 字段判断失败类型，不依赖解析 `message` 文本：

| 错误码 | 含义 |
|--------|------|
| `not_authenticated` | Token 缺失或过期 |
| `not_found` | 笔记不存在 |
| `validation_error` | 参数校验失败 |
| `api_error` | 其他 API 错误 |
| `unknown_error` | 未预期的异常 |

### Agent 典型工作流

```bash
# 1. 通过环境变量注入 Token
export FLOMO_TOKEN="..."

# 2. 搜索笔记
flomo search "项目进展" --json

# 3. 读取某条笔记详情
flomo get MTA1MDM5OTgy --json

# 4. 查看相关笔记，发现关联
flomo related MTA1MDM5OTgy --json

# 5. 查看每日回顾
flomo review --json

# 6. 创建新笔记
flomo new "基于以上分析，得出结论：... #insight" --json
```

## 项目结构

```
flomo_cli/
├── cli.py                 # Click 命令组入口
├── client.py              # API 客户端（签名、HTTP 传输、重试）
├── auth.py                # Token 管理（优先级链、缓存读写）
├── constants.py           # 常量（API Host、签名密钥、配置路径）
├── exceptions.py          # 语义化异常
├── error_codes.py         # 异常 → 稳定错误码映射
├── formatter.py           # 格式化门面（re-export）
├── formatter_utils.py     # 输出工具（JSON envelope、HTML 剥离）
├── formatter_renderers.py # Rich 渲染函数
└── commands/
    ├── _common.py         # handle_command 模式（统一认证/输出/错误）
    ├── auth.py            # login / logout / status
    └── memo.py            # list / get / new / edit / delete / search / related / tags / review
```

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest -v

# 运行单个测试文件
uv run pytest tests/test_signing.py -v
```

### 测试覆盖

| 测试文件 | 覆盖范围 |
|---------|---------|
| `test_signing.py` | MD5 签名算法（含已知正确值对照） |
| `test_auth.py` | Token 优先级链、缓存读写、HTML 剥离、错误码映射 |
| `test_client.py` | HTTP 响应处理、全部 client 方法（mock） |
| `test_commands.py` | CLI 命令端到端（CliRunner + mock） |

## 技术细节

- **签名算法**：参数按 key 排序拼接 → 追加固定 secret → MD5
- **认证方式**：Bearer Token（通过账密登录获取）
- **搜索实现**：Flomo 无服务端搜索 API，本工具通过分页拉取全量笔记后在内存中做关键词匹配
- **分页机制**：cursor-based（`latest_slug` + `latest_updated_at`），每页最多 200 条

## 许可证

MIT
