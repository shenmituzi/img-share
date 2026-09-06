# img-share

把**浏览器截图**或**本地图片**以"**聊天内嵌缩略图 + 点击看原图全屏 + 手机/其他设备可见**"的方式返回给 **DeepSeek Harness（DSH）** 对话。

> 这是一个 **DSH Skill**（v2.1.0）。安装后对 agent 说"打开 XX 网站截图给我 / 把这张图贴出来、手机也要能看"，它会自动：截图 → 存图 → 起公网隧道 → 回复里内嵌可点大图。

## ✨ 功能

- 🖼 截图浏览器（依赖 **web-access** skill，CDP 驱动真实 Chrome）
- 🌐 本地图片经公网隧道可达 → **手机/其他设备也能看**
- 🔍 聊天框内嵌缩略图，**点击看原图全屏**（已验证 DSH 能渲染公网 markdown 图片）
- 🚀 一键自举：起图库（仅回环 127.0.0.1）+ 起 cloudflared 公网隧道（自动选空闲端口、含重试、状态复用、幂等）
- 🧩 多图拼网格脚本（`scripts/montage.sh`，需 ffmpeg）

## 📦 安装

```bash
git clone https://github.com/shenmituzi/img-share ~/.dsh/skills/img-share
chmod +x ~/.dsh/skills/img-share/scripts/*.sh
```
> 之后**新开会话**生效。也可下载 ZIP 把 `img-share/` 放进 `~/.dsh/skills/`。

### 依赖

| 依赖 | 用途 | 说明 |
|---|---|---|
| **web-access** skill | 截图 | 同样装进 `~/.dsh/skills/`（否则可回退"上传已有图"） |
| **python3** | 图库服务 | 系统自带 |
| **cloudflared** | 公网隧道 | 官方安装；可设环境变量 `CLOUDFLARED=/路径/cloudflared` |
| **ffmpeg**（可选） | 多图拼网格 | `scripts/montage.sh` 需要 |

## 🚀 使用

对 agent 说（示例）：
- "打开 example.com 截图给我，手机也要能看到，点击能放大"
- "把 img/flow_1.png 贴到聊天框，做成可点大图的"

Agent 会加载 `img-share`，并按 `SKILL.md`：web-access 截图 → 存 `img/` → `bash scripts/setup.sh <img目录>` → 回复内嵌 `[![描述](BASE/文件) ](BASE/文件)`。

脚本手工测试：`bash scripts/setup.sh <图片目录>`（输出 PUBLIC_BASE）；`bash scripts/check.sh`（复核）。

## 🧩 环境注意（跨平台）

- **Linux / macOS / WSL**：开箱可跑。
- **Windows 原生**：需在 **WSL** 里用；脚本用 `wslpath` 自动转 Windows 路径（E:\\docFlow\\img → /mnt/...）；`setsid`/管道依赖 bash，别用 Git Bash 直接跑。
- **换行**：脚本是 LF；若改用 CRLF 保存，先转回 LF（`dos2unix`）。
- **开机自启**：Linux/macOS 用 systemd/launchd；Windows 用任务计划程序。

## ⚠️ 安全与边界

- **公网无鉴权**：图库仅回环，但公网隧道 URL 无访问控制——谁拿到 URL 都能看/下载该目录所有文件。**别放敏感图**；要限制加鉴权/随机路径，或改短时隧道。
- **隧道域名会变**：cloudflared 快捷隧道重启换域名，旧内嵌 URL 失效；长期用**命名隧道/固定域名**。
- **网络前提**：隧道需要稳定连上 Cloudflare 边缘节点；网络差可能建隧道失败（setup.sh 有重试，仍失败会回退本机/局域网）。
- **进程要常驻**：图库 + 隧道需在；否则图 404/502。

## 🏷 GitHub Topics

```
deepseek-harness  dsh  dsh-skill  deepseek  deepseek-ai  skill  agent-skills  ai-agents
screenshot  web-automation  browser-automation  cloudflare-tunnel  tunnel  chat-images
```

## 📄 脚本

- `scripts/setup.sh <图片目录> [端口]`：自举（起图库[仅回环]+起隧道，自动选端口、重试取域名、状态复用；幂等）。
- `scripts/check.sh`：读状态并复核公网地址。
- `scripts/montage.sh <输出.png> 图1 [图2 …]`：多图拼网格（需 ffmpeg）。
