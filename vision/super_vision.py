"""
super_vision.py — OCR экрана для Фитца (Wayland/GNOME через XDG Portal).
Использует jeepney (чистый Python, без dbus-python/gi).
"""
import os
import time
import threading
import urllib.parse
from datetime import datetime
from core.logger import get_logger

try:
    import mss
    from PIL import Image
    import pytesseract
except Exception:
    mss = None
    Image = None
    pytesseract = None

try:
    from jeepney import DBusAddress, new_method_call
    from jeepney.io.blocking import open_dbus_connection
    jeepney = True
except Exception:
    jeepney = None

from core import os_layer
_log = get_logger("super_vision")

# Путь к Tesseract
_TESSERACT_PATHS = [
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]
for p in _TESSERACT_PATHS:
    if os.path.exists(p):
        try:
            pytesseract.pytesseract.tesseract_cmd = p
        except Exception:
            _log.debug("пропущено в vision/super_vision.py (строка 43)")
        break


class SuperVision:
    def __init__(self):
        self.running = False
        self.log = []
        self._thread = None
        self._portal_ok = None

    def is_available(self) -> bool:
        return pytesseract is not None and Image is not None

    def start(self) -> str:
        if not self.is_available():
            return ("⚠️ Нет зависимостей. Установи: "
                    "pip install mss pytesseract pillow "
                    "и tesseract-ocr (с русским языком)")
        if self.running:
            return "👁️ Супер-зрение уже работает"
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return "👁️ Супер-зрение активировано (OCR экрана)"

    def stop(self) -> str:
        self.running = False
        return "⏹️ Супер-зрение выключено"

    def _loop(self):
        while self.running:
            try:
                text = self.read_screen()
                win = os_layer.get_active_window_title()
                if text and len(text.strip()) > 10:
                    self.log.append({
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "window": win,
                        "text": text[:300],
                    })
                    if len(self.log) > 50:
                        self.log = self.log[-50:]
                time.sleep(10)
            except Exception as e:
                print(f"⚠️ SuperVision: {e}")
                time.sleep(15)

    def _grab_portal(self):
        """
        Захват экрана через XDG Desktop Portal (jeepney).
        """
        if jeepney is None:
            print("⚠️ Нет jeepney. Установи: pip install jeepney")
            return None

        try:
            conn = open_dbus_connection(bus="SESSION")

            # 1) Вызов Screenshot
            addr = DBusAddress(
                "/org/freedesktop/portal/desktop",
                bus_name="org.freedesktop.portal.Desktop",
                interface="org.freedesktop.portal.Screenshot",
            )
            msg = new_method_call(
                addr, "Screenshot",
                "sa{sv}",
                ("", {"interactive": ("b", False)}),
            )
            reply = conn.send_and_get_reply(msg)
            handle = str(reply.body[0])

            # 2) Ждём сигнал Response
            conn.send(new_method_call(
                DBusAddress(
                    "/org/freedesktop/portal/desktop",
                    bus_name="org.freedesktop.portal.Desktop",
                    interface="org.freedesktop.DBus",
                ),
                "AddMatch",
                "s",
                (f"type='signal',interface='org.freedesktop.portal.Request',path='{handle}',member='Response'",),
            ))

            deadline = time.time() + 10
            while time.time() < deadline:
                try:
                    msg = conn.receive(timeout=1)
                except TimeoutError:
                    continue
                if msg is None:
                    continue
                if msg.header.fields.get("member") == "Response":
                    code, results = msg.body
                    if int(code) != 0:
                        print(f"⚠️ Portal отказал (код {code})")
                        return None
                    uri = str(results.get("uri", ""))
                    if not uri.startswith("file://"):
                        return None
                    src = urllib.parse.unquote(uri[7:])
                    img = Image.open(src)
                    img.load()
                    os.remove(src)
                    return img
            print("⚠️ Portal не ответил за 10 сек")
            return None
        except Exception as e:
            print(f"⚠️ Portal ошибка: {type(e).__name__}: {e!r}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            try:
                conn.close()
            except Exception:
                _log.debug("пропущено в vision/super_vision.py (строка 164)")

    def _grab_mss(self):
        try:
            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", shot.size, shot.rgb)
                import numpy as np
                if np.array(img).mean() > 5:
                    return img
        except Exception:
            _log.debug("пропущено в vision/super_vision.py (строка 175)")
        return None

    def _grab_screen(self):
        if os_layer.is_linux() and self._portal_ok is not False:
            img = self._grab_portal()
            if img is not None:
                import numpy as np
                if np.array(img).mean() > 5:
                    self._portal_ok = True
                    return img
                self._portal_ok = False

        img = self._grab_mss()
        if img is not None:
            return img

        return None

    def read_screen(self):
        img = self._grab_screen()
        if img is None:
            return None
        try:
            gray = img.convert("L")
            text = pytesseract.image_to_string(gray, lang="rus+eng")
            return text.strip() if text else None
        except Exception as e:
            print(f"⚠️ OCR ошибка: {e}")
            return None

    def find_on_screen(self, query: str):
        text = self.read_screen()
        if not text:
            return []
        q = query.lower()
        return [ln.strip() for ln in text.split("\n") if q in ln.lower()]

    def get_log(self, limit: int = 10):
        return self.log[-limit:]

    def get_status(self) -> str:
        return "👁️ Супер-зрение активно" if self.running else "👁️ Супер-зрение выключено"

    def get_current_context(self):
        text = self.read_screen()
        win = os_layer.get_active_window_title()
        ctx = []
        if win:
            ctx.append(f"Окно: {win}")
        if text:
            ctx.append(f"Текст: {text[:150]}")
        return " | ".join(ctx) if ctx else None


# ===== ГЛОБАЛЬНЫЙ ЭКЗЕМПЛЯР =====
_super_vision = None

def get_super_vision() -> SuperVision:
    global _super_vision
    if _super_vision is None:
        _super_vision = SuperVision()
    return _super_vision