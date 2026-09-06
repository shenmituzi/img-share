---
name: img-share
license: MIT
github: https://github.com/shenmituzi/img-share
description:
  截图浏览器，或在聊天里把本地图片以"内嵌缩略图 + 点击看原图全屏 + 手机/其他设备可见"的方式返回给用户。
  触发场景：用户要"截图某网页/页面并贴进聊天框"、"把图片显示在聊天里且手机也能看、能点开放大"、
  "把工作区图片经公网隧道变成可点大图的聊天内嵌图"。
metadata:
  author: dsh agent
  version: "2.2.0"
---

# img-share Skill

把**浏览器截图**或**本地图片**变成聊天框内的**可点大图**（缩略图+点击看原图），并且**手机/其他设备也能访问**。跨平台（Linux/macOS/WSL/**Windows 原生**均可用）。

## whenToUse（何时触发）

- 用户要"打开某个网站/页面**截图**给我"；
- 把某张图**贴到聊天框**，且希望"手机也能看、能点开放大看细节"；
- 想把工作区图片经公网隧道做成**可点大图的聊天内嵌图**。

## 依赖

| 依赖 | 用途 | 获取 |
|---|---|---|
| web-access skill | 截图（CDP 驱动浏览器） | 需装：https://github.com/eze-is/web-access |
| python3/python | 编排器（serve.py） | 系统自带 |
| cloudflared | 公网隧道（手机可达） | mac: `brew install cloudflared`；win: `winget install Cloudflare.cloudflared`；linux: 见其官方 README；或设 `CLOUDFLARED=/路径` |
| ffmpeg（可选） | 多图拼网格 | 系统安装（`scripts/montage.sh` 用） |

## 执行步骤

1. **截图**（如需）：用 web-access skill，`/screenshot` 渲染页面成 PNG。
   - 若 CDP/Chromium 在受限环境跑不起来（禁联网/进程崩溃），**降级到云端截图**：用 thum.io / mshots / microlink 等，带 `?wait=N&width=W`，返回后校验"非白像素占比>阈值、色簇数>N"，不是空白才可用。
2. **存图**：放到工作区（如 `img/x.png`，文件名用 ASCII/无空格）。
3. **自举分享**（**只分享这一个文件**，不开整个目录；起图库[仅回环]+公网隧道，端到端校验，输出 PUBLIC_BASE）：
   ```bash
   bash <skill>/scripts/setup.sh <img>/x.png        # Unix/WSL
   python <skill>/scripts/serve.py --share <img>/x.png   # Windows 原生
   ```
4. **回复里内嵌**（缩略图=原图 URL，点击开原图全屏）：
   ```markdown
   [![描述](https://<PUBLIC_BASE>/x.png)](https://<PUBLIC_BASE>/x.png)
   ```
   告知用户：聊天框显缩略图，点击开原图；手机用同一公网地址也可访问（已验证 DSH 能渲染公网 markdown 图片）。
5. **分享完毕→撤隧道**（避免长期公开）：
   ```bash
   bash <skill>/scripts/teardown.sh                  # 停图库+隧道+清理
   ```

## 失败处理

- **缺依赖**：serve.py 报"缺 cloudflared/python"，按提示装或设 `CLOUDFLARED`；截图缺 web-access 则走云端截图（见上）或让用户传图。
- **端口被占**：serve.py 自动选空闲端口。
- **隧道域名取不到**（网络慢/断连 Cloudflare）：serve.py 轮询重试；仍失败则告知"网络无法建隧道"，回退为**仅本机/局域网**（给本机地址）。
- **端到端校验失败**：serve.py 会 curl 真实文件名校验（200 才成功），失败即撤，避免"看似 live 实则 404"。
- **域名漂移**：快捷隧道重启换域名，旧内嵌 URL 失效；长期稳定用**命名隧道/固定域名**。

## 环境自检（Agent 先做）

开始前先探测：能否**出网**（curl 一个公网地址）、能否**spawn 浏览器进程**（CDP）。都不行 → 走**云端截图 + 提示需要更高权限**，不要直接给用户一个"看起来能但实际裂"的图。

## 安全（默认动作，非提醒）

- **只分享指定文件**：serve.py 把要分享的文件**拷进随机命名子目录**再起服务，**绝不开整个 img/** 目录（否则隧道 URL 能列出/下载该目录所有文件）。
- 图库**仅绑定 127.0.0.1**（局域网不能直连）；公网隧道 URL 无鉴权——**分享完立即 teardown**。
- 想更严：给 URL 加随机 token / 用短时隧道；**别放敏感图**。

## 优先：复用 DSH 自己的隧道（可选，推荐）

理想做法：**DSH 自己已把 GUI 开成公网/隧道**（用户手机正是通过它进这个会话），那么图片应**挂在 DSH 同一个域名**下，用户手机上打开会话自然就能加载——这才是"手机也能看到"的正解，而不是每次另开一条临时隧道。

- 若 DSH/宿主已把某路径（如 `/img/*`）暴露为静态服务（本机已通过 dsh-trust-proxy 加了 `/img/` 规则），则图片走 `https://<DSH域名>/img/x.png`，复用 DSH 隧道，跨设备、免多开隧道。
- serve.py 的**独立 cloudflared 隧道**是**可移植兜底**（任何机器都能跑）；若检测到宿主已暴露静态路径，**优先复用宿主隧道**。

## 边界

- **进程要常驻/可撤**：serve.py 记录 PID 供 teardown；DSH 会话里服务需跨会话（可用托管后台 + teardown 明确清理）。
- **文件名**：用 ASCII、无空格；脚本对文件存在做校验，中文/空格由 URL 编码处理，但建议避免。
- **工作区不同**：不同会话工作区不同，按该会话路径分享；serve.py 用系统临时目录，不依赖工作区。
