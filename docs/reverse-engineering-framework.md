# 逆向工程框架经验总结

> 基于对小红书 CLI (`xiaohongshu-cli`) 的源码分析，总结出适用于「网页逆向 → CLI 工具」的通用框架经验，供 Flomo CLI 参考。

---

## 一、整体架构分层

```
cli.py（入口层）
  └── commands/*（命令层，按业务模块分文件）
        └── client.py（传输层：签名、重试、限速、响应处理）
              ├── client_mixins.py（端点层：各业务 API 的具体调用）
              ├── signing.py（签名层：请求签名算法实现）
              ├── cookies.py（认证层：Token/Cookie 获取、缓存、TTL 管理）
              ├── constants.py（常量层：Host、UA、版本号等）
              └── exceptions.py（异常层：语义化异常类定义）
```

**核心原则：每一层只做一件事，传输机制与业务逻辑严格分离。**

---

## 二、逆向手法

### 1. 识别 API 域名与签名规则差异

复杂平台往往存在多个域名，对应不同的签名规则。小红书的例子：

| 域名 | 用途 | 签名方式 |
|------|------|---------|
| `edith.xiaohongshu.com` | 主 API | `x-s`/`x-t`/`x-s-common` 复杂签名（依赖第三方库） |
| `creator.xiaohongshu.com` | 创作者 API | AES-128-CBC 自实现，相对简单 |

**Flomo 关注点：** 抓包时区分不同接口的认证头差异，确认是 Bearer Token、Session Cookie 还是其他动态签名机制。

### 2. 请求头仿真策略

完整仿造真实浏览器的请求头，重点是 `sec-*` 系列头（服务器常用来识别爬虫）：

```python
headers = {
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", ...',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "dnt": "1",
    "priority": "u=1, i",
    "origin": "https://xxx.com",
    "referer": "https://xxx.com/",
}
```

### 3. 动态参数的提取与缓存

某些 API 需要从网页 HTML 或其他接口响应中提取动态参数（如 token、source 等）：

- **多重正则提取**：针对不同页面结构写多个 pattern，依次尝试
- **本地缓存**：提取成功后写入 `~/.工具名/token_cache.json`，避免重复请求
- **TTL 管理**：缓存设置过期时间（例如 24h），过期后自动重新提取
- **失效回滚**：API 调用失败时，主动 invalidate 缓存再重试

### 4. 模拟真实会话上下文

部分操作（如搜索）在真实浏览器中并非单次请求，而是一系列请求的组合。需要复刻完整行为序列：

```
搜索行为 = onebox 预热请求 + filter 预热请求 + notes 主请求 + recommend 后置请求
```

这类"会话 ID"需要在同一搜索会话内保持一致，并做本地持久化（TTL=10min）。

---

## 三、防反爬的具体操作

### 1. 请求频率控制

```python
def _rate_limit_delay(self):
    elapsed = time.time() - self._last_request_time
    if elapsed < self._request_delay:
        # Gaussian 抖动：模拟人类操作的随机性
        jitter = max(0, random.gauss(0.3, 0.15))
        # 偶发性长暂停（5% 概率）：模拟用户阅读停顿
        if random.random() < 0.05:
            jitter += random.uniform(2.0, 5.0)
        time.sleep(self._request_delay - elapsed + jitter)
```

### 2. 验证码/封禁的分级响应

| 状态码 / 业务码 | 含义 | 处理策略 |
|----------------|------|---------|
| HTTP 461/471 | 触发验证码 | 指数退避冷却（5→10→20→30s），抬高后续请求间隔 |
| HTTP 429/500-504 | 限流/服务故障 | 指数退避重试（最多 N 次） |
| code=300012 | IP 被封 | 抛出 `IpBlockedError`，告知用户换网络 |
| code=-100 | Session 过期 | 抛出 `SessionExpiredError`，引导重新登录 |

```python
def _request_with_retry(self, method, url, **kwargs):
    for attempt in range(self._max_retries):
        resp = self._http.request(method, url, **kwargs)
        if resp.status_code in (429, 500, 502, 503, 504):
            wait = (2 ** attempt) + random.uniform(0, 1)  # 指数退避
            time.sleep(wait)
            continue
        return resp
```

### 3. 响应 Cookie 的持续同步

每次请求后把响应中的新 Cookie 合并回 session，模拟浏览器的自然行为，避免 session 漂移：

```python
def _merge_response_cookies(self, resp):
    for name, value in resp.cookies.items():
        if value:
            self.cookies[name] = value
```

---

## 四、认证管理的工程模式

```
登录策略（优先级递降）：
  1. 本地缓存 Token/Cookie（TTL=N天，文件权限 0o600）
  2. 从本机浏览器自动提取（browser-cookie3）
  3. 扫码登录 / 账密登录
  4. 全部失败 → 抛出 NoCookieError，输出友好的排查步骤
```

**安全细节：**
- 凭证文件权限设为 `0o600`（仅当前用户可读）
- 凭证文件不加入版本控制（`.gitignore`）
- 凭证存储路径统一：`~/.工具名/`

---

## 五、工程规范的通用经验

### 异常体系设计

```python
class ApiError(Exception):
    """基础异常，携带 code 和原始 response"""

class NeedVerifyError(ApiError): ...     # 需要验证码
class SessionExpiredError(ApiError): ... # Session 过期
class IpBlockedError(ApiError): ...      # IP 被封
class SignatureError(ApiError): ...      # 签名失败
class NoCookieError(ApiError): ...       # 无有效凭证
```

每种失败场景对应独立的 Exception 类，CLI 层捕获后输出不同的用户提示。

### 常量管理

```python
# constants.py — 所有魔法字符串集中管理
API_HOST = "https://api.xxx.com"
USER_AGENT = "Mozilla/5.0 ..."
CONFIG_DIR = ".工具名"
TOKEN_FILE = "token.json"
```

### 本地缓存规范

| 文件 | 内容 | 权限 | TTL |
|------|------|------|-----|
| `~/.工具名/token.json` | 认证凭证 | 0o600 | 7 天 |
| `~/.工具名/token_cache.json` | 动态参数缓存 | 0o600 | 24 小时 |
| `~/.工具名/session_cache.json` | 会话 ID 缓存 | 0o600 | 10 分钟 |

### 推荐技术栈

| 模块 | 推荐选型 | 理由 |
|------|---------|------|
| HTTP 客户端 | `httpx` | 同步/异步均支持，API 现代 |
| CLI 框架 | `click` | group+command 模式，选项声明式 |
| 终端输出 | `rich` | 表格、颜色、进度条均支持 |
| 包管理 | `uv` + `pyproject.toml` | 速度快，零环境残留 |
| 构建后端 | `hatchling` | 轻量，与 uv 配合良好 |

---

## 六、Flomo CLI 下一步计划

### MVP 功能范围

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 查询近期笔记 | 列表分页，支持分页游标 |
| P0 | 关键字搜索笔记 | 全文搜索 |
| P0 | 查询相关笔记 | 基于某条笔记查询相关 |
| P1 | 创建笔记 | 发送 memo，支持标签 |
| P1 | 更新笔记 | 编辑已有 memo |
| P1 | 删除笔记 | 删除指定 memo |

### 待确认的逆向信息

通过抓包 `https://v3.flomoapp.com` 需要确认：

- [ ] 认证方式：JWT Bearer Token？Session Cookie？还是有动态签名？
- [ ] Token 的获取方式：登录接口的请求/响应结构
- [ ] Token 的有效期（决定本地缓存 TTL）
- [ ] 笔记列表 API 的分页参数（cursor-based 还是 offset-based？）
- [ ] 搜索 API 是否存在（还是需要客户端过滤）
- [ ] 创建/更新/删除接口的请求体结构
- [ ] 是否有 CSRF Token 或其他动态请求头
