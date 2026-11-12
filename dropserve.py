#!/usr/bin/env python3
"""dropserve: a small, token-protected, zero-dependency LAN file sharing server."""
from __future__ import annotations
import argparse
import hashlib
import hmac
import json
import mimetypes
import os
import secrets
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

__version__ = "1.0.0"
PAGE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>dropserve</title><style>
:root{font-family:ui-sans-serif,system-ui,sans-serif;color:#e8edf7;background:#0b1020;font-synthesis:none}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(ellipse at 15% 0,#1a3150 0,transparent 42%),#0b1020}.wrap{max-width:900px;margin:auto;padding:44px 20px}.top{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:28px}.brand{display:flex;align-items:center;gap:13px}.mark{width:42px;height:42px;border-radius:13px;background:linear-gradient(135deg,#55d6be,#6387ff);display:grid;place-items:center;color:#08121f;font-weight:900;font-size:22px}.brand h1{font-size:21px;margin:0}.sub{color:#91a0b8;font-size:13px;margin-top:4px}.pill{border:1px solid #26354e;border-radius:99px;padding:7px 11px;color:#a9bad3;font-size:12px}.panel{background:#111a2c;border:1px solid #24334c;border-radius:18px;padding:22px;margin-bottom:18px;box-shadow:0 18px 50px #0002}.drop{border:1px dashed #476080;border-radius:14px;padding:32px 18px;text-align:center;transition:.18s;background:#0e1728}.drop.over{border-color:#55d6be;background:#13283a}.drop strong{display:block;font-size:16px}.muted{color:#91a0b8;font-size:13px;margin:8px 0 16px}button,.choose{background:#55d6be;color:#08121f;border:0;border-radius:10px;padding:10px 15px;font-weight:750;cursor:pointer}.choose input{display:none}.files{width:100%;border-collapse:collapse}.files td{padding:13px 8px;border-top:1px solid #24334c;font-size:14px}.files td:last-child{text-align:right}.files a{color:#b8d7ff;text-decoration:none}.files a:hover{text-decoration:underline}.size{color:#91a0b8;font-size:12px;white-space:nowrap}.empty{text-align:center;color:#91a0b8;padding:24px}.status{min-height:20px;color:#8ee4d2;font-size:13px;margin-top:12px}.footer{text-align:center;color:#65758e;font-size:12px;margin-top:22px}@media(max-width:560px){.wrap{padding:25px 13px}.panel{padding:15px}.top{align-items:flex-start}.files td{padding:11px 4px}.size{display:none}}
</style></head><body><main class="wrap"><header class="top"><div class="brand"><div class="mark">↓</div><div><h1>dropserve</h1><div class="sub">Private file sharing on your local network</div></div></div><span class="pill">● connected</span></header><section class="panel"><div id="drop" class="drop"><strong>Drop files here to share</strong><p class="muted">or choose files from this device</p><label class="choose">Choose files<input id="picker" type="file" multiple></label><div id="status" class="status" role="status"></div></div></section><section class="panel"><div class="top"><div><strong>Shared files</strong><div class="sub" id="count">Loading…</div></div><button id="refresh" type="button">Refresh</button></div><table class="files"><tbody id="rows"><tr><td class="empty">Loading files…</td></tr></tbody></table></section><div class="footer">dropserve · files stay on the host machine</div></main><script>
const $=s=>document.querySelector(s),status=$('#status');function fmt(n){if(n<1024)return n+' B';let u=['KB','MB','GB','TB'],i=-1;do{n/=1024;i++}while(n>=1024&&i<u.length-1);return n.toFixed(1)+' '+u[i]}
async function refresh(){try{let r=await fetch('/api/files');if(r.status===401){location.reload();return}if(!r.ok)throw Error('Could not load file list');let files=await r.json();$('#count').textContent=files.length+' file'+(files.length===1?'':'s');let rows=$('#rows');rows.replaceChildren();if(!files.length){let tr=document.createElement('tr'),td=document.createElement('td');td.className='empty';td.textContent='No files shared yet';tr.append(td);rows.append(tr);return}for(let f of files){let tr=document.createElement('tr'),name=document.createElement('td'),size=document.createElement('td'),action=document.createElement('td'),a=document.createElement('a');a.href='/download/'+encodeURIComponent(f.name);a.textContent=f.name;a.setAttribute('download',f.name);name.append(a);size.className='size';size.textContent=fmt(f.size);let dl=document.createElement('a');dl.href=a.href;dl.textContent='Download';action.append(dl);tr.append(name,size,action);rows.append(tr)}}catch(e){status.textContent=e.message}}
async function upload(files){for(const file of files){status.textContent='Uploading '+file.name+'…';try{let r=await fetch('/upload?name='+encodeURIComponent(file.name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});let d=await r.json();if(!r.ok)throw Error(d.error||'Upload failed');status.textContent='Uploaded '+d.name}catch(e){status.textContent=file.name+': '+e.message}}await refresh()}
$('#picker').addEventListener('change',e=>upload(e.target.files));$('#refresh').addEventListener('click',refresh);let drop=$('#drop');for(let ev of ['dragenter','dragover'])drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.add('over')});for(let ev of ['dragleave','drop'])drop.addEventListener(ev,e=>{e.preventDefault();drop.classList.remove('over')});drop.addEventListener('drop',e=>upload(e.dataTransfer.files));refresh();
</script></body></html>'''
LOGIN_PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"><title>dropserve · sign in</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b1020;color:#e8edf7;font:15px system-ui}.box{width:min(360px,calc(100% - 36px));padding:28px;background:#111a2c;border:1px solid #26354e;border-radius:18px}h1{margin:0 0 8px}p{color:#91a0b8;font-size:13px}input,button{width:100%;padding:12px;border-radius:9px;margin-top:12px}input{background:#0b1020;border:1px solid #34445f;color:white}button{border:0;background:#55d6be;font-weight:700;cursor:pointer}</style><form class="box" method="post" action="/login"><h1>dropserve</h1><p>Enter the share token to access files on this network.</p><input name="token" type="password" placeholder="Access token" required autofocus autocomplete="current-password"><button>Continue</button></form></html>'''


def safe_name(name):
    name = urllib.parse.unquote(name or "").replace("\\", "/").split("/")[-1]
    name = "".join(c for c in name if c >= " " and c not in "\x7f")
    name = name.strip().strip(".")
    if not name or name in (".", ".."):
        raise ValueError("A valid filename is required")
    return name[:240]


def unique_path(directory, name):
    target = directory / name
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    for number in range(1, 10000):
        candidate = directory / ("%s (%d)%s" % (stem, number, suffix))
        if not candidate.exists():
            return candidate
    raise FileExistsError("Too many files with this name")


def make_cookie(token, timestamp=None):
    timestamp = int(time.time() if timestamp is None else timestamp)
    payload = str(timestamp)
    signature = hmac.new(token.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).hexdigest()
    return payload + "." + signature


def valid_cookie(cookie, token, now=None, max_age=12 * 60 * 60):
    try:
        stamp, signature = cookie.split(".", 1)
        issued = int(stamp)
        current = int(time.time() if now is None else now)
        if issued > current + 60 or current - issued > max_age:
            return False
        expected = hmac.new(token.encode("utf-8"), stamp.encode("ascii"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (ValueError, TypeError):
        return False


def create_handler(directory, token, max_bytes):
    class Handler(BaseHTTPRequestHandler):
        server_version = "dropserve/" + __version__
        sys_version = ""

        def log_message(self, fmt, *args):
            print("[%s] %s" % (self.log_date_time_string(), fmt % args), flush=True)

        def _send(self, status, body, content_type="text/html; charset=utf-8", headers=None):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Cache-Control", "no-store")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self):
            raw = self.headers.get("Cookie", "")
            cookies = {}
            for item in raw.split(";"):
                if "=" in item:
                    key, value = item.strip().split("=", 1)
                    cookies[key] = value
            return valid_cookie(cookies.get("dropserve_session", ""), token)

        def _require_auth(self):
            if self._authorized():
                return True
            self._send(401, LOGIN_PAGE)
            return False

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path == "/login":
                self._send(200, LOGIN_PAGE)
                return
            if path == "/" and not self._authorized():
                self._send(200, LOGIN_PAGE)
                return
            if not self._require_auth():
                return
            if path == "/":
                self._send(200, PAGE)
            elif path == "/api/files":
                items = []
                try:
                    for item in sorted(directory.iterdir(), key=lambda p: p.name.casefold()):
                        try:
                            if item.is_file() and not item.is_symlink():
                                st = item.stat()
                                items.append({"name": item.name, "size": st.st_size})
                        except OSError:
                            continue
                except OSError:
                    self._send(500, json.dumps({"error": "Could not read share directory"}), "application/json")
                    return
                self._send(200, json.dumps(items, ensure_ascii=False), "application/json; charset=utf-8")
            elif path.startswith("/download/"):
                try:
                    name = safe_name(path[len("/download/"):])
                    target = directory / name
                    if target.is_symlink() or not target.is_file():
                        raise FileNotFoundError
                    size = target.stat().st_size
                    with target.open("rb") as stream:
                        self.send_response(200)
                        self.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
                        self.send_header("Content-Length", str(size))
                        self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + urllib.parse.quote(name))
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("Cache-Control", "no-store")
                        self.end_headers()
                        while True:
                            chunk = stream.read(1024 * 1024)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                except (ValueError, FileNotFoundError, OSError):
                    self._send(404, "File not found")
            else:
                self._send(404, "Not found")

        def do_POST(self):
            path = urllib.parse.urlsplit(self.path)
            if path.path == "/login":
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if length < 1 or length > 4096:
                    self._send(400, "Invalid login request")
                    return
                from urllib.parse import parse_qs
                form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
                supplied = form.get("token", [""])[0]
                if not hmac.compare_digest(supplied, token):
                    self._send(403, LOGIN_PAGE)
                    return
                cookie = make_cookie(token)
                self._send(303, b"", headers={"Location": "/", "Set-Cookie": "dropserve_session=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200" % cookie})
                return
            if not self._require_auth():
                return
            if path.path != "/upload":
                self._send(404, "Not found")
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if length < 0:
                self._send(411, json.dumps({"error": "Content-Length is required"}), "application/json")
                return
            if length > max_bytes:
                self._send(413, json.dumps({"error": "File exceeds the configured upload limit"}), "application/json")
                return
            try:
                query = urllib.parse.parse_qs(path.query, keep_blank_values=True)
                name = safe_name(query.get("name", [""])[0])
                target = unique_path(directory, name)
                remaining = length
                temp = directory / (".dropserve-" + secrets.token_hex(8) + ".tmp")
                try:
                    with temp.open("xb") as stream:
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise OSError("Upload ended unexpectedly")
                            stream.write(chunk)
                            remaining -= len(chunk)
                    os.replace(str(temp), str(target))
                finally:
                    try:
                        temp.unlink()
                    except FileNotFoundError:
                        pass
                self._send(201, json.dumps({"name": target.name, "size": length}, ensure_ascii=False), "application/json; charset=utf-8")
            except (ValueError, OSError) as exc:
                self._send(400, json.dumps({"error": str(exc)}), "application/json; charset=utf-8")

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dropserve", description="Share files over your LAN with a private access token.")
    parser.add_argument("-d", "--directory", default=".", help="directory to share (default: current directory)")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="bind address (default: 0.0.0.0)")
    parser.add_argument("-p", "--port", type=int, default=8765, help="port (default: 8765; use 0 for automatic)")
    parser.add_argument("-t", "--token", help="access token (random token is generated if omitted)")
    parser.add_argument("--max-size", type=float, default=512, help="maximum upload size in MiB (default: 512)")
    parser.add_argument("-V", "--version", action="version", version="dropserve " + __version__)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if args.max_size <= 0:
        parser.error("--max-size must be greater than zero")
    directory = Path(args.directory).expanduser().resolve()
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        parser.error("cannot create share directory: %s" % exc)
    if not directory.is_dir():
        parser.error("share path is not a directory")
    token = args.token or secrets.token_urlsafe(24)
    if len(token) < 8:
        parser.error("--token must contain at least 8 characters")
    max_bytes = int(args.max_size * 1024 * 1024)
    handler = create_handler(directory, token, max_bytes)
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        parser.error("cannot start server: %s" % exc)
    server.daemon_threads = True
    host, port = server.server_address[:2]
    print("dropserve %s" % __version__)
    print("Sharing: %s" % directory)
    print("Listen:  %s:%s" % (host, port))
    print("Token:   %s" % token)
    print("Open http://<this-computer-ip>:%s on another device on the same network." % port)
    print("Press Ctrl+C to stop. Keep the token private.", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        print("\ndropserve: stopping", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
