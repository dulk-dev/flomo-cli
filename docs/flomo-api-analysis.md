# Flomo API 逆向分析

> 通过浏览器抓包 + 前端 JS 源码分析，完整还原 Flomo Web API 的认证、签名、端点结构。

---

## 一、API 基础信息

| 项目 | 值 |
|------|-----|
| API 基地址 | `https://flomoapp.com/api/v1/` |
| 前端版本 | `VUE_APP_VERSION: 5.25.122` |
| 构建时间 | `20260316073543` |
| 静态资源 | `https://resource.flomoapp.com/flomo-web/` |

---

## 二、认证机制

### 认证方式：Bearer Token

Flomo 使用标准的 **Bearer Token** 认证，**不依赖复杂签名**（比小红书简单得多）。

```
Authorization: Bearer your-access-token
```

### Token 存储

登录成功后，用户信息（含 token）存储在 `localStorage` 的 `me` 键中：

```json
{
  "id": 100001,
  "name": "YourName",
  "email": "your-phone-or-email",
  "access_token": "your-access-token",
  "api_token": "your-api-token",
  "pro_type": "pro",
  "slug": "MTAwMDAxMQ",
  ...
}
```

- **`access_token`**：主认证令牌，放在 `Authorization: Bearer` 头中
- **`api_token`**：API 写入 token（用于 Flomo 的 API 写入功能，非逆向所需）

### 登录接口

```
POST /api/v1/user/login_by_email
```

请求体：
```json
{
  "email": "your-phone-or-email",
  "password": "xxx",
  "wechat_union_id": "",
  "wechat_oa_open_id": ""
}
```

响应体（成功时 `code=0`）：
```json
{
  "code": 0,
  "data": {
    "id": 100001,
    "access_token": "your-access-token",
    ...
  }
}
```

错误码：
- `code=-10`：Session 过期，需重新登录
- `code=-20`：需要验证密码
- `code=-101`：需要绑定其他账号

---

## 三、请求签名机制

### 通用查询参数

所有 API 请求都携带以下查询参数：

| 参数 | 值 | 说明 |
|------|-----|------|
| `timestamp` | Unix 秒级时间戳 | `moment().unix()` |
| `api_key` | `flomo_web` | 固定值 |
| `app_version` | `4.0` | Web 端固定为 4.0 |
| `platform` | `web` | 固定值 |
| `webp` | `1` | 浏览器支持 webp 时附加 |
| `sign` | MD5 哈希 | 动态签名 |

### sign 签名算法（从 JS 源码还原）

```python
import hashlib

SIGN_SECRET = "dbbc3dd73364b4084c3a69346e0ce2b2"

def generate_sign(params: dict) -> str:
    """
    Flomo API 签名算法：
    1. 对参数按 key 字典序排序（ksort）
    2. 拼接为 key=value& 格式的字符串
    3. 去除末尾的 &
    4. 拼接固定 secret 后缀
    5. MD5 哈希
    """
    sorted_keys = sorted(params.keys())
    parts = []
    for key in sorted_keys:
        value = params[key]
        if value is None or (value == "" and value != 0):
            continue
        if isinstance(value, list):
            value.sort()
            for item in value:
                parts.append(f"{key}[]={item}")
        else:
            parts.append(f"{key}={value}")
    
    query_string = "&".join(parts)
    sign_input = query_string + SIGN_SECRET
    return hashlib.md5(sign_input.encode()).hexdigest()
```

### 签名验证示例

以 `user/me` 请求为例：
- 参数：`timestamp=1773669997`, `api_key=flomo_web`, `app_version=4.0`, `platform=web`, `webp=1`
- 排序拼接：`api_key=flomo_web&app_version=4.0&platform=web&timestamp=1773669997&webp=1`
- 追加 secret：`api_key=flomo_web&app_version=4.0&platform=web&timestamp=1773669997&webp=1dbbc3dd73364b4084c3a69346e0ce2b2`
- MD5 结果应为：`e8749f38dfc1fcdd1582d34a0c7759f0` ✓

---

## 四、请求头结构

### 必要请求头

```python
headers = {
    "Authorization": f"Bearer {access_token}",
    "platform": "<platform-string>",      # 设备平台标识
    "device-model": "<device-model>",      # 设备型号
    "device-id": "<device-id>",            # 设备唯一 ID
}
```

### GET vs POST 参数传递

- **GET 请求**：签名参数（timestamp, api_key, sign 等）放在 URL query string 中
- **POST/PUT/PATCH 请求**：签名参数放在请求体中（data/body），query string 为空

---

## 五、已发现的 API 端点

### 认证相关

| 端点 | 方法 | 用途 |
|------|------|------|
| `/user/login_by_email` | POST | 账号密码登录 |
| `/user/me` | GET | 获取当前用户信息 |
| `/user_setting/mine` | GET | 获取用户设置 |

### 笔记（Memo）CRUD

| 端点 | 方法 | 用途 | 已验证 |
|------|------|------|--------|
| `/memo` | PUT | 创建笔记 | ✅ |
| `/memo/{slug}` | PUT | 更新笔记 | ✅ |
| `/memo/{slug}` | DELETE | 删除笔记（软删除） | ✅ |
| `/memo/{slug}` | GET | 获取单条笔记 | ✅ |
| `/memo/updated/` | GET | 分页获取笔记列表（增量同步） | ✅ |
| `/memo/latest_updated_desc` | GET | 获取最新更新排序信息 | ✅ |
| `/memo/{slug}/recommended` | GET | 获取相关笔记（带相似度评分） | ✅ |

### 笔记其他操作

| 端点 | 方法 | 用途 |
|------|------|------|
| `/memo/{slug}/pin` | POST | 置顶笔记 |
| `/memo/{slug}/unpin` | POST | 取消置顶 |
| `/memo/{slug}/restore` | POST | 恢复已删除笔记 |
| `/memo/{slug}/force_delete/` | POST | 永久删除笔记 |
| `/memo/float/list` | GET | 获取浮动笔记列表 |
| `/memo/float/update` | PUT | 更新浮动状态 |
| `/memo/recommend_ignore` | POST | 忽略推荐 |
| `/memo/insight` | GET/POST | AI 洞察 |
| `/memo/insight/history` | GET | 洞察历史 |

### 标签（Tag）相关

| 端点 | 方法 | 用途 |
|------|------|------|
| `/tag/updated/` | GET | 分页获取标签列表 |
| `/tag/tree` | GET | 获取标签树结构 |

### 其他

| 端点 | 方法 | 用途 |
|------|------|------|
| `/subscription/` | GET | 获取订阅信息 |
| `/notification/mine` | GET | 获取通知 |
| `/announcement/show/` | GET | 获取公告 |
| `/wechat_account/` | GET | 微信账号关联 |
| `/notify_setting/mine/` | GET | 通知设置 |
| `/notify_memo_progress/` | GET | 笔记进度通知 |

---

## 六、分页机制

### memo/updated/ 接口

使用 **cursor-based** 增量同步模式：

```
GET /api/v1/memo/updated/?limit=200&latest_updated_at=0&latest_slug=MjI2MzM0MzYx&tz=8:0
```

| 参数 | 说明 |
|------|------|
| `limit` | 每页数量（默认 200） |
| `latest_updated_at` | 上次同步的时间戳（首次为 0） |
| `latest_slug` | 上次同步的最后一条记录 slug（Base64 编码的 ID） |
| `tz` | 时区偏移（如 `8:0` 表示 UTC+8） |

客户端通过多次调用逐步拉取全部数据，直到返回空列表。

### tag/updated/ 接口

同样的 cursor-based 模式：

```
GET /api/v1/tag/updated/?limit=200&latest_updated_at=0&tz=8:0
```

---

## 七、响应格式

### 通用响应结构

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| code | 含义 |
|------|------|
| `0` | 成功 |
| `-10` | Session 过期 |
| `-20` | 需要验证密码 |
| 其他非零 | 业务错误 |

---

## 八、Memo 数据结构

每条笔记的完整字段：

```json
{
  "content": "<p>HTML 格式的笔记内容</p>",
  "creator_id": 100001,
  "source": "android",           // 来源: android / ios / web / wechat
  "tags": ["标签名/子标签"],      // 字符串数组（非对象）
  "pin": 0,                      // 0=普通, 1=置顶
  "created_at": "2024-02-21 08:36:29",
  "updated_at": "2024-02-21 08:46:01",
  "deleted_at": null,            // 非 null 表示已删除
  "memo_from": "human",          // human / ai
  "slug": "MTA1MDM5OTgy",       // Base64 编码的唯一标识
  "linked_count": 0,             // 关联笔记数
  "files": [                     // 附件列表
    {
      "id": 19333249,
      "type": "image",           // image / audio
      "name": "文件名",
      "path": "file/2024-02-21/xxx.jpg",
      "size": 187146,
      "url": "https://static.flomoapp.com/...",
      "thumbnail_url": "https://static.flomoapp.com/.../thumbnailwebp"
    }
  ]
}
```

注意事项：
- `content` 字段为 **HTML 格式**，CLI 展示时需要转为纯文本或 Markdown
- `tags` 是**纯字符串数组**，支持 `父标签/子标签` 的层级格式
- `slug` 是 Base64 编码的数字 ID，用于 API 中标识具体笔记
- `files` 包含图片和音频附件，带有 OSS 签名 URL

---

## 九、相关笔记 API 详情

### 请求

```
GET /api/v1/memo/{slug}/recommended?type=1&no_same_tag=...
```

| 参数 | 说明 |
|------|------|
| `slug` | 笔记的 Base64 编码 ID |
| `type` | 推荐类型（默认 1，存储在 localStorage） |
| `no_same_tag` | 是否排除同标签笔记（可选） |

### 响应

返回按相似度排序的相关笔记列表：

```json
{
  "code": 0,
  "data": [
    {
      "memo_id": 159879584,
      "similarity": "0.9005300074973709",
      "memo": {
        "content": "<p>笔记内容...</p>",
        "tags": ["标签名"],
        "slug": "MTU5ODc5NTg0",
        "created_at": "2025-02-06 10:14:51",
        "linked_memos": [],
        "backlinked_memos": [],
        "files": [...]
      }
    }
  ]
}
```

每条结果包含：
- `similarity`：相似度评分（0~1，字符串格式）
- `memo`：完整的笔记对象（含 content、tags、files 等）
- `linked_memos` / `backlinked_memos`：双向引用关系

---

## 十、写入型 API 详情（已验证）

### 创建笔记

```
PUT /api/v1/memo
```

请求体（签名参数也放在 body 中）：
```json
{
  "content": "<p>笔记内容，支持 HTML</p>",
  "source": "web",
  "tz": "8:0",
  "timestamp": "1773670557",
  "api_key": "flomo_web",
  "app_version": "4.0",
  "platform": "web",
  "webp": "1",
  "sign": "xxx"
}
```

可选参数：
- `created_at`：指定创建时间
- `memo_from`：来源标记（默认 `"human"`）
- `file_ids`：附件 ID 列表

响应（`code=0`，`message="已创建"`）：
```json
{
  "code": 0,
  "message": "已创建",
  "data": {
    "content": "<p>...</p>",
    "slug": "MjI2MzY1Mjgx",
    "tags": ["自动从内容中提取的标签"],
    "created_at": "2026-03-16 22:35:57",
    "linked_memos": []
  }
}
```

**注意：标签从 content 中自动提取（`#标签名` 格式），无需单独传参。**

### 更新笔记

```
PUT /api/v1/memo/{slug}
```

请求体：
```json
{
  "content": "<p>更新后的内容 #标签</p>",
  "source": "web",
  "tz": "8:0",
  "pin": 0,
  "timestamp": "...",
  "api_key": "flomo_web",
  "app_version": "4.0",
  "platform": "web",
  "webp": "1",
  "sign": "xxx"
}
```

可选参数：
- `created_at`：修改创建时间
- `local_updated_at`：本地更新时间
- `pin`：置顶状态（0=普通, 1=置顶）
- `file_ids`：附件 ID 列表

响应（`code=0`，`message="已修改"`）：返回完整的 memo 对象（含 files、linked_memos、backlinked_memos）。

### 删除笔记

```
DELETE /api/v1/memo/{slug}
```

签名参数通过 URL query string 传递。

响应（`code=0`，`message="已删除"`）：
```json
{ "code": 0, "message": "已删除", "data": "" }
```

### 获取单条笔记

```
GET /api/v1/memo/{slug}
```

响应：返回完整的 memo 对象（含 content、tags、files、linked_memos、backlinked_memos）。

### 其他笔记操作

| 端点 | 方法 | 用途 |
|------|------|------|
| `/memo/{slug}/pin` | POST | 置顶笔记（body: `{force: 1}`） |
| `/memo/{slug}/unpin` | POST | 取消置顶 |
| `/memo/{slug}/restore` | POST | 恢复已删除笔记 |
| `/memo/{slug}/force_delete/` | POST | 永久删除笔记 |

### 搜索笔记

**Flomo 没有服务端搜索 API。** 搜索是纯客户端行为：
1. 先通过 `memo/updated/` 增量同步全部笔记到本地 IndexedDB
2. 在客户端 JavaScript 中对 content/tags 做 filter

**对 CLI 的影响：** 需要在本地实现搜索功能，方案：
- 先全量同步笔记（`memo/updated/` 分页拉取）
- 本地缓存到文件（JSON）
- 对 content 做纯文本/正则匹配

---

## 十一、与小红书 CLI 的对比

| 维度 | 小红书 CLI | Flomo CLI |
|------|-----------|-----------|
| 认证方式 | Cookie (a1/web_session) | Bearer Token |
| 签名复杂度 | 极高（x-s/x-t/x-s-common，依赖第三方库） | **极低**（MD5 + 固定 secret） |
| 防反爬强度 | 极高（验证码、IP 封禁、浏览器指纹） | **极低**（目前未发现任何防爬措施） |
| 登录方式 | QR 码扫描 / 浏览器 Cookie 提取 | **账号密码直接登录** |
| 复杂度评估 | ★★★★★ | ★★☆☆☆ |

**结论：Flomo 的 API 逆向非常友好，认证简单、签名算法透明、无明显反爬机制。可以快速实现 CLI 工具。**
