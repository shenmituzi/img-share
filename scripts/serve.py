#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""img-share 跨平台编排器（含 Windows 原生）：只分享指定文件、端到端校验、可 teardown。

用法:
  python serve.py --share <文件> [更多文件...] [--port N]   # 起服务+隧道，输出 PUBLIC_BASE
  python serve.py --status                                  # 复核全部运行中分享实例
  python serve.py --stop [ID]                               # 停指定实例；不带 ID 则停全部
"""
import argparse
import functools
import http.server
import json
import os
import re
import secrets
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

# 运行目录与状态均按"实例"隔离：每个实例一个 <id>.json，
# 避免多实例互相覆盖状态、--stop 误停他人。
BASE_DIR_NAME = "img-share"      # <系统临时目录>/img-share：实例状态与分享根目录的父目录
INSTANCES_SUBDIR = "instances"   # 实例状态 json 所在子目录
TOKEN_BYTES = 16                 # URL 随机 token 字节数(16B=128bit 随机)，让分享路径不可枚举
GALLERY_WAIT_SEC = 24            # 图库就绪最长等待(秒)
DOMAIN_POLL = 20                 # 取隧道域名轮询次数(每次间隔 3 秒)
E2E_POLL = 20                    # 端到端校验轮询次数(每次间隔 3 秒)
HTTP_TIMEOUT = 8                 # http_ok 单次请求超时(秒)
LEGACY_STATE = "img-share.state" # 旧版单实例状态文件名(仅用于升级时回收清理)


class _NoListingHandler(http.server.SimpleHTTPRequestHandler):
    """只提供静态文件、禁止目录列表的图库处理器。

    必须禁目录列表：否则根路径会把随机 token 子目录名列出来，token 路径就失去"不可枚举"意义。
    """

    def list_directory(self, path):  # noqa: D401
        self.send_error(404, "Directory listing disabled")
        return None


def serve_gallery(port: int, root: str) -> int:
    """以子进程方式运行图库（serve.py --gallery <port> <root>）：仅绑回环、禁目录列表。

    由 run() 通过 subprocess 拉起，进程常驻直到被 teardown/stop 终止。
    """
    handler = functools.partial(_NoListingHandler, directory=root)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        httpd.serve_forever()
    return 0


def base_dir() -> str:
    """实例状态目录与分享根目录的公共父目录（位于系统临时目录，跨会话可见）。"""
    d = os.path.join(tempfile.gettempdir(), BASE_DIR_NAME)
    os.makedirs(d, exist_ok=True)
    return d


def instances_dir() -> str:
    """存放每个实例状态 json 的目录。"""
    d = os.path.join(base_dir(), INSTANCES_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d


def instance_path(instance_id: str) -> str:
    """返回某实例状态文件的完整路径。instance_id 格式：<pid>-<8位随机hex>。"""
    return os.path.join(instances_dir(), "%s.json" % instance_id)


def list_instance_ids() -> List[str]:
    """列出当前登记的全部实例 id（按状态文件名排序，不带 .json 后缀）。"""
    try:
        files = os.listdir(instances_dir())
    except Exception:
        return []
    return sorted(f[:-5] for f in files if f.endswith(".json"))


def pick_port() -> int:
    """向内核申请一个空闲端口后立即释放，供图库绑定（存在极小竞态，可接受）。"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def find_cloudflared() -> Optional[str]:
    """定位 cloudflared：显式环境变量 CLOUDFLARED 优先，其次 PATH，最后常见默认位置。"""
    p = os.environ.get("CLOUDFLARED")
    if p and os.path.exists(p):
        return p
    for name in ("cloudflared", "cloudflared.exe"):
        p = shutil.which(name)
        if p:
            return p
    # 常见默认位置：Windows 下实际文件带 .exe 后缀，两个名字都试
    for name in ("~/.local/bin/cloudflared", "~/.local/bin/cloudflared.exe"):
        p = os.path.expanduser(name)
        if os.path.exists(p):
            return p
    return None


def detach_kwargs() -> Dict[str, int]:
    """子进程脱离当前会话的创建参数：Windows 用进程组+无控制台窗口，POSIX 用新会话。"""
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return {"creationflags": flags}
    return {"start_new_session": True}


def _no_proxy_opener():
    """构造强制直连的 opener：忽略系统/环境代理。

    原因：校验目标要么是本地回环、要么是公网隧道 URL；若本机系统代理不可用
    （代理软件残留等常见情况），走代理会把可用链路误判为 down。隧道建立本身
    依赖直连 Cloudflare 边缘，因此校验也必须直连，口径一致。
    """
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http_ok(url: str, timeout: int = HTTP_TIMEOUT) -> bool:
    """GET 探测 URL 是否返回 200（强制直连）；异常一律视为不可用。"""
    try:
        with _no_proxy_opener().open(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def read_domain(log_path: str) -> str:
    """从 cloudflared 日志中提取 trycloudflare 公网域名；取不到返回空串。"""
    try:
        txt = open(log_path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", txt)
    return m.group(0) if m else ""


def pid_alive(pid: Optional[int]) -> bool:
    """跨平台判断进程是否存活；pid 为空返回 False。

    注意：Windows 下 os.kill(pid, 0) 会强杀进程，不能用来探活，须改用 tasklist。
    """
    if not pid:
        return False
    try:
        if os.name == "nt":
            r = subprocess.run(
                ["tasklist", "/FI", "PID eq %d" % pid, "/NH"],
                capture_output=True, text=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return re.search(r"\b%d\b" % pid, r.stdout or "") is not None
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def stop_process(pid: Optional[int]) -> bool:
    """终止进程：Windows 用 taskkill /T 连子进程树一起杀，POSIX 用 SIGTERM。"""
    if not pid:
        return False
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True, text=True, timeout=15,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.kill(pid, 15)
        return True
    except Exception:
        return False


def cleanup_instance(instance_id: str) -> Optional[Dict]:
    """按实例 id 清理：停进程(若存活)、删分享目录、删状态文件。

    返回被清理实例的状态 dict；状态文件损坏/缺失时仅尝试删文件并返回 None。
    """
    fp = instance_path(instance_id)
    try:
        with open(fp, encoding="utf-8") as f:
            st = json.load(f)
    except Exception:
        try:
            os.remove(fp)
        except Exception:
            pass
        return None
    for key in ("tunnel_pid", "gallery_pid"):
        if pid_alive(st.get(key)):
            stop_process(st.get(key))
    shutil.rmtree(st.get("share_root", ""), ignore_errors=True)
    try:
        os.remove(fp)
    except Exception:
        pass
    return st


def reap_stale() -> List[str]:
    """回收孤儿实例：图库与隧道进程都已不在的旧实例，清理其进程/目录/状态。"""
    reaped = []
    for iid in list_instance_ids():
        try:
            with open(instance_path(iid), encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            continue
        if not pid_alive(st.get("gallery_pid")) and not pid_alive(st.get("tunnel_pid")):
            if cleanup_instance(iid):
                reaped.append(iid)
    return reaped


def cleanup_legacy() -> List[str]:
    """升级兼容：回收旧版(单实例)遗留的服务与临时目录。

    旧版遗留两处：<tmp>/img-share/img-share.state 单状态文件；
    <tmp>/img-share-<pid>/ 形态的分享目录(归属进程已死才删除)。
    """
    cleaned = []
    # 1) 旧版单状态文件：停进程 + 删分享目录 + 删状态文件
    old_state = os.path.join(base_dir(), LEGACY_STATE)
    if os.path.isfile(old_state):
        try:
            with open(old_state, encoding="utf-8") as f:
                st = json.load(f)
            for key in ("tunnel_pid", "gallery_pid"):
                if pid_alive(st.get(key)):
                    stop_process(st.get(key))
            # 旧状态文件里记录的分享目录一并删除，并登记目录名便于日志核对
            share = st.get("share")
            if share and os.path.isdir(share):
                shutil.rmtree(share, ignore_errors=True)
                cleaned.append(os.path.basename(share) or share)
        except Exception:
            pass
        try:
            os.remove(old_state)
        except Exception:
            pass
        cleaned.append("legacy-state")
    # 2) 旧版 <tmp>/img-share-<pid> 分享目录：目录归属 pid 已死则删除
    tmp = tempfile.gettempdir()
    try:
        for name in os.listdir(tmp):
            m = re.fullmatch(r"img-share-(\d+)", name)
            if not m:
                continue
            full = os.path.join(tmp, name)
            if os.path.isdir(full) and not pid_alive(int(m.group(1))):
                shutil.rmtree(full, ignore_errors=True)
                cleaned.append(name)
    except Exception:
        pass
    return cleaned


def public_url(st: Dict, name: str) -> str:
    """构造带随机 token 路径的公开文件 URL（文件名做 URL 编码）。"""
    return "%s/%s/%s" % (st["base"], st["token"], urllib.parse.quote(name))


def write_instance(st: Dict) -> None:
    """原子写入实例状态文件（先写 .tmp 再 rename，避免出现半截状态文件）。"""
    fp = instance_path(st["id"])
    tmp_fp = fp + ".tmp"
    with open(tmp_fp, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    os.replace(tmp_fp, fp)


def run(args) -> int:
    """起服务+隧道分享文件：图库仅回环、禁目录列表、文件放随机 token 子目录、端到端校验后登记实例。"""
    cf = find_cloudflared()
    if not cf:
        print("[!] 未找到 cloudflared。安装: mac(brew install cloudflared) / win(winget install Cloudflare.cloudflared) / linux(见 README)；或设环境变量 CLOUDFLARED=/路径/cloudflared")
        return 1
    files = args.share
    if not files:
        print("[!] 至少给一个要分享的文件")
        return 1
    for f in files:
        if not os.path.isfile(f):
            print("[!] 文件不存在: %s" % f)
            return 1

    reaped = reap_stale()
    if reaped:
        print("reaped stale instances: " + ", ".join(reaped))
    legacy = cleanup_legacy()
    if legacy:
        print("cleaned legacy leftovers: " + ", ".join(legacy))

    # 每次分享新建真随机唯一目录(mkdtemp 原子创建，避免 PID 复用冲突)；
    # 文件再放进 16B 随机 token 子目录，公网只能访问带 token 的路径，且目录列表已禁用。
    share_root = tempfile.mkdtemp(prefix="share-", dir=base_dir())
    token = secrets.token_hex(TOKEN_BYTES)
    token_dir = os.path.join(share_root, token)
    os.makedirs(token_dir)
    names: List[str] = []
    for f in files:
        base = os.path.basename(f.rstrip("/\\"))
        if not base:
            print("[!] 无效文件名: %s" % f)
            shutil.rmtree(share_root, ignore_errors=True)
            return 1
        shutil.copyfile(os.path.abspath(f), os.path.join(token_dir, base))
        names.append(base)

    instance_id = "%d-%s" % (os.getpid(), secrets.token_hex(4))
    port = args.port or pick_port()
    first = names[0]
    gproc = None
    tproc = None
    try:
        # 1) 图库子进程：serve.py --gallery <port> <share_root>（仅回环、禁目录列表）
        gallery_log = os.path.join(base_dir(), "gallery-%s.log" % instance_id)
        with open(gallery_log, "w", encoding="utf-8") as glog:
            gproc = subprocess.Popen(
                [sys.executable, os.path.abspath(__file__), "--gallery", str(port), share_root],
                stdout=glog, stderr=glog, **detach_kwargs(),
            )
        # 2) 就绪校验：本地带 token 的真实文件 URL 返回 200 才算图库就绪
        local_url = public_url({"base": "http://127.0.0.1:%d" % port, "token": token}, first)
        ready = False
        for _ in range(GALLERY_WAIT_SEC):
            if http_ok(local_url):
                ready = True
                break
            time.sleep(1)
        if not ready:
            raise RuntimeError("图库未就绪(端口 %d)，日志见 %s" % (port, gallery_log))

        # 3) 隧道：cloudflared 快捷隧道指向本地图库
        tun_log = os.path.join(base_dir(), "tunnel-%s.log" % instance_id)
        with open(tun_log, "w", encoding="utf-8") as tlog:
            tproc = subprocess.Popen(
                [cf, "tunnel", "--url", "http://127.0.0.1:%d" % port,
                 "--no-autoupdate", "--protocol", "http2"],
                stdout=tlog, stderr=tlog, **detach_kwargs(),
            )
        base = ""
        for _ in range(DOMAIN_POLL):
            base = read_domain(tun_log)
            if base:
                break
            time.sleep(3)
        if not base:
            raise RuntimeError("未取到隧道域名，日志见 %s" % tun_log)

        # 4) 端到端校验：公网带 token 的真实文件 URL 必须返回 200，否则立即撤
        u = public_url({"base": base, "token": token}, first)
        ok = False
        for _ in range(E2E_POLL):
            if http_ok(u):
                ok = True
                break
            time.sleep(3)
        if not ok:
            raise RuntimeError("端到端校验失败: %s" % u)

        st = {
            "id": instance_id,
            "base": base,
            "token": token,
            "port": port,
            "gallery_pid": gproc.pid,
            "tunnel_pid": tproc.pid,
            "names": names,
            "share_root": share_root,
            "tun_log": tun_log,
            "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        write_instance(st)
        print("PUBLIC_BASE=%s" % base)
        print("PUBLIC_PATH=/%s/<文件名>" % token)
        print("SHARE_FILES=" + ",".join(names))
        print("内嵌+点击全屏: [![描述](%s)](%s)" % (u, u))
        print("复核: python serve.py --status")
        print("teardown: python serve.py --stop %s   (全部: --stop)" % instance_id)
        return 0
    except Exception as e:
        print("[!] %s" % e)
        for p in (tproc, gproc):
            if p is not None:
                try:
                    p.terminate()
                except Exception:
                    pass
        shutil.rmtree(share_root, ignore_errors=True)
        return 1


def status() -> int:
    """复核全部运行中分享实例：逐个探测真实文件的公网可达性。"""
    reap_stale()
    ids = list_instance_ids()
    if not ids:
        print("[!] 无运行中分享(先 --share)")
        return 1
    live_any = False
    for iid in ids:
        try:
            with open(instance_path(iid), encoding="utf-8") as f:
                st = json.load(f)
        except Exception:
            continue
        u = public_url(st, st["names"][0])
        live = http_ok(u)
        live_any = live_any or live
        print("id=%s started=%s" % (st.get("id"), st.get("started_at", "?")))
        print("  PUBLIC_BASE=%s" % st["base"])
        print("  SHARE_FILES=" + ",".join(st["names"]))
        print("  live=%s %s" % ("200" if live else "404/down", u))
    return 0 if live_any else 1


def stop(target: str) -> int:
    """停止实例：target 为具体 id；'__all__' 表示停全部实例。"""
    ids = list_instance_ids()
    if not ids:
        print("[!] 无实例可停止")
        return 1
    if target != "__all__":
        if target not in ids:
            print("[!] 未找到实例 %s（现有: %s）" % (target, ", ".join(ids)))
            return 1
        ids = [target]
    stopped = []
    for iid in ids:
        st = cleanup_instance(iid)
        if st:
            stopped.append(iid)
    print("stopped: " + (", ".join(stopped) if stopped else "none"))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="img-share orchestrator (cross-platform, multi-instance)")
    ap.add_argument("--share", nargs="+", metavar="FILE", help="要分享的文件(可多个)")
    ap.add_argument("--port", type=int, default=None, help="图库端口(默认自动选空闲端口)")
    ap.add_argument("--status", action="store_true", help="复核全部运行中分享")
    ap.add_argument("--stop", nargs="?", const="__all__", default=None, metavar="ID",
                    help="停指定实例；不带 ID 停全部")
    # 内部子命令：由 run() 以子进程方式拉起图库（禁目录列表、仅回环）
    ap.add_argument("--gallery", nargs=2, metavar=("PORT", "ROOT"), help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.gallery is not None:
        return serve_gallery(int(a.gallery[0]), a.gallery[1])
    if a.stop is not None:
        return stop(a.stop)
    if a.status:
        return status()
    if a.share:
        return run(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
