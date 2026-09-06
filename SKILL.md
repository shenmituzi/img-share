---
name: img-share
license: MIT
github: https://github.com/<OWNER>/img-share
description:
  截图浏览器，或在聊天里把本地图片以"内嵌缩略图 + 点击看原图全屏 + 手机/其他设备可见"的方式返回给用户。
  触发场景：用户要"截图某网页/页面并贴进聊天框"、"把图片显示在聊天里且手机也能看、能点开放大"、
  "把工作区 img/ 的图通过公网隧道变成可点大图的聊天内嵌图"。
metadata:
  author: dsh agent
  version: "2.0.0"
---

# img-share Skill

在 DSH 对话里：**截图浏览器 / 分享本地图片 → 聊天框内嵌缩略图 → 点击看原图全屏 → 手机/其他设备可见**。

## 依赖

- 截图：需要 **web-access** skill（CDP 驱动浏览器）。只分享已有本地图则不需要。
- 自举基础设施：**python3** + **cloudflared**（提供公网隧道）。可选 **ffmpeg**（多图拼网格）。
- 本 skill 的 `scripts/setup.sh` 会自动：起图库服务（root=图片目录，自动选空闲端口）+ 起 cloudflared 公网隧道 → 输出可内嵌的公开图片 URL。

## 完整流程（截图 → 聊天框返回）

1. **截图**（如需要）：用 **web-access** skill，`/screenshot` 把目标页面渲染成 PNG。或直接使用已有图片。
   ```bash
   curl -s "http://localhost:3456/screenshot?target=<ID>&file=/tmp/x.png"
   ```
2. **放到图片目录**：默认取当前工作区 `img/`（存为英文/可 URL 编码文件名，避免中文跨设备编码问题，如 `flow_1.png`）。
   ```bash
   mkdir -p <工作区>/img && cp /tmp/x.png <工作区>/img/flow_1.png
   ```
3. **自举服务**（起图库 + 起公网隧道，输出公开 URL；幂等，可在任意机器跑）：
   ```bash
   bash "<本skill>/scripts/setup.sh" "<工作区>/img"
   ```
   记下输出的 `PUBLIC_BASE`（形如 `https://xxx.trycloudflare.com`）。也可用 `scripts/check.sh` 复核。
4. **在回复里内嵌**（缩略图=原图 URL，点击打开原分辨率大图）：
   ```markdown
   [![描述](https://<PUBLIC_BASE>/<文件名>)](https://<PUBLIC_BASE>/<文件名>)
   ```
   告知用户：聊天框显示缩略图，点击开原图放大看细节；手机用同一公网域名打开也可访问。

## 多图拼网格（可选，需 ffmpeg）

```bash
ffmpeg -y -i a.png -i b.png -i c.png -filter_complex "[0:v]scale=640:360[a];[1:v]scale=640:360[b];[2:v]scale=640:360[c];[a][b][c]concat=n=3:v=1[o];[o]tile=1x3" -frames:v 1 out.png
```
（或 `tile=2x3` 做 2 列；更多帧依次加输入。）

## 边界与注意

- **公网无鉴权**：图库走公开隧道、无访问控制，别放敏感图；如需保护加简单鉴权或内网限制。
- **隧道域名会变**：cloudflared 快捷隧道重启即换域名，旧消息里嵌的 URL 会失效；长期稳定应改用**命名隧道/固定域名**。
- **进程要常驻**：图库 + cloudflared 都要在，否则图 404/502。`setup.sh` 用 `setsid … &` 脱离会话常驻；要**开机自启**可安排为 systemd 用户服务。
- **工作区不同**：不同会话的工作区不同，图片应落到对应工作区的 `img/`，并把该目录传给 `setup.sh`。
- **composer 内嵌为"助手消息 markdown 图"**：只能经 `[![..](url)](url)` 展示；若要把图做成"会话真实附件"，用注入 `POST /api/session.prompt`（多一条消息+触发一轮回复，谨慎使用）。