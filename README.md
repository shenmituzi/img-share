# img-share

把**浏览器截图**或**本地图片**以"**聊天内嵌缩略图 + 点击看原图全屏 + 手机/其他设备可见**"的方式返回给 **DeepSeek Harness（DSH）** 对话。

> 这是一个 **DSH Skill**。安装后，当你对 agent 说"打开 XX 网站截图给我 / 把这张图贴出来、手机也要能看"，agent 会自动完成：截图 → 存图 → 起公网隧道 → 在回复里内嵌可点大图的图片。

## ✨ 功能

- 🖼 截图浏览器（依赖 **web-access** skill，CDP 驱动真实 Chrome）
- 🌐 本地图片经公网隧道可达 → **手机/其他设备也能看**
- 🔍 聊天框内嵌缩略图，**点击看原图全屏**
- 🚀 一行脚本自举：自动起图库服务 + 起 cloudflared 公网隧道（自动选空闲端口，幂等）

## 📦 安装（Skill）

把本仓库的 `img-share/` 目录放入 `~/.dsh/skills/`，或通过 Skill Center / git 安装。之后需求匹配时 agent 会自动加载 `img-share` 与 `web-access`。

## 🚀 使用

用户说"截图 XX 页面并贴进聊天框 / 手机可见 / 可点大图"时，agent 按 `SKILL.md` 执行：

1. `web-access` 截图 → 存到工作区 `img/`
2. `bash scripts/setup.sh <工作区>/img`（起图库 + 公网隧道，输出 `PUBLIC_BASE`）
3. 回复里内嵌 `[![描述](BASE/文件) ](BASE/文件)`

## 🧩 依赖

- **web-access** skill（截图，CDP 驱动浏览器）
- **python3**（图库服务）、**cloudflared**（公网隧道）；可选 **ffmpeg**（多图拼网格）

## 📄 脚本

- `scripts/setup.sh <图片目录>`：自举——起图库（自动选空闲端口）+ 起 cloudflared 公网隧道，输出 `PUBLIC_BASE`；幂等。
- `scripts/check.sh`：复核并打印当前 `PUBLIC_BASE`。

## 🏷 GitHub Topics（建议给仓库打的标签）

```
deepseek-harness
dsh
dsh-skill
deepseek
deepseek-ai
skill
agent-skills
ai-agents
screenshot
web-automation
browser-automation
cloudflare-tunnel
tunnel
chat-images
```

用 `gh` 添加（或 GitHub 页面 → Settings/About → Topics）：
```bash
gh repo edit <OWNER>/img-share --add-topic deepseek-harness --add-topic dsh --add-topic dsh-skill --add-topic deepseek --add-topic skill --add-topic agent-skills --add-topic screenshot --add-topic web-automation --add-topic cloudflare-tunnel
```

## ⚠️ 注意

- **公网无鉴权**：图库走公开隧道，别放敏感图。
- **隧道域名会变**：cloudflared 快捷隧道重启换域名，旧图 URL 失效；长期用**命名隧道/固定域名**。
- **进程要常驻**：图库 + 隧道需在；建议开机自启（systemd 用户服务）。
- 发布前请把 `SKILL.md` 的 `github:` 字段改为你的真实仓库地址。
