"""
vision_sdk.py — Зрение Фитца напрямую через DeepSeek (V4.1 Flash Vision).
Кроссплатформенная поддержка: Linux (gdbus/gnome-screenshot/mss/scrot),
Windows (PIL.ImageGrab/mss), macOS (screencapture/mss).
Сохраняет скриншоты в data/screenshots/<категория>/.
Добавлен кэш по хэшу изображения (с автоочисткой).
"""
import os
import shutil
import base64
import hashlib
import traceback
import subprocess
import platform as _platform
from datetime import datetime
from PIL import Image
from openai import OpenAI
from core.logger import get_logger

_vlog = get_logger("vision_sdk")
_VISION_TIMEOUTS = (30.0, 60.0)

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    _vlog.debug("dotenv не загрузился — OK, переменные из окружения")

_SYSTEM = _platform.system()  # "Linux", "Windows", "Darwin"

# ===== ПУТИ И ПАПКИ =====
_COPIED_MARKER = os.path.join("data", "screenshots", ".copied.txt")
_CACHE_DIR = os.path.join("data", "screenshots", ".vision_cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

# ===== ОЧИСТКА КЭША ПРИ ЗАГРУЗКЕ =====
def _clean_old_cache(max_files: int = 500, max_age_days: int = 7):
    """Удаляет старые файлы кэша, чтобы папка не разрасталась бесконечно."""
    try:
        cache_files = [
            os.path.join(_CACHE_DIR, f)
            for f in os.listdir(_CACHE_DIR)
            if f.endswith(".txt")
        ]
        if not cache_files:
            return
        now = datetime.now().timestamp()
        # Сортируем по времени модификации (новые в начале)
        cache_files.sort(key=os.path.getmtime, reverse=True)

        # Удаляем всё сверх max_files
        for f in cache_files[max_files:]:
            try:
                os.remove(f)
            except OSError:
                pass

        # Удаляем файлы старше max_age_days
        cutoff = now - max_age_days * 86400
        for f in cache_files[:max_files]:
            try:
                if os.path.getmtime(f) < cutoff:
                    os.remove(f)
            except OSError:
                pass
    except Exception:
        _vlog.debug("пропущено в core/vision_sdk.py (строка 67)")

_SCREENSHOTS_DIR = os.path.join("data", "screenshots")


def _cleanup_old_screenshots(days: int = 7):
    """Удаляет скриншоты старше N дней из data/screenshots/<категория>/."""
    if not os.path.isdir(_SCREENSHOTS_DIR):
        return
    try:
        now = datetime.now().timestamp()
        cutoff = now - days * 86400
        removed = 0
        for category in os.listdir(_SCREENSHOTS_DIR):
            cat_dir = os.path.join(_SCREENSHOTS_DIR, category)
            if not os.path.isdir(cat_dir) or category.startswith("."):
                continue
            for fname in os.listdir(cat_dir):
                fpath = os.path.join(cat_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
                        removed += 1
                except OSError:
                    pass
        if removed > 0:
            print(f"🧹 Очищено скриншотов: {removed}")
    except Exception:
        _vlog.debug("пропущено в core/vision_sdk.py (строка 97)")


_cleanup_old_screenshots()
_clean_old_cache()


def _load_copied() -> set:
    if not os.path.exists(_COPIED_MARKER):
        return set()
    try:
        with open(_COPIED_MARKER, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    except Exception:
        return set()


def _mark_copied(key: str):
    try:
        os.makedirs(os.path.dirname(_COPIED_MARKER), exist_ok=True)
        with open(_COPIED_MARKER, "a", encoding="utf-8") as f:
            f.write(key + "\n")
    except Exception:
        _vlog.debug("пропущено в core/vision_sdk.py (строка 120)")


def _get_image_hash(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception:
        return ""


def _get_cached_response(img_hash: str) -> str:
    cache_file = os.path.join(_CACHE_DIR, f"{img_hash}.txt")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            _vlog.debug("screenshot OSError — skipping file")
    return ""


def _save_cached_response(img_hash: str, response: str):
    if not img_hash or not response:
        return
    cache_file = os.path.join(_CACHE_DIR, f"{img_hash}.txt")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(response)
    except Exception:
        _vlog.debug("пропущено в core/vision_sdk.py (строка 150)")


# ============================================================
# СКРИНШОТЫ: Linux
# ============================================================
def _ensure_unsafe_mode() -> bool:
    """Включает unsafe_mode в GNOME Shell для разрешения скриншотов на Wayland."""
    try:
        check_res = subprocess.run([
            "gdbus", "call", "--session",
            "--dest", "org.gnome.Shell",
            "--object-path", "/org/gnome/Shell",
            "--method", "org.gnome.Shell.Eval",
            "global.context.unsafe_mode"
        ], capture_output=True, timeout=5)

        if check_res.returncode == 0 and b"true" in check_res.stdout:
            return True

        res = subprocess.run([
            "gdbus", "call", "--session",
            "--dest", "org.gnome.Shell",
            "--object-path", "/org/gnome/Shell",
            "--method", "org.gnome.Shell.Eval",
            "global.context.unsafe_mode = true"
        ], capture_output=True, timeout=5)

        if res.returncode == 0:
            print("DEBUG: unsafe_mode успешно включен через D-Bus")
            return True
        else:
            err = res.stderr.decode().strip()
            print(f"DEBUG: Не удалось включить unsafe_mode. Ответ: {err}")
            return False
    except Exception as e:
        print(f"DEBUG: Ошибка при вызове unsafe_mode: {e}")
        return False


def _make_screenshot_linux(temp_path: str) -> bool:
    """Пытается сделать скриншот под Linux."""
    _ensure_unsafe_mode()

    # 1. gdbus (GNOME Shell)
    try:
        abs_path = os.path.abspath(temp_path)
        res = subprocess.run([
            "gdbus", "call", "--session",
            "--dest", "org.gnome.Shell.Screenshot",
            "--object-path", "/org/gnome/Shell/Screenshot",
            "--method", "org.gnome.Shell.Screenshot.Screenshot",
            "false", "false", abs_path
        ], capture_output=True, timeout=10)

        if res.returncode == 0 and os.path.exists(abs_path) and os.path.getsize(abs_path) > 0:
            print("DEBUG: Скриншот сделан через gdbus (GNOME Shell)")
            return True
        else:
            print(f"DEBUG: gdbus вернул код {res.returncode}, stderr: {res.stderr.decode().strip()}")
    except FileNotFoundError:
        print("DEBUG: gdbus не найден, пробую gnome-screenshot...")
    except Exception as e:
        print(f"DEBUG: gdbus упал: {e}")

    # 2. gnome-screenshot
    try:
        res = subprocess.run(["gnome-screenshot", "-f", temp_path], capture_output=True, timeout=10)
        if res.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print("DEBUG: Скриншот сделан через gnome-screenshot")
            return True
        else:
            print(f"DEBUG: gnome-screenshot вернул код {res.returncode}")
    except Exception as e:
        print(f"DEBUG: gnome-screenshot упал: {e}")

    # 3. mss (X11)
    try:
        import mss
        import numpy as np
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.save(temp_path)
            arr = np.array(img)
            if arr.mean() > 5:
                print("DEBUG: Скриншот сделан через mss (X11)")
                return True
            print("DEBUG: mss вернул черный экран")
    except Exception as e:
        print(f"DEBUG: mss упал: {e}")

    # 4. scrot (X11 fallback)
    try:
        subprocess.run(["scrot", temp_path], check=True, timeout=5)
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print("DEBUG: Скриншот сделан через scrot (X11)")
            return True
    except Exception as e:
        print(f"DEBUG: scrot упал: {e}")

    return False


# ============================================================
# СКРИНШОТЫ: Windows
# ============================================================
def _make_screenshot_windows(temp_path: str) -> bool:
    """Пытается сделать скриншот под Windows."""
    # 1. PIL.ImageGrab
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=True)
        img.save(temp_path)
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print("DEBUG: Скриншот сделан через PIL.ImageGrab (Windows)")
            return True
    except Exception as e:
        print(f"DEBUG: ImageGrab упал: {e}")

    # 2. mss
    try:
        import mss
        import numpy as np
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # все мониторы
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
            img.save(temp_path)
            arr = np.array(img)
            if arr.mean() > 5:
                print("DEBUG: Скриншот сделан через mss (Windows)")
                return True
    except Exception as e:
        print(f"DEBUG: mss упал: {e}")

    return False


# ============================================================
# СКРИНШОТЫ: macOS
# ============================================================
def _make_screenshot_macos(temp_path: str) -> bool:
    """Пытается сделать скриншот под macOS."""
    # 1. screencapture
    try:
        subprocess.run(["screencapture", "-x", temp_path], check=True, timeout=10)
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print("DEBUG: Скриншот сделан через screencapture (macOS)")
            return True
    except Exception as e:
        print(f"DEBUG: screencapture упал: {e}")

    # 2. mss
    try:
        import mss
        import numpy as np
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img.save(temp_path)
            arr = np.array(img)
            if arr.mean() > 5:
                print("DEBUG: Скриншот сделан через mss (macOS)")
                return True
    except Exception as e:
        print(f"DEBUG: mss упал: {e}")

    return False


# ============================================================
# ЕДИНЫЙ МЕТОД
# ============================================================
def _make_screenshot(temp_path: str) -> bool:
    """Делает скриншот — кроссплатформенно."""
    if _SYSTEM == "Linux":
        return _make_screenshot_linux(temp_path)
    elif _SYSTEM == "Windows":
        return _make_screenshot_windows(temp_path)
    elif _SYSTEM == "Darwin":
        return _make_screenshot_macos(temp_path)
    else:
        print(f"DEBUG: Неизвестная платформа {_SYSTEM}, пробую mss...")
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=temp_path)
            return os.path.exists(temp_path) and os.path.getsize(temp_path) > 0
        except Exception:
            return False


def _save_screenshot_to_category(category: str, src_file: str) -> str:
    if not src_file or not os.path.exists(src_file):
        return ""

    file_key = f"{os.path.basename(src_file)}::{int(os.path.getmtime(src_file))}"
    if file_key in _load_copied():
        return ""

    dest_dir = os.path.join("data", "screenshots", category)
    os.makedirs(dest_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(src_file)[1] or ".png"
    dest_path = os.path.join(dest_dir, f"{ts}{ext}")

    try:
        shutil.copy2(src_file, dest_path)
        _mark_copied(file_key)
        return dest_path
    except Exception:
        return ""


def describe_screen(prompt: str = "Сделай скриншот и опиши, что на экране.",
                    window_title: str = None,
                    category: str = "прочее") -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("API_URL", "https://api.provod.ai/v1")

    if not api_key:
        return "⚠️ Нет ключа API для зрения. Проверь .env (API_KEY)."

    temp_path = os.path.join("data", "_temp_screenshot.png")
    os.makedirs("data", exist_ok=True)

    # 1. Делаем скриншот
    if not _make_screenshot(temp_path):
        return "⚠️ Не удалось сделать скриншот (все методы вернули ошибку или черный экран)."

    # 2. Проверяем кэш
    img_hash = _get_image_hash(temp_path)
    cached = _get_cached_response(img_hash)
    if cached:
        print(f"DEBUG: Использую кэш для {img_hash[:8]}...")
        _save_screenshot_to_category(category, temp_path)
        try:
            os.remove(temp_path)
        except Exception:
            _vlog.debug("screenshot OSError — skipping file")
        return cached

    # 3. Сохраняем в папку
    saved_path = _save_screenshot_to_category(category, temp_path)

    # 4. Отправляем в API
    try:
        print("DEBUG: Отправляю в API...")
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=60.0)

        with open(temp_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        full_prompt = prompt
        if window_title:
            full_prompt = f"Опиши окно '{window_title}' на экране. {prompt}"

        result = None
        for attempt in range(2):
            try:
                response = client.with_options(timeout=_VISION_TIMEOUTS[attempt]).chat.completions.create(
                    model="anthropic/claude-haiku-5.5",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": full_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{b64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=1500,
                )
            except Exception as e:
                print(f"DEBUG: Попытка {attempt + 1} не удалась: {e}")
                if attempt == 0:
                    print(f"DEBUG: Повторяю с таймаутом {_VISION_TIMEOUTS[1]} сек...")
                    continue
                raise

            msg = response.choices[0].message
            result = msg.content
            reasoning = getattr(msg, "reasoning_content", None)

            if result and result.strip():
                break
            else:
                print(f"DEBUG: Попытка {attempt + 1} вернула пустой content. Reasoning: {reasoning[:100] if reasoning else 'None'}")
                if attempt == 0:
                    print("DEBUG: Повторяю запрос...")
                    continue

        if not result or not result.strip():
            return "⚠️ Модель вернула пустой ответ (только reasoning). Попробуй ещё раз."

        _save_cached_response(img_hash, result)
        if saved_path:
            print(f"📸 Скриншот сохранён: {saved_path}")
        return result.strip()

    except Exception as e:
        print(f"DEBUG: ОШИБКА API: {e}")
        traceback.print_exc()
        return f"⚠️ Ошибка API: {e}"
    finally:
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            _vlog.debug("screenshot OSError — skipping file")