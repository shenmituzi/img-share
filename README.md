# img-share

把**浏览器截图**或**本地图片**以"**聊天内嵌缩略图 + 点击看原图全屏 + 手机/其他设备可见**"的方式返回给 **DeepSeek Harness（DSH）** 对话。**跨平台：Linux / macOS / WSL / Windows 原生**。

> DSH Skill v2.2.0。对 agent 说"打开 XX 网站截图给我 / 把这张图贴出来、手机也要能看"，它会：截图 → 存图 → 起公网隧道（**只分享该文件**）→ 回复里内嵌可点大图 → 用完可撤隧道。
![Uploading image.png…]()


## ✨ 功能

- 🖼 截图浏览器（web-access，CDP）；失败可降级**云端截图**（thum.io 等 + 非空白校验）
- 🌐 图片经公网隧道可达 → **手机/其他设备也能看**
- 🔍 聊天内嵌缩略图、**点击看原图全屏**（已验证 DSH 渲染公网 markdown 图）
- 🚀 **跨平台编排器 `scripts/serve.py`（纯 Python，Windows 原生可用）**：只分享指定文件（随机子目录）、仅回环、自动选端口、端到端校验、状态、**teardown**
- 🧩 可选 `scripts/montage.sh`（ffmpeg 拼网格）

## 📦 安装

```bash
git clone https://github.com/shenmituzi/img-share ~/.dsh/skills/img-share
chmod +x ~/.dsh/skills/img-share/scripts/*.sh
```
> 新开会话生效。也可下载 ZIP 放 `img-share/` 到 `~/.dsh/skills/`。

### 依赖

| 依赖 | 获取 |
|---|---|
| web-access skill | https://github.com/eze-is/web-access |
| python3 | 系统自带 |
| cloudflared | mac: `brew install cloudflared`；win: `winget install Cloudflare.cloudflared`；linux: 其官方 README；或设 `CLOUDFLARED` |
| ffmpeg（可选） | montage.sh 用 |

## 🚀 使用

- Linux/WSL：`bash scripts/setup.sh <img>/x.png`
- **Windows 原生**：`python scripts/serve.py --share <img>\\x.png`
- 复核：`bash scripts/check.sh`（或 `python scripts/serve.py --status`）
- **撤隧道**：`bash scripts/teardown.sh`

对 agent 说："打开 example.com 截图给我，手机也要能看到，点击能放大"。

## 🧩 跨平台

- **Linux/macOS/WSL**：`setup.sh`（转到 serve.py）。
- **Windows 原生**：直接用 `python scripts/serve.py --share …`（python + cloudflared.exe 即可，无需 bash）。
- **mac 无 setsid**：serve.py 用 python subprocess，天然跨平台（不依赖 setsid/nohup/seq）。
- 换行 LF；Git Bash 可用 python 直跑更稳。

## ⚠️ 安全与边界

- **默认只分享单文件**（随机子目录），**不开整个 img/**；图库仅 127.0.0.1；公网 URL 无鉴权 → **用完 teardown**。
- 隧道域名重启即变（需稳定用命名隧道）；隧道需稳定连 Cloudflare 边缘。
- 进程需常驻/可撤（serve.py 记录 PID）。

## 🏷 GitHub Topics

```
deepseek-harness  dsh  dsh-skill  deepseek  deepseek-ai  skill  agent-skills  ai-agents
screenshot  web-automation  browser-automation  cloudflare-tunnel  tunnel  chat-images
```

## 📄 脚本

- `serve.py`：跨平台编排器（`--share/--status/--stop`）。
- `setup.sh` / `check.sh` / `teardown.sh`：薄壳调用 serve.py。
- `montage.sh`：多图拼网格（需 ffmpeg）。
