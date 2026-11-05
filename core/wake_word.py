"""
wake_word.py — Гибридный детектор имени (Vosk + GigaAM).
pause() реально закрывает поток и ждёт, пока PortAudio отпустит устройство.
"""
import os
import io
import json
import time
import wave
import queue
import threading
from collections import deque
from core.logger import get_logger

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import vosk
except Exception:
    vosk = None

try:
    import onnx_asr
except Exception:
    onnx_asr = None

_log = get_logger("wake_word")


def _silence_fd2():
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    os.dup2(devnull, 2)
    os.close(devnull)
    return old_stderr


def _restore_fd2(old_stderr):
    try:
        os.dup2(old_stderr, 2)
    finally:
        os.close(old_stderr)


class WakeWordDetector:
    def __init__(self,
                 vosk_model_path: str = "data/models/vosk/vosk-model-small-ru-0.22",
                 gigaam_model: str = "gigaam-v3-rnnt",
                 sample_rate: int = 16000):
        self.vosk_model_path = vosk_model_path
        self.gigaam_model_name = gigaam_model
        self.sample_rate = sample_rate
        self.gigaam_lock = threading.Lock()  # ЗАЩИТА ОТ СЕГФОЛТА

        self.vosk_model = None
        self.gigaam = None

        self.running = False
        self._paused = False
        self.wake_detected = threading.Event()
        self.last_word = None
        self._thread = None
        self._last_hit_time = 0.0
        self._stream = None

        self.grammar_words = ["фиц", "фитц", "сильви", "[unk]"]

        self.fuzzy_roots = (
            "фит", "фиц", "fit",
            "силь", "сил", "сель", "sel", "syl",
        )

        self._blocksize = 4000
        maxlen = int(3.0 * sample_rate / self._blocksize)
        self._ring = deque(maxlen=maxlen)

    # ============================================================
    # ЗАГРУЗКА
    # ============================================================
    def _load_vosk(self) -> bool:
        if vosk is None:
            print("⚠️ Vosk не установлен")
            return False
        if not os.path.exists(self.vosk_model_path):
            print(f"⚠️ Vosk модель не найдена: {self.vosk_model_path}")
            return False
        try:
            try:
                vosk.SetLogLevel(-1)
            except Exception:
                _log.debug("пропущено в core/wake_word.py (строка 95)")
            old = _silence_fd2()
            try:
                self.vosk_model = vosk.Model(self.vosk_model_path)
            finally:
                _restore_fd2(old)
            return True
        except Exception as e:
            print(f"⚠️ Ошибка загрузки Vosk: {e}")
            return False

    def _load_gigaam(self) -> bool:
        if onnx_asr is None:
            print("⚠️ onnx-asr не установлен")
            return False
        try:
            print("🔄 Загружаю GigaAM (проверка имени)...")
            self.gigaam = onnx_asr.load_model(self.gigaam_model_name)
            print("✅ GigaAM загружена")
            return True
        except Exception as e:
            print(f"⚠️ Ошибка загрузки GigaAM: {e}")
            return False

    # ============================================================
    # СТАРТ / СТОП / ПАУЗА
    # ============================================================
    def start(self) -> bool:
        if self.running:
            return False
        if not self._load_vosk():
            return False
        if not self._load_gigaam():
            return False
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("🎯 Wake-word детектор запущен (Vosk + GigaAM)")
        return True

    def stop(self):
        self.running = False
        time.sleep(0.3)
        self._close_stream()
        time.sleep(0.2)

    def pause(self):
        self._paused = True
        time.sleep(0.2)
        self._close_stream()
        time.sleep(0.8)

    def resume(self):
        self._paused = False

    def _close_stream(self):
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:
            _log.debug("пропущено в core/wake_word.py (строка 156)")
        finally:
            self._stream = None

    def _open_stream(self, callback):
        self._stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self._blocksize,
            dtype="int16",
            channels=1,
            callback=callback,
        )
        self._stream.start()

    # ============================================================
    # GIGAAM-ПРОВЕРКА
    # ============================================================
    def _gigaam_confirm(self) -> bool:
        if self.gigaam is None:
            return True
        if not self._ring:
            return False

        try:
            audio_bytes = b"".join(self._ring)
            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_bytes)
            wav_io.seek(0)

            tmp_path = "data/_gigaam_tmp.wav"
            os.makedirs("data", exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(wav_io.getvalue())

            # БЛОКИРОВКА МОДЕЛИ (с таймаутом, чтобы не зависнуть навсегда)
            result_container = {"text": ""}

            def _recognize():
                try:
                    result_container["text"] = self.gigaam.recognize(tmp_path)
                except Exception:
                    result_container["text"] = ""

            t = threading.Thread(target=_recognize, daemon=True)
            t.start()
            t.join(timeout=5.0)
            if t.is_alive():
                print("⚠️ GigaAM завис на 5 сек — пропускаем проверку")
                text = ""
            else:
                text = result_container.get("text", "")

            if isinstance(text, list):
                text = " ".join(text)
            text = (text or "").lower().strip()
            print(f"🔍 GigaAM проверил: «{text}»")

            for root in self.fuzzy_roots:
                if root in text:
                    return True
            return False
        except Exception as e:
            print(f"⚠️ GigaAM ошибка: {e}")
            return False
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                _log.debug("пропущено в core/wake_word.py (строка 228)")

    # ============================================================
    # ОСНОВНОЙ ЦИКЛ
    # ============================================================
    def _loop(self):
        if sd is None:
            print("⚠️ sounddevice недоступен")
            return

        q = queue.Queue()

        def audio_cb(indata, frames, time_info, status):
            if self._paused:
                return
            data = bytes(indata)
            self._ring.append(data)
            q.put(data)

        grammar_json = json.dumps(self.grammar_words, ensure_ascii=False)

        def new_recognizer():
            old = _silence_fd2()
            try:
                rec = vosk.KaldiRecognizer(
                    self.vosk_model, self.sample_rate, grammar_json
                )
                rec.SetWords(False)
            finally:
                _restore_fd2(old)
            return rec

        try:
            rec = new_recognizer()

            while self.running:
                if self._paused:
                    time.sleep(0.1)
                    continue

                if self._stream is None:
                    try:
                        self._open_stream(audio_cb)
                    except Exception as e:
                        print(f"⚠️ Vosk stream: {e}")
                        time.sleep(0.5)
                        continue

                try:
                    data = q.get(timeout=0.5)
                except queue.Empty:
                    continue

                if not rec.AcceptWaveform(data):
                    continue

                result = json.loads(rec.Result())
                text = (result.get("text") or "").strip().lower()
                rec = new_recognizer()

                if not text or text == "[unk]":
                    continue

                if time.time() - self._last_hit_time < 2.0:
                    continue

                print(f"❓ Vosk зацепился за «{text}» — проверяю...")
                confirmed = self._gigaam_confirm()
                self._ring.clear()

                if not confirmed:
                    print("❌ GigaAM не подтвердил — ложное срабатывание")
                    continue

                self._last_hit_time = time.time()
                self.last_word = text
                print(f"🎯 wake-word ПОДТВЕРЖДЁН: «{text}»")
                self.wake_detected.set()

        except Exception as e:
            print(f"⚠️ Wake-word ошибка: {e}")
        finally:
            self._close_stream()
            self.running = False

    # ============================================================
    # API
    # ============================================================
    def wait_for_wake(self, timeout: float = None) -> bool:
        return self.wake_detected.wait(timeout=timeout)

    def reset(self):
        self.wake_detected.clear()

    def is_wake(self) -> bool:
        return self.wake_detected.is_set()