#!/usr/bin/env python3
"""Польотний тест тепловізійної камери (SEEK UAV) на борту дрона.

Raspberry Pi на автономному живленні, до польотника НЕ під'єднаний.
Камера — по USB: ESP32 (CP210x, JSON @921600) + UVC-відео.

Поки дрон кружляє (~10 хв), програма за сценарієм (PLAN нижче) кожні 30-40 с
перемикає камеру: палітри, пресети (наземна / повітряна ціль, низький /
високий контраст, контури), сцени, DDE, шумодави, шторку (вирівнювання),
поворот 180°. Паралельно пише відео:

  raw.mp4        — чистий потік з камери (без жодних написів);
  annotated.mp4  — той самий потік + смуга знизу: крок, пресет, що змінено,
                   поточні значення всіх параметрів, відповідь камери, таймер.
  commands.jsonl — кожна команда і відповідь камери з часом від старту запису.
  журнал.txt     — те саме людською мовою.

Запуск:
  python3 flight_test.py             — одразу (камера має бути під'єднана)
  python3 flight_test.py --auto      — чекати появи камери, потім старт
                                       (так запускається з автостарту)
  python3 flight_test.py --fake --speed 20   — симуляція без камери, у 20× швидше
  python3 flight_test.py --plan      — лише показати сценарій
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

BAUD = 921600
AUTO_DIR = os.path.expanduser("~/Вильоти-фіксації")   # автозаписи (--auto, на борту)
TEST_DIR = os.path.expanduser("~/test-video")         # ручні/тестові запуски
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SEGMENT_SECONDS = 60          # відео ріжеться шматками: зникне живлення — втратимо ≤1 хв
MIN_FREE_BYTES = 1 << 30

# --- фірмовий стиль SEEK UAV (HUD) ---
BRAND = "SEEK UAV"
BRAND_TAG = "Тепловізійна камера Seek UAV 640 V1"
C_ACCENT = "0xE0561F"         # фірмовий помаранчевий (кнопка на сайті)
C_BAR = "0x161616"            # тло нижньої панелі
C_GRAY = "0xB8B8B8"           # другорядний текст
C_WHITE = "white"
# ffmpeg-безпечне екранування тексту для drawtext (одинарні лапки/двокрапки/%)
def esc(t):
    return (str(t).replace("\\", "\\\\").replace(":", "\\:")
            .replace("'", "’").replace("%", "\\%"))

# --- назви з документації Mini2 (1_MINI2instruction set.xlsx) ---
PALETTES = {0: "White hot", 1: "(резерв)", 2: "Gold sepia", 3: "Ironbow",
            4: "Rainbow", 5: "Night", 6: "Aurora", 7: "Red hot", 8: "Jungle",
            9: "Medical", 10: "Black hot", 11: "Gold red"}
SCENES = {0: "Низькотемп. виділення", 1: "Лінійне розтягнення",
          2: "Низький контраст", 3: "Загальний", 4: "Високий контраст",
          5: "Виділення гарячого", 6: "Резерв 1", 7: "Резерв 2", 8: "Резерв 3",
          9: "Контури"}

DEFAULTS = {"brightness": 50, "contrast": 50, "palette": 0, "scene": 3,
            "dde": 65, "anr": 50, "tnr": 50, "egi": 50,
            "shutter_period": 1, "shutter_auto": True}

# --- пресети «як у полі» ---
PRESETS = {
    "ground": ("ПРЕСЕТ 1 · НАЗЕМНА ЦІЛЬ",
               "люди/техніка на тлі ґрунту: високий контраст, підсилені деталі",
               {"palette": 0, "scene": 4, "brightness": 50, "contrast": 60,
                "dde": 75, "anr": 50, "tnr": 60, "egi": 50}),
    "air": ("ПРЕСЕТ 2 · ПОВІТРЯНА ЦІЛЬ",
            "дрон/ЛА на холодному небі: гаряче — червоним, мін. шлейф від TNR",
            {"palette": 7, "scene": 5, "brightness": 40, "contrast": 70,
             "dde": 85, "anr": 35, "tnr": 25, "egi": 50}),
    "lowcon": ("ПРЕСЕТ 3 · НИЗЬКИЙ КОНТРАСТ",
               "туман/дощ/світанок: м'яка картинка, сильний шумодав",
               {"palette": 3, "scene": 2, "brightness": 55, "contrast": 35,
                "dde": 55, "anr": 75, "tnr": 75, "egi": 50}),
    "outline": ("ПРЕСЕТ 4 · КОНТУРИ / ВИСОКИЙ КОНТРАСТ",
                "орієнтування вночі: контурний режим, EGI на максимум",
                {"palette": 10, "scene": 9, "brightness": 50, "contrast": 75,
                 "dde": 70, "anr": 50, "tnr": 50, "egi": 90}),
}


def base(**changes):
    """Команда = заводські значення + зміни: кожен крок стартує з відомого стану,
    тож видно ефект саме того параметра, який показуємо."""
    cmd = {k: v for k, v in DEFAULTS.items() if k not in ("shutter_period", "shutter_auto")}
    cmd.update(changes)
    return cmd


def preset_step(key, seconds):
    title, note, params = PRESETS[key]
    return (seconds, title, note, [base(**params)])


# (тривалість с, заголовок, пояснення, [команди по черзі])
PLAN = [
    (30, "БАЗА · заводські налаштування", "еталон для порівняння: White hot, сцена «Загальний»",
     [base(), {"shutter_auto": True, "shutter_period": 1}]),
    (30, "ПАЛІТРА · Black hot", "чорне — гаряче", [base(palette=10)]),
    (30, "ПАЛІТРА · Ironbow", "залізо: кольорова шкала температур", [base(palette=3)]),
    (30, "ПАЛІТРА · Red hot", "найгарячіше підсвічено червоним", [base(palette=7)]),
    (30, "ПАЛІТРА · Rainbow", "веселка: максимум розрізнення рівнів", [base(palette=4)]),
    preset_step("ground", 35),
    preset_step("air", 35),
    preset_step("lowcon", 35),
    preset_step("outline", 35),
    (30, "СЦЕНА · Низькотемпературне виділення", "підкреслює холодні об'єкти", [base(scene=0)]),
    (30, "СЦЕНА · Лінійне розтягнення", "без нелінійного AGC — «чесна» шкала", [base(scene=1)]),
    (30, "DDE = 0 · деталізацію ВИМКНЕНО", "порівняй з наступним кроком: розмиті краї", [base(dde=0)]),
    (30, "DDE = 100 · деталізація МАКСИМУМ", "різкі краї, дрібні деталі, більше зерна", [base(dde=100)]),
    (30, "ШУМОДАВ ВИМКНЕНО · ANR=0 TNR=0", "зерно і «сніг» на рівних ділянках", [base(anr=0, tnr=0)]),
    (30, "ШУМОДАВ МАКСИМУМ · ANR=100 TNR=100", "гладко, але шлейф за рухом", [base(anr=100, tnr=100)]),
    (30, "ШТОРКА ЗАКРИТА · автошторку вимкнено", "кадр однорідний — камера бачить шторку",
     [{"shutter_auto": False}, {"shutter": "close"}]),
    (30, "ШТОРКА ВІДКРИТА · вирівнювання (NUC)", "після калібрування — рівне поле; автошторка знов увімк.",
     [{"shutter": "open"}, {"shutter_auto": True, "shutter_period": 1}]),
    (35, "ПОВОРОТ 180° · записано у флеш", "картинку перевернуто командою rotation",
     [base(), {"rotation": 180, "btn": "save"}]),
    (35, "ПОВОРОТ 0° · відновлення", "повертаємо нормальну орієнтацію й початкові налаштування",
     ["RESTORE", {"rotation": 0, "btn": "save"}]),
]

PARAM_LABELS = [("palette", "Палітра"), ("scene", "Сцена"), ("brightness", "Яскр"),
                ("contrast", "Контр"), ("dde", "DDE"), ("anr", "ANR"), ("tnr", "TNR"),
                ("egi", "EGI")]


def fmt_time(s):
    s = max(0, int(s))
    return f"{s // 60:02d}:{s % 60:02d}"


def log(msg):
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


# ------------------------------------------------------------------ пошук заліза
def usb_attr(sysdev, name):
    """Піднятись по sysfs від пристрою до USB-вузла і прочитати атрибут."""
    path = os.path.realpath(sysdev)
    while path and path != "/":
        f = os.path.join(path, name)
        if os.path.isfile(f):
            with open(f) as fh:
                return fh.read().strip()
        path = os.path.dirname(path)
    return None


def find_serial():
    ports = sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/ttyACM*"))
    # спершу CP210x (10c4) — це ESP32 на модулі камери
    ports.sort(key=lambda p: usb_attr(f"/sys/class/tty/{os.path.basename(p)}/device",
                                      "idVendor") != "10c4")
    return ports[0] if ports else None


def find_video():
    """USB UVC-вузол з захопленням. Термалка (3474) — першою."""
    found = []
    for node in sorted(glob.glob("/sys/class/video4linux/video*"),
                       key=lambda p: int(re.sub(r"\D", "", os.path.basename(p)))):
        real = os.path.realpath(node)
        if "/usb" not in real:
            continue                       # pispbe, hevc і т.п. на Pi
        idx = os.path.join(node, "index")
        if os.path.isfile(idx) and open(idx).read().strip() != "0":
            continue                       # другий вузол UVC — метадані
        vendor = usb_attr(node + "/device", "idVendor")
        found.append((vendor != "3474", "/dev/" + os.path.basename(node)))
    found.sort()
    return found[0][1] if found else None


def pick_format(dev):
    """Найбільша роздільність у YUYV (інакше MJPG) і найвищий fps для неї."""
    try:
        out = subprocess.run(["v4l2-ctl", "-d", dev, "--list-formats-ext"],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return None
    fmts, cur, size = {}, None, None
    for line in out.splitlines():
        m = re.search(r"'(\w+)'", line)
        if m and "[" in line:
            cur = m.group(1)
            fmts.setdefault(cur, {})
            continue
        m = re.search(r"Size: \w+ (\d+)x(\d+)", line)
        if m and cur:
            size = (int(m.group(1)), int(m.group(2)))
            fmts[cur].setdefault(size, [])
            continue
        m = re.search(r"\(([\d.]+) fps\)", line)
        if m and cur and size:
            fmts[cur][size].append(float(m.group(1)))
    for fourcc, ff in (("YUYV", "yuyv422"), ("MJPG", "mjpeg")):
        if fmts.get(fourcc):
            size = max(fmts[fourcc], key=lambda s: s[0] * s[1])
            avail = fmts[fourcc][size] or [30.0]
            # YUYV нестиснений: 640×512×2×60 ≈ 39 МБ/с > смуги USB2 → «corrupted buffer».
            # Тримаємось ≤30 fps для сирого потоку; для MJPG обмеження нема.
            cap = 30.0 if fourcc == "YUYV" else max(avail)
            fps = max([f for f in avail if f <= cap] or [min(avail)])
            return ff, size, int(round(fps))
    return None


# ------------------------------------------------------------------ камера (UART)
class Camera:
    def __init__(self, port):
        import serial  # pyserial
        self._serial_mod = serial
        self.port = port
        self.ser = None
        self.open()

    def open(self):
        try:
            self.ser = self._serial_mod.Serial(self.port, BAUD, timeout=0.1)
            self.ser.reset_input_buffer()
        except Exception as e:
            self.ser = None
            log(f"UART {self.port} не відкрився: {e}")

    def send(self, obj, timeout=3.0):
        """Надіслати JSON-рядок, дочекатися JSON-відповіді. Повертає dict або None."""
        if self.ser is None:
            self.open()
            if self.ser is None:
                return None
        try:
            self.ser.reset_input_buffer()
            self.ser.write((json.dumps(obj, separators=(",", ":")) + "\n").encode())
            self.ser.flush()
            end = time.monotonic() + timeout
            buf = b""
            while time.monotonic() < end:
                buf += self.ser.read(512)
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if line.startswith(b"{"):
                        try:
                            return json.loads(line)
                        except ValueError:
                            pass
            return None
        except Exception as e:
            log(f"UART помилка: {e}")
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None       # наступна команда спробує перевідкрити
            return None

    def close(self):
        if self.ser:
            self.ser.close()


class FakeCamera:
    """Симуляція ESP32 для перевірки без заліза."""
    port = "fake"

    def __init__(self):
        self.params = dict(DEFAULTS)

    def send(self, obj, timeout=3.0):
        time.sleep(0.02)
        if obj.get("cmd") == "get":
            return {"ok": True, "info": {"name": "fake", "version": "0", "serial": "FAKE"},
                    "params": dict(self.params), "defaults": dict(DEFAULTS)}
        if "shutter" in obj:
            return {"ok": True, "shutter": obj["shutter"]}
        if obj.get("btn") == "save":
            return {"ok": True, "saved": True}
        self.params.update(obj)
        return {"ok": True, "params": obj}

    def close(self):
        pass


# ------------------------------------------------------------------ запис відео
class Recorder:
    def __init__(self, outdir, source, fmt, fake=False):
        self.outdir = outdir
        self.source = source
        self.fmt = fmt              # (ffmpeg_format, (w, h), fps)
        self.fake = fake
        # динамічні поля HUD (кожне — окремий drawtext з reload)
        self.fields = ["step", "desc", "active", "p1", "p2", "status", "timer"]
        self.txt = {k: os.path.join(outdir, f".ov_{k}.txt") for k in self.fields}
        self.proc = None
        self.part = 0
        self.errlog = open(os.path.join(outdir, "ffmpeg.log"), "ab")
        self.write_overlay({})

    def write_overlay(self, fields):
        # атомарна заміна: ffmpeg (reload=1) ніколи не прочитає напівзаписаний файл.
        # порожній рядок → пробіл, щоб drawtext не лаявся на пустий textfile
        for k, path in self.txt.items():
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(fields.get(k) or " ")
            os.replace(tmp, path)

    def _hud(self, AW, AH, BAR):
        """Фірмовий HUD SEEK UAV: кутові скоби, приціл, лого, панель параметрів."""
        u = AW / 1280.0
        def px(v):
            return max(1, int(round(v * u)))
        parts = []
        db = lambda x, y, w, h, c, a=1.0: parts.append(
            f"drawbox=x={x}:y={y}:w={w}:h={h}:color={c}@{a}:t=fill")
        # роздільна лінія «зображення / панель»
        db(0, AH, AW, px(3), C_ACCENT)
        # лого + тег зверху зліва (на зображенні, з підкладкою для читабельності)
        dt = lambda **kw: parts.append("drawtext=" + ":".join(
            f"{k}={v}" for k, v in kw.items()))
        dt(fontfile=FONT_BOLD, text=f"'{BRAND}'", fontcolor=C_WHITE, fontsize=px(40),
           x=px(24), y=px(20), box=1, boxcolor="black@0.35", boxborderw=px(10))
        db(px(24), px(20) + px(52), px(150), px(3), C_ACCENT)
        dt(fontfile=FONT, text=f"'{esc(BRAND_TAG)}'", fontcolor=C_GRAY, fontsize=px(15),
           x=px(24), y=px(20) + px(60), box=1, boxcolor="black@0.35", boxborderw=px(6))
        # нижня панель: параметри
        BY = AH + px(14)
        dt(fontfile=FONT_BOLD, textfile=self.txt["step"], reload=1, expansion="none",
           fontcolor=C_ACCENT, fontsize=px(31), x=px(24), y=BY)
        dt(fontfile=FONT, textfile=self.txt["desc"], reload=1, expansion="none",
           fontcolor=C_GRAY, fontsize=px(20), x=px(24), y=BY + px(42))
        dt(fontfile=FONT_BOLD, textfile=self.txt["active"], reload=1, expansion="none",
           fontcolor=C_ACCENT, fontsize=px(22), x=px(24), y=BY + px(74))
        dt(fontfile=FONT, textfile=self.txt["p1"], reload=1, expansion="none",
           fontcolor=C_WHITE, fontsize=px(21), x=px(24), y=BY + px(108))
        dt(fontfile=FONT, textfile=self.txt["p2"], reload=1, expansion="none",
           fontcolor=C_WHITE, fontsize=px(21), x=px(24), y=BY + px(138))
        return ",".join(parts), BAR

    def start(self):
        ff, (w, h), fps = self.fmt
        self.part += 1
        k = 2 if w <= 640 else 1                  # презентабельний розмір: 640→1280
        AW, AH = w * k, h * k
        BAR = int(190 * AW / 1280.0)              # панель під параметри (пропорційно)
        hud, BAR = self._hud(AW, AH, BAR)
        ann = (f"[a]scale={AW}:{AH}:flags=lanczos,"
               f"pad=iw:ih+{BAR}:0:0:color={C_BAR},{hud}[ann]")
        if self.fake:
            inp = ["-re", "-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate={fps}"]
        else:
            inp = ["-f", "v4l2", "-input_format", ff, "-video_size", f"{w}x{h}",
                   "-framerate", str(fps), "-i", self.source]
        enc = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-g", str(fps), "-f", "segment", "-segment_time", str(SEGMENT_SECONDS),
               "-segment_format", "matroska", "-reset_timestamps", "1"]
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "warning"] + inp + [
            "-filter_complex", f"[0:v]split=2[raw][a];{ann}",
            "-map", "[raw]", *enc, os.path.join(self.outdir, f"raw_p{self.part}_%03d.mkv"),
            "-map", "[ann]", *enc, os.path.join(self.outdir, f"annotated_p{self.part}_%03d.mkv")]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=self.errlog)
        log(f"запис: {self.source} {w}x{h}@{fps} ({ff}), частина {self.part}")

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if not self.proc:
            return
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write(b"q")      # коректно дописати файли
                self.proc.stdin.flush()
            except Exception:
                pass
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=5)
        self.proc = None

    def finalize(self):
        """Склеїти шматки в raw.mp4 / annotated.mp4 (без перекодування)."""
        for kind in ("raw", "annotated"):
            segs = sorted(glob.glob(os.path.join(self.outdir, f"{kind}_p*_*.mkv")),
                          key=lambda p: [int(x) for x in re.findall(r"\d+", os.path.basename(p))])
            segs = [s for s in segs if os.path.getsize(s) > 1024]
            if not segs:
                continue
            lst = os.path.join(self.outdir, f".{kind}_list.txt")
            with open(lst, "w") as f:
                f.writelines(f"file '{s}'\n" for s in segs)
            out = os.path.join(self.outdir, f"{kind}.mp4")
            r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                                "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
                                "-movflags", "+faststart", out], stderr=self.errlog)
            if r.returncode == 0 and os.path.getsize(out) > 1024:
                for s in segs:
                    os.remove(s)
                os.remove(lst)
                log(f"готово: {out}")
            else:
                log(f"склейка {kind} не вдалась — шматки лишились у теці")


# ------------------------------------------------------------------ сценарій
class FlightTest:
    def __init__(self, cam, rec, outdir, speed=1.0):
        self.cam = cam
        self.rec = rec
        self.outdir = outdir
        self.speed = speed
        self.state = dict(DEFAULTS)
        self.state["rotation"] = 0
        self.original = None
        self.t0 = None
        self.stop_flag = threading.Event()
        self.last_status = "—"
        self.jsonl = open(os.path.join(outdir, "commands.jsonl"), "a", encoding="utf-8")
        self.human = open(os.path.join(outdir, "журнал.txt"), "a", encoding="utf-8")
        self.total = sum(s[0] for s in PLAN)

    def now(self):
        return (time.monotonic() - self.t0) * self.speed if self.t0 else 0.0

    def send(self, obj, step_no):
        if obj == "RESTORE":
            obj = self.restore_cmd()
        resp = self.cam.send(obj)
        t = self.now()
        ok = bool(resp and resp.get("ok"))
        if ok:
            for k, v in obj.items():
                if k in self.state:
                    self.state[k] = v
            self.last_status = "OK"
        elif resp is None:
            self.last_status = "НЕМАЄ ВІДПОВІДІ"
        else:
            self.last_status = f"ПОМИЛКА {resp.get('err', '?')}"
        rec = {"t": round(t, 2), "step": step_no, "sent": obj, "resp": resp}
        self.jsonl.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.jsonl.flush()
        self.human.write(f"{fmt_time(t)}  крок {step_no:02d}  → {json.dumps(obj, ensure_ascii=False)}"
                         f"   ← {json.dumps(resp, ensure_ascii=False) if resp else 'немає відповіді'}\n")
        self.human.flush()
        log(f"  → {obj}  ← {resp}")
        return resp

    def restore_cmd(self):
        src = self.original or DEFAULTS
        keys = [k for k, _ in PARAM_LABELS] + ["shutter_period", "shutter_auto"]
        return {k: src[k] for k in keys if k in src}

    def overlay(self, step_no, step, step_t0, changed):
        dur, title, note, _ = step
        s = self.state
        t = self.now()

        def val(k):
            v = s.get(k)
            if k == "palette":
                return PALETTES.get(v, v)
            if k == "scene":
                return SCENES.get(v, v)
            return v

        cells = [f"{label} {val(k)}" for k, label in PARAM_LABELS]
        shutter = "авто" if s.get("shutter_auto") else "РУЧНА"
        active = [f"{label} {val(k)}" for k, label in PARAM_LABELS if k in changed]
        for extra in ("shutter", "rotation"):
            if extra in changed:
                active.append("Шторка " + shutter if extra == "shutter"
                              else f"Поворот {s.get('rotation', 0)}°")
        fields = {
            "step": f"{step_no:02d}/{len(PLAN)}   {title}",
            "desc": note,
            "active": ("ЗМІНЕНО:  " + "   ·   ".join(active)) if active else "",
            "p1": "     ".join(cells[:4]),
            "p2": "     ".join(cells[4:]) + f"     Шторка {shutter}     Поворот {s.get('rotation', 0)}°",
            "status": (f"КАМЕРА {self.last_status}      T+{fmt_time(t)} / {fmt_time(self.total)}"
                       f"      крок {fmt_time(t - step_t0)} / {fmt_time(dur)}"),
            "timer": f"● REC  {fmt_time(t)}",
        }
        self.rec.write_overlay(fields)

    def run(self):
        info = self.cam.send({"cmd": "get"})
        if info and info.get("ok"):
            self.original = info.get("params")
            self.state.update(self.original or {})
            log(f"камера: {info.get('info')}  параметри: {self.original}")
        else:
            log(f"камера не відповіла на get ({info}) — продовжую, відновлю до заводських")
        with open(os.path.join(self.outdir, "camera_before.json"), "w") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)

        self.rec.start()
        time.sleep(1.5)                  # хай ffmpeg відкриє пристрій
        self.t0 = time.monotonic()
        step_start = 0.0
        for i, step in enumerate(PLAN, 1):
            if self.stop_flag.is_set():
                break
            dur, title, note, cmds = step
            log(f"КРОК {i}/{len(PLAN)} [{fmt_time(step_start)}] {title}")
            self.human.write(f"\n=== {fmt_time(step_start)} КРОК {i}: {title} — {note}\n")
            cmd_keys = {k for c in cmds if isinstance(c, dict) for k in c}
            for c in cmds:
                self.send(c, i)
            # підсвічуємо помаранчевим те, що змінилось цим кроком або від заводського
            changed = {k for k, _ in PARAM_LABELS if self.state.get(k) != DEFAULTS[k]}
            if "shutter" in cmd_keys or self.state.get("shutter_auto") is False:
                changed.add("shutter")
            if "rotation" in cmd_keys or self.state.get("rotation", 0):
                changed.add("rotation")
            step_end = step_start + dur
            while self.now() < step_end and not self.stop_flag.is_set():
                self.overlay(i, step, step_start, changed)
                if not self.rec.alive():
                    log("ffmpeg зупинився — перезапускаю запис")
                    self.rec.start()
                time.sleep(0.5 / self.speed if self.speed < 5 else 0.1)
            step_start = step_end

    def emergency_restore(self):
        """При перериванні: повернути камеру в робочий стан."""
        log("відновлення камери після переривання")
        for c in ({"shutter": "open"}, self.restore_cmd(), {"rotation": 0, "btn": "save"}):
            self.send(c, 0)


# ------------------------------------------------------------------ main
def wait_time_sync(timeout=90):
    """У Pi немає RTC: після завантаження годинник відстає, доки NTP не синхронізує.
    Чекаємо синхронізації (без мережі — до timeout). Повертає True, якщо час точний."""
    end = time.monotonic() + timeout
    while True:
        try:
            r = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"],
                               capture_output=True, text=True, timeout=5)
            if r.stdout.strip() == "yes":
                return True
        except (OSError, subprocess.SubprocessError):
            return False
        if time.monotonic() >= end:
            return False
        time.sleep(2)


def next_run_dir(synced=True, auto=False):
    root, prefix = (AUTO_DIR, "rb_auto_test") if auto else (TEST_DIR, "test")
    os.makedirs(root, exist_ok=True)
    # наскрізний номер запуску: без RTC/мережі дата в назві хибна, а номер надійний
    nums = [int(m.group(1)) for x in os.listdir(root) if (m := re.search(r"_#(\d+)_", x))]
    seq = max(nums, default=0) + 1
    base = f"{prefix}_#{seq:03d}_{dt.datetime.now():%Y-%m-%d_%H-%M-%S}" + ("" if synced else "_час-не-синхр")
    d, n = os.path.join(root, base), 1
    while os.path.exists(d):
        n += 1
        d = os.path.join(root, f"{base}_{n}")
    os.makedirs(d)
    return d


def print_plan():
    t = 0
    for i, (dur, title, note, cmds) in enumerate(PLAN, 1):
        print(f"{fmt_time(t)}  {i:2d}. {title}  ({dur} с) — {note}")
        for c in cmds:
            print(f"          {c if c != 'RESTORE' else '<відновити початкові параметри>'}")
        t += dur
    print(f"Разом: {fmt_time(t)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--auto", action="store_true", help="чекати появи камери (для автостарту)")
    ap.add_argument("--delay", type=float, default=5, help="пауза перед стартом, с (дефолт 5)")
    ap.add_argument("--port", help="UART камери (дефолт — автопошук)")
    ap.add_argument("--video", help="відеопристрій (дефолт — автопошук USB UVC)")
    ap.add_argument("--fake", action="store_true", help="симуляція без камери")
    ap.add_argument("--speed", type=float, default=1.0, help="прискорення сценарію (для тесту)")
    ap.add_argument("--plan", action="store_true", help="показати сценарій і вийти")
    ap.add_argument("--steps", type=int, help="виконати лише перші N кроків сценарію")
    a = ap.parse_args()

    if a.steps:
        PLAN[:] = PLAN[:a.steps]

    if a.plan:
        print_plan()
        return 0

    if a.fake:
        port, video, fmt = "fake", "testsrc", ("rawvideo", (384, 288), 30)
    else:
        while True:
            port = a.port or find_serial()
            video = a.video or find_video()
            if port and video:
                break
            if not a.auto:
                log(f"камеру не знайдено (UART: {port}, відео: {video})")
                return 1
            time.sleep(2)
        time.sleep(2)                   # UVC щойно з'явився — дати йому прокинутись
        fmt = pick_format(video)
        if not fmt:
            log(f"не вдалось прочитати формати {video}")
            return 1

    if shutil.disk_usage(os.path.expanduser("~")).free < MIN_FREE_BYTES:
        log("мало місця на картці (<1 ГБ) — не стартую")
        return 1

    synced = True
    if a.auto and not a.fake:
        log("чекаю синхронізації часу (NTP, до 90 с)…")
        synced = wait_time_sync()
        if not synced:
            log("час не синхронізовано — дата/час у назві теки можуть бути неточні")
    outdir = next_run_dir(synced, a.auto)
    log(f"UART {port}, відео {video} {fmt} → {outdir}")
    if a.delay > 0:
        log(f"старт через {a.delay:.0f} с")
        time.sleep(a.delay)

    cam = FakeCamera() if a.fake else Camera(port)
    rec = Recorder(outdir, video, fmt, fake=a.fake)
    test = FlightTest(cam, rec, outdir, speed=a.speed)

    def on_signal(*_):
        test.stop_flag.set()
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    completed = False
    try:
        test.run()
        completed = not test.stop_flag.is_set()
    finally:
        # повне проходження саме відновлює камеру останніми кроками;
        # при перериванні або усіченому (--steps) прогоні — робимо це вручну
        if not completed or a.steps:
            test.emergency_restore()
        rec.stop()
        with open(os.path.join(outdir, "camera_after.json"), "w") as f:
            json.dump(cam.send({"cmd": "get"}), f, ensure_ascii=False, indent=2)
        cam.close()
        rec.finalize()
        log("ТЕСТ ЗАВЕРШЕНО" if completed else "ТЕСТ ПЕРЕРВАНО")
        os.sync()
    return 0 if completed else 2


if __name__ == "__main__":
    sys.exit(main())
