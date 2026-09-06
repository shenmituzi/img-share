#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""img-share 跨平台编排器（含 Windows 原生）：只分享指定文件、端到端校验、可 teardown。
用法:
  python serve.py --share <文件> [更多文件...] [--port N]     # 起服务+隧道，输出 PUBLIC_BASE
  python serve.py --status                                   # 复核当前
  python serve.py --stop                                     # 停服务+隧道+清理
"""
import argparse, json, os, re, shutil, socket, subprocess, sys, tempfile, time, urllib.parse, urllib.request, shutil

STATE_NAME = "img-share.state"

def state_dir():
    d = os.path.join(tempfile.gettempdir(), "img-share")
    os.makedirs(d, exist_ok=True)
    return d

def state_path():
    return os.path.join(state_dir(), STATE_NAME)

def pick_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p

def find_cloudflared():
    from shutil import which
    for c in ("cloudflared", "cloudflared.exe"):
        p = which(c)
        if p: return p
    p = os.environ.get("CLOUDFLARED")
    if p and os.path.exists(p): return p
    p = os.path.expanduser("~/.local/bin/cloudflared")
    if os.path.exists(p): return p
    return None

def detach_kwargs():
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}

def http_ok(url, timeout=8):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def read_domain(log):
    try:
        txt = open(log, encoding="utf-8", errors="ignore").read()
    except Exception:
        return ""
    m = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', txt)
    return m.group(0) if m else ""

def run(args):
    cf = find_cloudflared()
    if not cf:
        print("[!] 未找到 cloudflared。 安装: mac(brew install cloudflared) / win(winget install Cloudflare.cloudflared) / linux(见 README)；或设环境变量 CLOUDFLARED=/路径/cloudflared")
        return 1
    files = args.share
    if not files:
        print("[!] 至少给一个要分享的文件"); return 1
    for f in files:
        if not os.path.isfile(f):
            print("[!] 文件不存在: %s" % f); return 1
    # 只把指定文件拷进独立随机分享目录（不暴露整个 img/）
    share = os.path.join(tempfile.gettempdir(), "img-share-%d" % os.getpid())
    os.makedirs(share, exist_ok=True)
    names = []
    for f in files:
        base = os.path.basename(f.strip())
        shutil.copyfile(os.path.abspath(f), os.path.join(share, base))
        names.append(base)
    port = args.port or pick_port()
    gallery_log = os.path.join(state_dir(), "gallery-%d.log" % os.getpid())
    g = open(gallery_log, "w")
    gproc = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                             cwd=share, stdout=g, stderr=g, **detach_kwargs())
    for _ in range(24):
        if http_ok("http://127.0.0.1:%d/" % port): break
        time.sleep(1)
    tun_log = os.path.join(state_dir(), "tunnel-%d.log" % os.getpid())
    t = open(tun_log, "w")
    tproc = subprocess.Popen([cf, "tunnel", "--url", "http://127.0.0.1:%d" % port,
                              "--no-autoupdate", "--protocol", "http2"], stdout=t, stderr=t, **detach_kwargs())
    base = ""
    for _ in range(20):
        base = read_domain(tun_log)
        if base: break
        time.sleep(3)
    if not base:
        print("[!] 未取到隧道域名，请看 %s" % tun_log); gproc.terminate(); tproc.terminate(); shutil.rmtree(share, ignore_errors=True); return 1
    # 端到端校验真实文件（URL 编码）
    first = names[0]
    u = "%s/%s" % (base, urllib.parse.quote(first))
    ok = False
    for _ in range(20):
        if http_ok(u): ok = True; break
        time.sleep(3)
    if not ok:
        print("[!] 端到端校验失败: %s" % u); gproc.terminate(); tproc.terminate(); shutil.rmtree(share, ignore_errors=True); return 1
    st = {"base": base, "port": port, "gallery_pid": gproc.pid, "tunnel_pid": tproc.pid,
          "names": names, "share": share, "tun_log": tun_log}
    with open(state_path(), "w") as f:
        json.dump(st, f)
    print("PUBLIC_BASE=%s" % base)
    print("SHARE_FILES=" + ",".join(names))
    print("内嵌+点击全屏: [![描述](%s/%s)](%s/%s)" % (base, urllib.parse.quote(first), base, urllib.parse.quote(first)))
    print("teardown: python serve.py --stop")
    return 0

def status(args):
    st = load_state()
    if not st: print("[!] 无状态（先 --share）"); return 1
    u = "%s/%s" % (st["base"], urllib.parse.quote(st["names"][0]))
    print("PUBLIC_BASE=%s" % st["base"])
    print("SHARE_FILES=" + ",".join(st["names"]))
    print("live=%s" % ("200" if http_ok(u) else "404/down"))
    return 0

def stop(args):
    st = load_state()
    if not st: print("[!] 无状态可停止"); return 1
    stopped = []
    for key, lab in (("gallery_pid", "gallery"), ("tunnel_pid", "tunnel")):
        pid = st.get(key)
        if pid:
            try: os.kill(pid, 15); stopped.append(lab)
            except Exception: pass
    shutil.rmtree(st["share"], ignore_errors=True)
    try: os.remove(state_path())
    except Exception: pass
    print("stopped: " + (",".join(stopped) if stopped else "none"))
    return 0

def load_state():
    try:
        with open(state_path()) as f: return json.load(f)
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser(description="img-share orchestrator (cross-platform)")
    ap.add_argument("--share", nargs="+", metavar="FILE")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--stop", action="store_true")
    a = ap.parse_args()
    if a.stop: return stop(a)
    if a.status: return status(a)
    if a.share: return run(a)
    ap.print_help(); return 2

if __name__ == "__main__":
    sys.exit(main())