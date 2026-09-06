---
name: img-share
license: MIT
github: https://github.com/shenmituzi/img-share
description:
  截图浏览器，或在聊天里把本地图片以"内嵌缩略图 + 点击看原图全屏 + 手机/其他设备可见"的方式返回给用户。
  触发场景：用户要"截图某网页/页面并贴进聊天框"、"把图片显示在聊天里且手机也能看、能点开放大"、
  "把工作区 img/ 的图通过公网隧道变成可点大图的聊天内嵌图"。
metadata:
  author: dsh agent
  version: "2.1.0"
---

# img-share Skill

把**浏览器截图**或**本地图片**变成聊天框内的**可点大图**（缩略图+点击看原图），并且**手机/其他设备也能访问**。

## whenToUse（何时触发）

- 用户要"打开某个网站/页面**截图**给我"；
- 把某张图**贴到聊天框**，且希望"手机也能看、能点开放大看细节"；
- 想把工作区 img/ 的图经公网隧道做成**可点大图的聊天内嵌图**。

> 只分享"已有本地图片"时不需要 web-access；只在本机看时可跳过隧道。

## 依赖

| 依赖 | 用途 | 获取 | 缺了替代 |
|---|---|---|---|
| web-access skill | 截图（CDP 驱动浏览器） | 安装到 ~/.dsh/skills/（"+waUrl+"） | 无截图能力则回退"上传已有图/让用户拖入" |
| python3 | 起本地图库服务 | 系统自带 | 无 |
| cloudflared | 公网隧道（手机可达） | 官方安装；或设环境变量 CLOUDFLARED=/路径/cloudflared | 不装则仅本机/局域网可看 |
| ffmpeg（可选） | 多图拼网格 | 系统安装 | 只嵌单图，不做网格 |

## 执行步骤

1. **截图**（如需）：用 web-access skill，`/screenshot` 把目标页渲染成 PNG；或直接用已有图。
   ```bash
   curl -s "http://localhost:3456/screenshot?target=<ID>&file=/tmp/x.png"
   ```
2. **存图**：放到当前工作区 `img/`（文件名用 ASCII/可 URL 编码，如 `flow_1.png`）：
   ```bash
   mkdir -p <工作区>/img && cp /tmp/x.png <工作区>/img/flow_1.png
   ```
   多图拼网格（可选）：`bash <skill>/scripts/montage.sh <工作区>/img/grid.png 图1 图2 …`
3. **自举服务**（起图库+公网隧道，输出 PUBLIC_BASE；跨平台、带重试、状态复用、图库仅回环）：
   ```bash
   bash <skill>/scripts/setup.sh "<工作区>/img"
   ```
   记下 `PUBLIC_BASE`（形如 `https://xxx.trycloudflare.com`）。重复调用会复用同一隧道（幂等）。`scripts/check.sh` 可复核。
4. **回复里内嵌**（缩略图=原图 URL，点击开原图全屏）：
   ```markdown
   [![描述](https://<PUBLIC_BASE>/<文件名>)](https://<PUBLIC_BASE>/<文件名>)
   ```
   告知用户：聊天框显示缩略图，点击开原图放大；手机用同一公网地址也可访问。**已验证**：DSH 聊天框可正常渲染公网 markdown 图片（缩略图+点击）。

## 失败处理（Agent 要兜底）

- **缺依赖**：setup.sh 会报"缺少 python3/cloudflared"，按提示安装或设 CLOUDFLARED；截图缺 web-access 则回退"让用户传图/拖入"。
- **图库端口被占**：setup.sh 自动换新空闲端口（python 绑定探测），无需人工。
- **隧道域名取不到**（网络慢/连不上 Cloudflare 边缘）：setup.sh 轮询 45s 重试；仍失败则告知用户"网络无法建隧道"，回退为**仅本机/局域网可看**（提示用本机地址）。
- **域名漂移**：cloudflared 快捷隧道重启即换域名，旧内嵌 URL 失效。长期稳定用**命名隧道/固定域名**；每次重新自举后更新回复里的 URL。

## 安全（务必向用户说明）

- 图库仅绑定 **127.0.0.1**（局域网不能直连），但**公网隧道 URL 无鉴权**——谁拿到 URL 都能看/下载该目录所有文件。
- **别放敏感图**；要限制可加鉴权（如隧道 token/随机路径），或改短时隧道用完即撤。
- 建议：只对**确定要分享**的图自举服务，用完停掉。

## 边界

- **进程要常驻**：图库 + cloudflared 都要在，否则图 404/502（setup.sh 用 setsid/nohup 脱离会话；Windows 需处理进程常驻）。
- **工作区不同**：不同会话工作区不同，图应落到对应工作区的 img/，并把该目录传给 setup.sh。
- **路径**：Windows 路径（如 E:\\docFlow\\img）在 WSL 里会被 setup.sh 自动转成 /mnt/…（用 wslpath）；脚本需保持 LF 换行。