"""실시간 환율 위젯 - 네이버 금융(하나은행 고시환율)
- 드래그 이동, 창 가장자리·모서리 드래그로 크기 조절(글자 비례)
- 우클릭 메뉴: 표시 통화 선택 / 갱신시각 표시 / 글자색·배경색 / 투명도 / 굵기 / 자동실행 / 종료
- 둥근 모서리: Windows 11 DWM 창 모서리 속성(DwmSetWindowAttribute)
- 설정은 fxwidget.json 에 저장
"""
import tkinter as tk
from tkinter import colorchooser, font as tkfont
import requests, threading, json, os, sys, time, urllib.request
# 학교/회사망의 SSL 검사 장비 대응: OS 인증서 저장소를 사용 (없으면 무시)
try:
    import truststore; truststore.inject_into_ssl()
except Exception: pass
try:
    import ctypes
    _user32 = ctypes.windll.user32 if sys.platform == "win32" else None
except Exception:
    _user32 = None

REFRESH_SEC = 60
MIN_ROW_PX = 14   # 통화 1줄 최소 높이(px), 6pt 글자 기준
EDGE = 8          # 크기조절 감지 가장자리 폭(px)
PAD = 3           # 내부 여백(px)
DWM_CORNER = 3    # 2=ROUND(약 8px), 3=ROUNDSMALL(약 4px)
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
FONT = "Consolas" if IS_WIN else "Menlo"
URL = "https://api.stock.naver.com/marketindex/exchange/{}"
FALLBACK_URL = "https://open.er-api.com/v6/latest/KRW"   # 네이버 차단 시 대체(일 1회 갱신)
UNIT100 = {"JPY", "VND"}   # 100단위 고시 통화
HDR = {"User-Agent": "Mozilla/5.0"}
# exe(PyInstaller)로 실행 시 exe 옆, 스크립트 실행 시 스크립트 옆에 설정 저장
_BASE = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CFG = os.path.join(_BASE, "fxwidget.json")
LOG = os.path.join(_BASE, "fxwidget.log")
if IS_WIN:
    STARTUP_LNK = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup", "fxwidget.lnk")
else:
    STARTUP_LNK = os.path.expanduser("~/Library/LaunchAgents/kr.bluesoft.fxwidget.plist")

# (표시명, 네이버 코드)  ※ JPY·VND는 100단위 고시
CURRENCIES = [
    ("USD", "FX_USDKRW"), ("JPY", "FX_JPYKRW"), ("EUR", "FX_EURKRW"), ("CNY", "FX_CNYKRW"),
    ("GBP", "FX_GBPKRW"), ("AUD", "FX_AUDKRW"), ("CAD", "FX_CADKRW"), ("HKD", "FX_HKDKRW"),
    ("TWD", "FX_TWDKRW"), ("THB", "FX_THBKRW"), ("VND", "FX_VNDKRW"), ("SGD", "FX_SGDKRW"),
    ("CHF", "FX_CHFKRW"),
]
DEFAULT_COLORS = {"USD": "#ea835b", "JPY": "#ffb74d", "EUR": "#81c784", "CNY": "#e57373"}
DEFAULT = {
    "geometry": "143x75", "bg": "#404040", "fg": "#dddddd", "stat": "#888888", "alpha": 0.8,
    "show": ["USD", "JPY"], "show_time": True, "colors": DEFAULT_COLORS, "bold": True,
    "proxy": "",   # 예: "http://proxy.school.ac.kr:8080"  (비우면 Windows 시스템 프록시 자동 사용)
    "relay_url": "",   # 예: "https://내도메인/fxrelay/fx.php"  (relay/fx.php 를 회사 서버에 올린 주소)
}

class FxWidget(tk.Tk):
    if IS_WIN:
        CURSORS = {"n": "size_ns", "s": "size_ns", "e": "size_we", "w": "size_we",
                   "nw": "size_nw_se", "se": "size_nw_se", "ne": "size_ne_sw", "sw": "size_ne_sw", "": "arrow"}
    else:
        CURSORS = {"n": "resizeupdown", "s": "resizeupdown", "e": "resizeleftright", "w": "resizeleftright",
                   "nw": "fleur", "se": "fleur", "ne": "fleur", "sw": "fleur", "": "arrow"}

    def __init__(self):
        super().__init__()
        self.cfg = json.loads(json.dumps(DEFAULT))
        try:
            saved = json.load(open(CFG, encoding="utf-8"))
            self.cfg["colors"].update(saved.pop("colors", {}))
            for k in ("usd", "jpy"):   # 구버전 설정 호환
                if k in saved: self.cfg["colors"][k.upper()] = saved.pop(k)
            self.cfg.update(saved)
        except Exception: pass

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", self.cfg["alpha"])
        g = self.cfg["geometry"]
        if "+" not in g: g += "+{}+40".format(self.winfo_screenwidth() - 240)
        self.geometry(g)

        self.texts = {}   # name -> 표시 문자열
        self.prev = {}
        self.stat_text = ""
        self.cv = tk.Canvas(self, highlightthickness=0, bd=0)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<ButtonPress-1>", self._start)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<Motion>", self._hover)
        self.cv.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        if IS_MAC:
            self.cv.bind("<Button-2>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
            self.bind("<Command-q>", lambda e: self._quit())
        self.bind("<Configure>", self._on_resize)

        self._build_menu()
        self._apply_minsize()
        self.refresh()

    # ---- 메뉴 ----
    def _build_menu(self):
        self.menu = tk.Menu(self, tearoff=0)
        cur = tk.Menu(self.menu, tearoff=0)
        self.show_vars = {}
        for n, _ in CURRENCIES:
            v = tk.BooleanVar(value=n in self.cfg["show"])
            self.show_vars[n] = v
            cur.add_checkbutton(label=n, variable=v, command=self._update_show)
        self.menu.add_cascade(label="표시 통화", menu=cur)
        self.time_var = tk.BooleanVar(value=self.cfg["show_time"])
        self.menu.add_checkbutton(label="갱신 시각 표시", variable=self.time_var, command=self._update_show)
        self.menu.add_separator()
        col = tk.Menu(self.menu, tearoff=0)
        col.add_command(label="기본 글자색", command=lambda: self._pick("fg"))
        col.add_command(label="시각 글자색", command=lambda: self._pick("stat"))
        col.add_command(label="배경색", command=lambda: self._pick("bg"))
        col.add_separator()
        for n, _ in CURRENCIES:
            col.add_command(label=f"{n} 글자색", command=lambda n=n: self._pick(("colors", n)))
        self.menu.add_cascade(label="색상", menu=col)
        al = tk.Menu(self.menu, tearoff=0)
        for pct in (100, 90, 80, 70, 60, 50, 40, 30, 20):
            al.add_command(label=f"{pct}%", command=lambda a=pct/100: self._set_alpha(a))
        self.menu.add_cascade(label="투명도", menu=al)
        self.bold_var = tk.BooleanVar(value=self.cfg["bold"])
        self.menu.add_checkbutton(label="굵은 글자", variable=self.bold_var, command=self._set_bold)
        self.menu.add_separator()
        self.autostart_var = tk.BooleanVar(value=os.path.exists(STARTUP_LNK))
        self.menu.add_checkbutton(label="시작 시 자동 실행", variable=self.autostart_var, command=self._set_autostart)
        self.menu.add_separator()
        self.menu.add_command(label="종료", command=self._quit)

    def _update_show(self):
        self.cfg["show"] = [n for n, _ in CURRENCIES if self.show_vars[n].get()]
        self.cfg["show_time"] = self.time_var.get()
        self._apply_minsize(); self._save(); self._draw()
        self.refresh_now()

    def _min_h(self):
        rows = len(self.cfg["show"]) + (0.55 if self.cfg["show_time"] else 0)
        return max(30, int(rows * MIN_ROW_PX) + PAD * 2)

    def _apply_minsize(self):
        mh = self._min_h()
        self.minsize(100, mh)
        self.update_idletasks()
        if self.winfo_height() < mh:
            self.geometry(f"{self.winfo_width()}x{mh}")

    # ---- 그리기 ----
    def _round(self):
        """Windows 11 DWM 둥근 모서리. 투명(layered) 창과 함께 동작함"""
        if not _user32 or getattr(self, "_rounded", False): return
        try:
            hwnd = _user32.GetParent(self.winfo_id()) or self.winfo_id()
            pref = ctypes.c_int(DWM_CORNER)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), ctypes.sizeof(pref))
            self._rounded = True
        except Exception:
            pass

    def _draw(self):
        cv, c = self.cv, self.cfg
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2 or h < 2: return
        cv.delete("all")
        cv.config(bg=c["bg"]); self.configure(bg=c["bg"])
        self._round()

        shown = c["show"]
        rows = len(shown) + (0.55 if c["show_time"] else 0)
        if rows == 0: return
        wt = "bold" if c["bold"] else "normal"
        longest = max((self.texts.get(n, f"{n} ---") for n in shown), key=len, default="USD 0,000.00 ▲")
        f = max(6, int((h - PAD * 2) / (rows * 1.45)))
        while f > 6 and tkfont.Font(family=FONT, size=f, weight=wt).measure(longest) > w - PAD * 2:
            f -= 1
        font = (FONT, f, wt)
        fo = tkfont.Font(family=FONT, size=f, weight=wt)
        lh = fo.metrics("linespace")
        # 남는 가로 공간을 좌우로 균등 분배 (글자 블록을 가운데 정렬)
        x = max(PAD, (w - fo.measure(longest)) // 2)
        y = PAD
        for n in shown:
            cv.create_text(x, y, text=self.texts.get(n, f"{n} ---"), anchor="nw",
                           font=font, fill=c["colors"].get(n, c["fg"]))
            y += lh
        if c["show_time"]:
            cv.create_text(x, y, text=self.stat_text, anchor="nw",
                           font=(FONT, max(6, f // 2)), fill=c["stat"])

    def _on_resize(self, e):
        if e.widget is self: self._draw()

    # ---- 색상/설정 ----
    def _pick(self, key):
        cur = self.cfg["colors"].get(key[1], self.cfg["fg"]) if isinstance(key, tuple) else self.cfg[key]
        col = colorchooser.askcolor(cur, title=str(key), parent=self)[1]
        if col:
            if isinstance(key, tuple): self.cfg["colors"][key[1]] = col
            else: self.cfg[key] = col
            self._save(); self._draw()

    def _set_autostart(self):
        """Windows: 시작프로그램 바로가기 / macOS: LaunchAgents plist"""
        try:
            if self.autostart_var.get():
                if IS_WIN:
                    ps = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{STARTUP_LNK}');"
                          f"$s.TargetPath='{sys.executable}';"
                          + ("" if getattr(sys, "frozen", False) else f"$s.Arguments='\"{os.path.abspath(__file__)}\"';")
                          + f"$s.WorkingDirectory='{_BASE}';$s.Save()")
                    import subprocess
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000, check=True)
                else:
                    if getattr(sys, "frozen", False):
                        args = [sys.executable]
                    else:
                        args = [sys.executable, os.path.abspath(__file__)]
                    items = "".join(f"<string>{a}</string>" for a in args)
                    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>kr.bluesoft.fxwidget</string>
<key>ProgramArguments</key><array>{items}</array>
<key>RunAtLoad</key><true/>
</dict></plist>
"""
                    os.makedirs(os.path.dirname(STARTUP_LNK), exist_ok=True)
                    open(STARTUP_LNK, "w").write(plist)
            else:
                if os.path.exists(STARTUP_LNK): os.remove(STARTUP_LNK)
        except Exception:
            self.autostart_var.set(os.path.exists(STARTUP_LNK))

    def _set_bold(self):
        self.cfg["bold"] = self.bold_var.get()
        self._save(); self._draw()

    def _set_alpha(self, a):
        self.cfg["alpha"] = a
        self.attributes("-alpha", a); self._save()

    def _save(self):
        self.cfg["geometry"] = self.geometry()
        try: json.dump(self.cfg, open(CFG, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        except Exception: pass

    def _quit(self):
        self._save(); self.destroy()

    # ---- 이동/크기 ----
    def _edge(self, e):
        x, y = e.x_root - self.winfo_rootx(), e.y_root - self.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        v = "n" if y < EDGE else "s" if y > h - EDGE else ""
        hz = "w" if x < EDGE else "e" if x > w - EDGE else ""
        return v + hz

    def _hover(self, e):
        self.cv.config(cursor=self.CURSORS[self._edge(e)])

    def _start(self, e):
        self._mode = self._edge(e)
        self._ox, self._oy = e.x_root, e.y_root
        self._gx, self._gy = self.winfo_x(), self.winfo_y()
        self._gw, self._gh = self.winfo_width(), self.winfo_height()

    def _drag(self, e):
        dx, dy = e.x_root - self._ox, e.y_root - self._oy
        m = self._mode
        if not m:
            self.geometry(f"+{self._gx+dx}+{self._gy+dy}")
            return
        x, y, w, h = self._gx, self._gy, self._gw, self._gh
        mh = self._min_h()
        if "e" in m: w = max(100, self._gw + dx)
        if "s" in m: h = max(mh, self._gh + dy)
        if "w" in m:
            w = max(100, self._gw - dx); x = self._gx + (self._gw - w)
        if "n" in m:
            h = max(mh, self._gh - dy); y = self._gy + (self._gh - h)
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ---- 데이터 ----
    def refresh(self):
        self.refresh_now()
        self.after(REFRESH_SEC * 1000, self.refresh)

    def refresh_now(self):
        threading.Thread(target=self._fetch, daemon=True).start()

    def _proxies(self):
        p = self.cfg.get("proxy") or ""
        if p: return {"http": p, "https": p}
        return None   # None이면 requests가 Windows 시스템 프록시(레지스트리)를 자동 사용

    def _get(self, url):
        """GET JSON. SSL 검증 실패 시 검증 없이 1회 재시도 (SSL 인스펙션 망 대응)"""
        kw = dict(headers=HDR, timeout=10, proxies=self._proxies())
        try:
            return requests.get(url, **kw).json()
        except requests.exceptions.SSLError:
            import urllib3; urllib3.disable_warnings()
            self._insecure = True
            return requests.get(url, verify=False, **kw).json()

    # ---- 소스별 조회 (각각 {name: value} 반환, 실패 시 예외) ----
    def _src_relay(self, want):
        """직접 운영하는 중계 서버(relay/fx.php). 설정 relay_url 이 있을 때만"""
        base = (self.cfg.get("relay_url") or "").strip()
        if not base: raise RuntimeError("relay_url 미설정")
        j = self._get(base + ("&" if "?" in base else "?") + "codes=" + ",".join(c for _, c in want))
        return {n: float(j[c]) for n, c in want if c in j}

    def _src_naver(self, want):
        res = {}
        for n, code in want:
            j = self._get(URL.format(code))["exchangeInfo"]
            res[n] = float(j["closePrice"].replace(",", ""))
        return res

    def _src_erapi(self, want):
        r = self._get(FALLBACK_URL)["rates"]
        return {n: (100 if n in UNIT100 else 1) / r[n] for n, _ in want if n in r}

    def _src_frankfurter(self, want):
        """ECB 기준 일 1회 갱신, 도메인이 달라 차단 회피용"""
        syms = ",".join(n for n, _ in want)
        r = self._get(f"https://api.frankfurter.app/latest?from=KRW&to={syms}")["rates"]
        return {n: (100 if n in UNIT100 else 1) / r[n] for n, _ in want if n in r}

    def _fetch(self):
        res, errs = {}, []
        want = [(n, c) for n, c in CURRENCIES if n in self.cfg["show"]]
        src = "none"
        # 순서: 중계서버(설정 시) → 네이버 → er-api → frankfurter. 하나라도 값이 나오면 중단
        for name, fn in (("relay", self._src_relay), ("naver", self._src_naver),
                         ("er-api", self._src_erapi), ("frankfurter", self._src_frankfurter)):
            if not want: break
            if name == "relay" and not (self.cfg.get("relay_url") or "").strip(): continue
            try:
                res = fn(want)
                if res: src = name; break
            except Exception as ex:
                errs.append(f"{name} {type(ex).__name__}: {str(ex)[:120]}")
        try:
            with open(LOG, "w", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} source={src} ok={sorted(res)}\n")
                for e in errs: f.write(e + "\n")
                f.write(f"system_proxy={urllib.request.getproxies()} cfg_proxy={self.cfg.get('proxy')!r} "
                        f"insecure_retry={getattr(self, '_insecure', False)}\n")
                if errs: f.write("힌트: 학교망 프록시가 있으면 fxwidget.json 의 proxy 에 http://주소:포트 를 넣으세요\n")
        except Exception: pass
        self.after(0, self._show, res, errs if not res else None, src)

    def _show(self, res, err, src="naver"):
        for n, v in res.items():
            self.texts[n] = f"{n} {v:,.2f}{self._arrow(n, v)}"
        tag = "  오류" if err else ("" if src in ("naver", "relay") else "  *대체")
        self.stat_text = time.strftime("%H:%M:%S") + tag
        self._draw()

    def _arrow(self, k, v):
        p = self.prev.get(k); self.prev[k] = v
        if p is None or abs(v - p) < 0.005: return ""
        return " ▲" if v > p else " ▼"

if __name__ == "__main__":
    FxWidget().mainloop()
