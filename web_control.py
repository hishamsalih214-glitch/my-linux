#!/usr/bin/env python3
# لوحة تحكم ويب - من غير تليجرام خالص
# شغّل: python web_control.py
# افتح في المتصفح: http://localhost:8080
# بايثون العادي بس، من غير pip

import json
import os
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8080
SITE_PORT = 8000
SITE_DIR = Path.home() / "site"
START_TIME = time.time()
site_proc = None

HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>لوحة تحكم هشام</title>
<style>
body{font-family:system-ui,Arial,sans-serif;background:#f6f6f6;color:#111;margin:0;padding:20px}
.card{max-width:520px;margin:0 auto;background:#fff;border-radius:14px;padding:22px;box-shadow:0 4px 18px rgba(0,0,0,.08)}
h1{margin:0 0 6px;font-size:22px}
p{color:#555;margin:0 0 16px}
button{display:block;width:100%;padding:14px;margin:10px 0;font-size:17px;border:0;border-radius:10px;cursor:pointer}
.green{background:#16a34a;color:#fff}
.red{background:#dc2626;color:#fff}
.blue{background:#2563eb;color:#fff}
#status{background:#f1f5f9;border-radius:10px;padding:14px;white-space:pre-line;line-height:1.7}
a{color:#2563eb}
</style>
</head>
<body>
<div class="card">
<h1>أهلاً، أنا هشام 👋</h1>
<p>لوحة تحكم موقعك — من غير تليجرام</p>
<div id="status">جاري التحميل...</div>
<button class="blue" onclick="call('/api/status')">🔄 تحديث الحالة</button>
<button class="green" onclick="call('/api/site_on')">▶️ تشغيل الموقع</button>
<button class="red" onclick="call('/api/site_off')">⏹️ إيقاف الموقع</button>
<p id="msg"></p>
<p>لما يشتغل الموقع، افتحه من هنا: <a href="/site/" target="_blank">فتح الموقع</a></p>
</div>
<script>
async function call(path){
  document.getElementById('msg').textContent = 'جاري التنفيذ...';
  try{
    const r = await fetch(path,{method:'POST'});
    const d = await r.json();
    document.getElementById('msg').textContent = d.message || 'تم';
    await load();
  }catch(e){ document.getElementById('msg').textContent = 'فيه مشكلة: '+e; }
}
async function load(){
  try{
    const r = await fetch('/api/status');
    const d = await r.json();
    document.getElementById('status').textContent =
      '⏱️ شغال من: ' + d.uptime +
      '\\n💾 مساحة فاضية: ' + d.free +
      '\\n🌐 الموقع: ' + (d.site_running ? 'شغال على المنفذ ' + d.site_port : 'واقف');
  }catch(e){ document.getElementById('status').textContent = 'مش قادر أجيب الحالة'; }
}
load();
</script>
</body>
</html>
"""

# نسخة مضمّنة من صفحة الموقع، عشان اللوحة تشتغل بملف واحد بس
# لو ملف index.html موجود جنب السكربت، هو اللي هيتنسخ. لو مش موجود،
# دي اللي هتتكتب في ~/site/index.html بدل ما يطلع الموقع فاضي.
SITE_HTML = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>موقعي</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #0f172a; color: #f1f5f9; text-align: center; }
  main { max-width: 560px; margin: 0 auto; padding: 48px 20px; }
  h1 { font-size: 2rem; margin: 0 0 8px; }
  p { color: #cbd5e1; line-height: 1.8; }
  .box { background: #1e293b; border-radius: 12px; padding: 20px; margin-top: 24px; }
  a { color: #38bdf8; }
</style>
</head>
<body>
<main>
  <h1>أهلاً، أنا هشام 👋</h1>
  <p>دي صفحة البداية لموقعي. غيّر النص ده من ملف index.html زي ما تحب.</p>
  <div class="box">
    <p><strong>عن الموقع</strong><br>اكتب هنا فكرة موقعك في سطرين.</p>
    <p><strong>تواصل معايا</strong><br>حط هنا رابط تليجرام أو أي وسيلة تواصل تحبها.</p>
  </div>
  <p style="margin-top:24px; font-size:0.9rem;">شغّال من موبايلي عن طريق لوحة التحكم</p>
</main>
</body>
</html>
"""

def get_status():
    uptime_sec = int(time.time() - START_TIME)
    h, rem = divmod(uptime_sec, 3600)
    m, s = divmod(rem, 60)
    uptime = f"{h} ساعة {m} دقيقة {s} ثانية"
    try:
        total, used, free = shutil.disk_usage(str(SITE_DIR if SITE_DIR.exists() else Path.home()))
        free_gb = f"{free / (1024**3):.1f} GB"
    except Exception:
        free_gb = "؟"
    running = site_proc is not None and site_proc.poll() is None
    return {"uptime": uptime, "free": free_gb, "site_running": running, "site_port": SITE_PORT}

def start_site():
    global site_proc
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    # انسخ صفحة البداية لو المجلد فاضي
    src = Path(__file__).parent / "index.html"
    dst = SITE_DIR / "index.html"
    if not dst.exists():
        try:
            if src.exists():
                shutil.copy(src, dst)
            else:
                # مفيش index.html جنب الملف — اكتب النسخة المضمّنة
                dst.write_text(SITE_HTML, encoding="utf-8")
        except Exception:
            pass
    if site_proc is not None and site_proc.poll() is None:
        return False, "الموقع شغال أصلاً"
    site_proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(SITE_PORT), "--directory", str(SITE_DIR)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return True, f"الموقع اشتغل على المنفذ {SITE_PORT}"

def stop_site():
    global site_proc
    if site_proc is None or site_proc.poll() is not None:
        return False, "الموقع واقف أصلاً"
    site_proc.terminate()
    try:
        site_proc.wait(timeout=5)
    except Exception:
        site_proc.kill()
    site_proc = None
    return True, "الموقع اتوقف"

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(HTML)
        elif self.path == "/api/status":
            self._send_json(get_status())
        elif self.path == "/site/" or self.path == "/site":
            # لو الموقع شغال، حوّل ليه
            if site_proc is not None and site_proc.poll() is None:
                self.send_response(302)
                self.send_header("Location", f"http://localhost:{SITE_PORT}/")
                self.end_headers()
            else:
                self._send_json({"message": "الموقع واقف، دوس تشغيل الموقع الأول"}, 400)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/status":
            self._send_json(get_status())
        elif self.path == "/api/site_on":
            ok, msg = start_site()
            self._send_json({"ok": ok, "message": msg, **get_status()})
        elif self.path == "/api/site_off":
            ok, msg = stop_site()
            self._send_json({"ok": ok, "message": msg, **get_status()})
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"لوحة التحكم شغالة على: http://localhost:{PORT}")
    print("افتح الرابط ده في متصفح موبايلك")
    print("للإيقاف: دوس Ctrl+C")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
