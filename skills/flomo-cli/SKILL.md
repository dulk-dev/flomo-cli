---
name: flomo-cli
description: Flomo 笔记命令行工具。当需要与 Flomo 交互时使用，包括创建/编辑/删除/搜索笔记、查看标签和相关笔记、每日回顾、管理认证。触发词：flomo、笔记、memo、记录想法、写笔记、查笔记、每日回顾。
---

# flomo-cli 使用指南

通过逆向 Flomo Web API 实现的 CLI，通过 `uv run flomo` 调用。

## 认证

使用前必须先完成认证，三种方式（按优先级从高到低）：

```bash
# 方式 1：CLI 参数（最高优先级）
uv run flomo --token "ACCESS_TOKEN" list --json

# 方式 2：环境变量
export FLOMO_TOKEN="ACCESS_TOKEN"
uv run flomo list --json

# 方式 3：交互式登录（Token 缓存到 ~/.flomo-cli/token.json）
uv run flomo login --email EMAIL --password PASSWORD
```

检查认证状态：

```bash
uv run flomo status --json
```

## 命令参考

**始终加 `--json` 获取结构化输出。** 管道模式下自动输出 JSON。

### 笔记操作

```bash
# 列出笔记（默认 20 条，新→旧）
uv run flomo list --json
uv run flomo list --limit 50 --sort oldest --json

# 查看单条笔记
uv run flomo get <slug> --json

# 创建笔记（标签通过 #标签名 语法自动提取）
uv run flomo new "内容文本 #标签名" --json
uv run flomo new -f file.txt --json
echo "内容" | uv run flomo new --json

# 更新笔记
uv run flomo edit <slug> "新内容" --json

# 删除笔记（-y 跳过确认）
uv run flomo delete <slug> -y --json

# 搜索（本地全文匹配，可按标签过滤）
uv run flomo search "关键词" --json
uv run flomo search "关键词" --tag "标签名" --json

# 语义相关笔记
uv run flomo related <slug> --json

# 标签列表
uv run flomo tags --json

# 每日回顾（获取今日推荐回顾的笔记列表）
uv run flomo review --json
```

### 认证管理

```bash
uv run flomo login --email EMAIL --password PASSWORD --json
uv run flomo logout --json
uv run flomo status --json
```

## JSON 输出格式

成功：

```json
{ "ok": true, "data": [...], "has_more": true }
```

失败：

```json
{ "ok": false, "error": "错误码", "message": "描述" }
```

## 错误码

| 错误码 | 含义 | 处理方式 |
|--------|------|----------|
| `not_authenticated` | Token 缺失或过期 | 重新执行 `flomo login` 或检查 `FLOMO_TOKEN` |
| `not_found` | 笔记不存在 | 检查 slug 是否正确 |
| `validation_error` | 参数校验失败 | 检查命令参数 |
| `api_error` | API 错误 | 重试或检查网络 |
| `unknown_error` | 未预期异常 | 查看详细 message |

## 笔记数据结构

`--json` 输出的 `data` 中每条笔记包含：

```json
{
  "slug": "MjI2MzcyMjgw",
  "content": "<p>HTML 原始内容</p>",
  "content_text": "纯文本内容",
  "tags": ["标签1", "开发/子标签"],
  "created_at": "2026-03-17 10:30:00",
  "updated_at": "2026-03-17 10:30:00",
  "deleted_at": null,
  "files": [{"id": 123, "type": "image", "name": "photo.jpg", "size": 270391, "url": "https://...", "thumbnail_url": "https://..."}]
}
```

- `slug` 是笔记的唯一标识，用于 get/edit/delete/related 操作
- `tags` 支持多级标签，如 `开发/flomo-cli`
- `content` 是 HTML 格式，`content_text` 是剥离 HTML 后的纯文本
- `deleted_at` 为 null 表示正常笔记，默认已过滤软删除笔记
- `files` 包含附件完整信息（URL 可直接下载）

## 典型工作流

```bash
# 1. 查看今日回顾推荐
uv run flomo review --json

# 2. 搜索相关笔记
result=$(uv run flomo search "项目进展" --json)

# 3. 从结果中取出某条笔记的 slug，查看详情
uv run flomo get MTA1MDM5OTgy --json

# 4. 查看语义相关笔记
uv run flomo related MTA1MDM5OTgy --json

# 5. 创建新笔记
uv run flomo new "基于分析得出结论：... #insight" --json
```

## 注意事项

- 搜索通过拉取全量笔记后本地匹配实现，笔记量大时较慢
- 创建/编辑时纯文本自动包裹 `<p>` 标签转为 HTML
- 删除是软删除（移入回收站），默认已过滤软删除笔记
- list 返回 `has_more=true` 时表示还有更多，可调 `--limit` 获取更多
- review 返回的是 Flomo 推荐的今日回顾笔记，可能包含较早的历史笔记
- 所有命令需在 flomo-cli 项目根目录下通过 `uv run flomo` 执行
