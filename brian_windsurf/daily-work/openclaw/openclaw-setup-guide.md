# OpenClaw 安装、升级与 Discord 集成指南（Windows 11）

> 记录时间：2026-02-15（更新）
> 环境：Windows 11 + Git Bash + Clash for Windows + npm 全局安装
> OpenClaw 版本：>= 2026.2.13

---

## 一、Gateway 启动 / 停止 / 重启

OpenClaw 的核心进程是 **Gateway**，负责所有频道连接、Agent 执行和控制面板。

> **注意**：`openclaw start` 命令**不存在**，所有启动操作都通过 `openclaw gateway` 子命令完成。

### 1.1 前台模式（推荐调试时使用）

```bash
# 前台启动，日志直接输出到终端，Ctrl+C 停止
openclaw gateway

# 带详细日志（推荐，能看到 Discord 连接等细节）
openclaw gateway --verbose

# 强制启动（忽略端口占用，杀掉旧进程）
openclaw gateway --force
```

### 1.2 服务模式（后台运行）

```bash
# 安装为 Windows 计划任务服务（首次需要）
openclaw gateway install

# 启动服务（已安装后使用，无输出到终端）
openclaw gateway start

# 停止服务
openclaw gateway stop

# 重启服务（等同于 stop + start，用于应用配置变更）
openclaw gateway restart

# 卸载服务
openclaw gateway uninstall
```

> Windows 上 `gateway install` 会创建名为 `OpenClaw Gateway (main)` 的计划任务。
> 如果 `gateway install` 失败（权限问题），可以一直用前台模式 `openclaw gateway --verbose`。

### 1.3 强制停止（进程卡死时）

```bash
# 杀掉所有 node 进程（会影响其他 Node 程序）
taskkill //IM node.exe //F

# 或者按 PID 精确杀
taskkill //PID <进程号> //F
```

---

## 二、常用诊断命令

```bash
# 查看版本
openclaw --version

# 系统整体状态（Gateway + 频道 + Agent）
openclaw status

# Gateway 服务状态（运行状态、端口、配置路径、RPC 连通性）
openclaw gateway status
openclaw gateway status --deep    # 包含健康探测

# 频道状态（Discord/Telegram 等连接情况）
openclaw channels status
openclaw channels status --probe  # 带网络探测

# 健康检查 + 自动修复（配置迁移、安全审计、服务配置修复）
openclaw doctor
openclaw doctor --fix             # 自动移除无效配置项

# 实时日志流
openclaw logs --follow

# 安全审计
openclaw security audit
openclaw security audit --deep
```

---

## 三、配置管理命令

```bash
# 查看当前配置
openclaw config get

# 设置配置项
openclaw config set <key> <value>

# 删除配置项
openclaw config unset <key>

# 交互式重新配置
openclaw configure

# 重新运行初始化向导
openclaw onboard
```

---

## 四、频道和配对命令

```bash
# 列出所有频道
openclaw channels list

# 查看配对请求
openclaw pairing list discord

# 批准 Discord 配对
openclaw pairing approve discord <配对码>
```

---

## 五、升级 OpenClaw

### 5.1 推荐方式（npm 全局安装）

```bash
# 1. 先停掉 Gateway
openclaw gateway stop

# 2. 杀掉所有 node 进程（释放文件锁，避免 EPERM 错误）
taskkill //IM node.exe //F

# 3. 删除旧的 openclaw 包（解决 EPERM 残留问题）
rm -rf "/c/Users/hh/AppData/Roaming/npm/node_modules/openclaw"

# 4. 重新安装最新版（--ignore-scripts 跳过 node-llama-cpp 的 postinstall 崩溃）
npm i -g openclaw@latest --ignore-scripts

# 5. 验证 + 健康检查
openclaw --version
openclaw doctor
```

### 5.2 `openclaw update` 命令

如果是 git checkout 安装的，可以直接用：

```bash
openclaw update
```

npm 全局安装的会提示 `not-git-install`，需要用上面的 npm 方式升级。

---

## 六、集成 Discord

### 6.1 前置准备

1. 访问 [Discord Developer Portal](https://discord.com/developers/applications)
2. 创建 Application → 进入 Bot 页面
3. 开启 **Privileged Intents**：
   - **Message Content Intent**（必需）
   - **Server Members Intent**（如需白名单功能）
4. 复制 **Bot Token**（不是 Client ID）
5. 通过 **OAuth2 URL Generator** 生成邀请链接，将 Bot 邀请至服务器：
   - SCOPES 勾选 `bot`
   - BOT PERMISSIONS 按需勾选（测试阶段可勾 `Administrator`）

### 6.2 配置 openclaw.json

编辑 `~/.openclaw/openclaw.json`，在 `channels` 中添加 discord 配置：

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "proxy": "http://127.0.0.1:7890",
      "token": "你的Bot Token",
      "allowBots": true,
      "guilds": {
        "你的GuildID": {
          "requireMention": true,
          "channels": {
            "频道ID": {
              "allow": true
            }
          }
        }
      },
      "dm": {
        "enabled": true,
        "policy": "allowlist"
      }
    }
  }
}
```

**关键字段说明**：

- **proxy**：（国内必需）指向 Clash 本地 HTTP 代理端口，让 Discord WebSocket 流量走代理
- **token**：Bot Token，在 Developer Portal → Bot 页面复制
- **guilds**：配置允许的服务器和频道（`requireMention: true` 表示需要 @Bot 才响应）
- **dm.policy**：`allowlist` 表示私信需要配对

### 6.3 邀请 Bot 到服务器

邀请 URL 格式：

```
https://discord.com/oauth2/authorize?client_id=你的APPLICATION_ID&permissions=8&scope=bot
```

在浏览器打开 → 选择服务器 → 授权。

### 6.4 配对（如需要）

Bot 会在 Discord 里发送配对码，然后在终端执行：

```bash
openclaw pairing approve discord <配对码>
```

---

## 七、解决网络问题（国内环境）

### 7.1 问题现象

```
[discord] [default] channel exited: Failed to resolve Discord application id
```

**根本原因**：国内无法直连 Discord API 和 WebSocket Gateway。

### 7.2 验证网络连通性

```bash
# 通过 Clash 代理测试
curl --proxy http://127.0.0.1:7890 -H "Authorization: Bot 你的BotToken" https://discord.com/api/v10/users/@me
```

- 返回 JSON（`{"id":..., "username":...}`）→ 代理通，Token 有效
- 超时 / connection reset → 代理不通或节点有问题

### 7.3 正确解决方案：`channels.discord.proxy`（推荐，>= 2026.2.13）

在 `~/.openclaw/openclaw.json` 的 `channels.discord` 中添加 `proxy` 字段：

```json
"discord": {
  "enabled": true,
  "proxy": "http://127.0.0.1:7890"
}
```

这会让 OpenClaw 的 Discord 模块内部（包括 REST API 和 WebSocket）都通过 Clash 代理连接。

**同时在 `~/.bashrc` 中设置**：

```bash
export NODE_TLS_REJECT_UNAUTHORIZED=0
```

> **重要**：`HTTP_PROXY` / `HTTPS_PROXY` 环境变量对 OpenClaw 的 Discord 模块无效（Node.js 内部 WebSocket 不读这些变量）。不要依赖环境变量，必须用 `channels.discord.proxy` 配置。

> **重要**：`channels.discord.proxy` 在 OpenClaw `2026.2.12` 及更早版本中不被支持，会报 `Unrecognized key`。必须升级到 `>= 2026.2.13`。

### 7.4 Clash for Windows 配置建议

在 Clash 配置文件的 `rules` 中添加 Discord 域名规则，确保走代理：

```yaml
- DOMAIN-SUFFIX,discord.com,你的代理节点名
- DOMAIN-SUFFIX,discord.gg,你的代理节点名
- DOMAIN-SUFFIX,discordapp.com,你的代理节点名
- DOMAIN-SUFFIX,discordapp.net,你的代理节点名
- DOMAIN-SUFFIX,discord.media,你的代理节点名
```

### 7.5 不推荐的方案（踩坑记录）

| 方案 | 问题 |
|------|------|
| `HTTP_PROXY`/`HTTPS_PROXY` 环境变量 | Node.js WebSocket 不读这些变量，Discord 模块无效 |
| Clash TUN 模式 | 会导致 SSL 证书错误（SNI mismatch），且可能路由到错误服务器 |
| `applicationId` 手动配置 | 在当前版本中是 `Unrecognized key` |

---

## 八、日常启动流程

每次使用 OpenClaw + Discord 的完整启动步骤：

```bash
# 1. 确保 Clash for Windows 正在运行（System Proxy 开启，选好代理节点）

# 2. 启动 Gateway（前台模式）
openclaw gateway --verbose

# 3. 成功标志：日志中出现
# [discord] gateway proxy enabled
# [discord] logged in to discord as <你的bot id>
# discord gateway: WebSocket connection opened
```

> 前提：`~/.bashrc` 中已设置 `export NODE_TLS_REJECT_UNAUTHORIZED=0`，
> `~/.openclaw/openclaw.json` 中已配置 `channels.discord.proxy`。

### 8.1 在 Discord 中使用

- 在已配置的服务器频道中 **@brianbot** 发送消息，Bot 会回复
- 如果 `requireMention: true`，必须 @提及 Bot 才会触发响应
- 首次 DM 需要配对：`openclaw pairing approve discord <配对码>`

---

## 九、常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `error: unknown command 'start'` | 命令不存在 | 用 `openclaw gateway start` |
| `Failed to resolve Discord application id` | 网络不通 Discord API | 在 `openclaw.json` 中配置 `channels.discord.proxy` |
| `EPERM: operation not permitted` (npm 升级时) | 文件被锁 | 先 `taskkill //IM node.exe //F`，再 `rm -rf` 旧包 |
| `node-llama-cpp postinstall` 崩溃 | Vulkan 预编译不兼容 | 用 `--ignore-scripts` 安装 |
| `schannel: SNI or certificate check failed` | TUN 模式 SSL 拦截 | 不用 TUN，改用 `channels.discord.proxy` |
| `Unrecognized key: "proxy"` | OpenClaw 版本过旧 | 升级到 >= 2026.2.13 |
| `ERR_TLS_CERT_ALTNAME_INVALID` (Facebook 证书) | 代理节点 DNS 污染 | 换一个干净的代理节点 |
| `gateway token missing` (WebSocket 1008) | 浏览器未带 token 访问 | 用启动日志中带 `?token=` 的 URL 打开控制台 |
