# agent-project-memory

Agent Project Memory 是一个面向 Codex、Claude Code、Gemini/Antigravity 等本地执行型 Agent 的项目记忆与交接目录模板。

它解决的问题是：Agent 换会话、换工具、换系统、上下文压缩或聊天记录丢失后，不知道以前做过什么、项目在哪里、问题如何解决、下一步该干什么。

## 核心思路

不要把长期项目状态只放在聊天上下文里。每个 Agent 都应读取一个固定的、可版本管理的项目记忆目录。

推荐目录：

```text
.codex/
├── AGENTS.md
└── project_memory/
    ├── INDEX.md
    ├── templates/
    │   ├── RECORD_TEMPLATE.md
    │   └── SESSION_TEMPLATE.md
    └── records/
        ├── clone-dual-system-sync/
        │   └── SUMMARY.md
        ├── tailscale-moonlight-sunshine/
        │   └── SUMMARY.md
        └── claude-code-proxy-fix/
            └── SUMMARY.md
```

## 使用方式

1. 把本仓库的 `.codex/` 目录复制到需要长期维护的 Agent 全局规则目录或项目目录。
2. 让 Agent 在开始工作前先读取 `.codex/AGENTS.md`。
3. 每完成一个非一次性问题，把结论写入 `.codex/project_memory/records/<topic>/SUMMARY.md`。
4. 更新 `.codex/project_memory/INDEX.md`，让后续 Agent 能按关键词找到对应记录。

## 适合记录什么

- 网络、代理、Tailscale、Moonlight、Sunshine、SSH、VPS 等环境问题。
- Claude Code、Codex、Gemini、Antigravity、Computer Use、MCP 等 Agent 配置问题。
- 长期项目的交接状态、验证方式、回滚方式。
- 已经踩过坑且后续可能重复遇到的问题。

## 不适合记录什么

- 密钥、密码、cookie、token、私钥。
- 完整敏感日志、私人订单数据、身份证件、联系方式。
- 只适合当前一次对话的临时推理过程。

## 当前仓库状态

这是通过 ChatGPT GitHub connector 直接提交的项目初始化版本。当前版本先提供可用的目录结构、模板、示例记录和基础校验脚本。
