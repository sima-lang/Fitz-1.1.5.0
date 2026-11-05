"""
voice.py — Голос Фитца 1.1.5.0 (GigaAM, липсинк, независимая громкость).
Блок 5.5: голосовые эмоции (pitch/rate).
Блок 5.6: дыхание в речи (<break time="400ms"/>).
"""
import os
import io
import re
import time
import wave
import queue
import random
import threading

import numpy as np
from core.logger import get_logger

try:
    import sounddevice as sd
except Exception:
    sd = None

try:
    import torch
except Exception:
    torch = None

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

from . import os_layer
_log = get_logger("voice")

try:
    from .voice_processor import voice_processor
except Exception:
    voice_processor = None


class Voice:
    POST_SPEECH_PAUSE = 0.7

    def __init__(self, speaker: str = "baya", sample_rate: int = 48000):
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.model = None
        self.engine_type = "none"
        self.is_speaking = False
        self.current_volume = 0.0
        self.last_speech_end = 0.0
        self.volume = 1.0
        self._lock = threading.Lock()
        self._queue = queue.Queue()
        self._stop_worker = False
        self._gigaam = None

        self._init_engine()
        self._start_worker()

    def _init_engine(self):
        if torch is not None and sd is not None:
            try:
                cache_dir = os.path.abspath("data/models")
                os.makedirs(cache_dir, exist_ok=True)
                os.environ.setdefault("TORCH_HOME", cache_dir)
                self.model, _ = torch.hub.load(
                    repo_or_dir="snakers4/silero-models",
                    model="silero_tts",
                    language="ru",
                    speaker="v3_1_ru",
                )
                self.model.to(torch.device("cpu"))
                self.engine_type = "silero"
                print(f"✅ Голос: Silero TTS загружен (speaker={self.speaker})")
                return
            except Exception as e:
                print(f"⚠️ Silero не загрузился: {e}")

        if pyttsx3 is not None:
            try:
                self._pyttsx3 = pyttsx3.init()
                self.engine_type = "pyttsx3"
                print("✅ Голос: pyttsx3 (fallback)")
                return
            except Exception as e:
                print(f"⚠️ pyttsx3 не загрузился: {e}")

        if os_layer.is_linux():
            import shutil
            if shutil.which("espeak") or shutil.which("espeak-ng"):
                self.engine_type = "espeak"
                print("✅ Голос: espeak (fallback)")
                return

        self.engine_type = "none"
        print("⚠️ Голосовой движок недоступен — только текстовый вывод")

    def _start_worker(self):
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while not self._stop_worker:
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            # ===== Блок 5.5: очередь хранит (text, pitch, rate) =====
            if isinstance(item, tuple) and len(item) == 3:
                text, pitch, rate = item
            else:
                text, pitch, rate = item, "high", "medium"
            self._speak_now(text, pitch=pitch, rate=rate)

    def speak(self, text: str, pitch: str = "high", rate: str = "medium"):
        if not text:
            _log.info("voice drop: пустой текст до нормализации")
            return
        raw_len = len(text)
        text = self._normalize(text)
        if not text:
            _log.info("voice drop: пустой после нормализации (исходно %d симв.)", raw_len)
            return
        self.is_speaking = True
        self._queue.put((text, pitch, rate))
        _log.info("voice enqueue: %d симв., engine=%s, очередь=%d",
                  len(text), self.engine_type, self._queue.qsize())

    def speak_blocking(self, text: str, pitch: str = "high", rate: str = "medium"):
        if not text:
            return
        text = self._normalize(text)
        if not text:
            return
        self.is_speaking = True
        self._speak_now(text, pitch=pitch, rate=rate)

    def wait(self, timeout: float = None):
        start = time.time()
        while not self._queue.empty() or self.is_speaking:
            if timeout and (time.time() - start) > timeout:
                return
            time.sleep(0.05)

    def _speak_now(self, text: str, pitch: str = "high", rate: str = "medium"):
        _t0 = time.time()
        try:
            if not text or not text.strip():
                _log.info("voice drop: пустой текст в _speak_now")
                return
            _log.info("voice start: %d симв., engine=%s", len(text), self.engine_type)
            with self._lock:
                self.is_speaking = True
                if self.engine_type == "silero":
                    # ===== Блок 5.5: pitch/rate из параметров =====
                    # 1.6.0: авто-rate по длине текста
                    word_count = len(text.split())
                    if rate == "medium":
                        if word_count > 50:
                            rate = "slow"
                        elif word_count < 10:
                            rate = "medium"
                    # Нормализация: паузы между словами для Silero
                    if "<break" not in text:
                        ssml_text = re.sub(r"(\w)\s+(\w)", r"\1 <break time='80ms'/> \2", text)
                        text = ssml_text
                    if not text.strip().startswith("<speak>"):
                        text = (
                            f'<speak><prosody pitch="{pitch}" rate="{rate}">'
                            f'{text}</prosody></speak>'
                        )

                    audio = self.model.apply_tts(
                        text=text,
                        speaker=self.speaker,
                        sample_rate=self.sample_rate,
                    )
                    if hasattr(audio, 'numpy'):
                        audio = audio.numpy()
                    audio = np.asarray(audio, dtype=np.float32)

                    audio = audio * self.volume

                    import sounddevice as _sd
                    _sd.play(audio, self.sample_rate, blocking=False)

                    chunk_size = int(self.sample_rate * 0.05)
                    total = len(audio)
                    pos = 0
                    while pos < total:
                        chunk = audio[pos:pos+chunk_size]
                        if len(chunk) == 0:
                            break
                        rms = float(np.sqrt(np.mean(chunk ** 2)))
                        self.current_volume = min(1.0, rms * 5.0)
                        pos += chunk_size
                        time.sleep(0.05)

                    try:
                        while _sd.get_stream().active:
                            time.sleep(0.05)
                        time.sleep(0.15)
                    except Exception:
                        _log.debug("пропущено в core/voice.py (строка 204)")

                    self.current_volume = 0.0

                elif self.engine_type == "pyttsx3":
                    self._pyttsx3.say(text)
                    self._pyttsx3.runAndWait()
                elif self.engine_type == "espeak":
                    import subprocess
                    import shutil as _shutil
                    exe = "espeak-ng" if _shutil.which("espeak-ng") else "espeak"
                    subprocess.run([exe, "-v", "ru", "-s", "160", text],
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"⚠️ Ошибка озвучки: {e}")
        finally:
            time.sleep(0.2)
            self.is_speaking = False
            self.current_volume = 0.0
            self.last_speech_end = time.time()
            _log.info("voice finish: %d симв., %.2f с", len(text or ""), time.time() - _t0)

    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        if voice_processor is not None:
            try:
                text = voice_processor.process(text)
            except Exception:
                _log.debug("пропущено в core/voice.py (строка 233)")

        # 1.6.0: замена сокращений перед удалением символов
        abbreviations = {
            r'\bт\.е\.': 'то есть',
            r'\bт\.д\.': 'так далее',
            r'\bт\.п\.': 'тому подобное',
            r'\bи т\.д\.': 'и так далее',
            r'\bи т\.п\.': 'и тому подобное',
            r'\bдр\.': 'другие',
            r'\bпр\.': 'прочее',
            r'\bсм\.': 'смотри',
            r'\bнапр\.': 'например',
            r'\bок\.': 'около',
        }
        for pattern, replacement in abbreviations.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        # Смайлики не читаем — Silero их не произносит, эмоции передаются через Haru
        text = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", " ", text)
        # Комментарии в звёздочках (*подмигиваю*) — не озвучиваем
        text = re.sub(r"\*[^*\n]{1,60}\*", " ", text)
        # Удаление символов, мешающих озвучке
        text = re.sub(r"[^\w\s\.\,\!\?\-\:\(\)]", " ", text)
        # Схлопываем множественные пробелы
        text = re.sub(r"\s+", " ", text).strip()
        # Удаляем множественные знаки препинания
        text = re.sub(r'([.!?])\1+', r'\1', text)
        text = re.sub(r'\.{3,}', '…', text)  # многоточие → пауза

        # ===== Блок 5.6: дыхание между предложениями (усилено) =====
        text = re.sub(r'([.!?…])\s+', r'\1 <break time="400ms"/> ', text)
        # Запятые — короткая пауза
        text = re.sub(r',\s+', r', <break time="150ms"/> ', text)
        return text.strip()

    def _can_listen(self) -> bool:
        if self.is_speaking:
            return False
        if not self._queue.empty():
            return False
        if (time.time() - self.last_speech_end) < self.POST_SPEECH_PAUSE:
            return False
        return True

    def _gigaam_recognize(self, wav_path: str, wake_detector=None) -> str:
        try:
            import onnx_asr
            model = None
            lock = None
            if wake_detector and hasattr(wake_detector, "gigaam") and wake_detector.gigaam:
                model = wake_detector.gigaam
                lock = getattr(wake_detector, "gigaam_lock", None)
            elif self._gigaam is not None:
                model = self._gigaam
            else:
                print("🔄 Загружаю GigaAM для команд...")
                self._gigaam = onnx_asr.load_model("gigaam-v3-rnnt")
                model = self._gigaam
                print("✅ GigaAM для команд готова")

            if lock:
                with lock:
                    text = model.recognize(wav_path)
            else:
                text = model.recognize(wav_path)

            if isinstance(text, list):
                text = " ".join(text)
            return (text or "").strip()
        except Exception as e:
            print(f"⚠️ GigaAM ошибка: {e}")
            return ""

    def listen_continuous(self, callback, wake_detector=None):
        if sd is None:
            print("⚠️ Слух недоступен: нет sounddevice.")
            return

        MIC_DEVICE = getattr(wake_detector, "device", None) if wake_detector else None
        sample_rate = 16000
        chunk_duration = 0.3
        chunk_samples = int(chunk_duration * sample_rate)

        print("🎤 Калибровка микрофона (2 сек тишины)...")
        try:
            cal = sd.rec(int(2 * sample_rate), samplerate=sample_rate,
                         channels=1, dtype="int16", device=MIC_DEVICE)
            sd.wait()
            cal_rms = float(np.sqrt(np.mean(cal.astype(np.float32) ** 2)))
        except Exception as e:
            print(f"⚠️ Калибровка не удалась: {e}. Порог 2000.")
            cal_rms = 1100.0

        silence_threshold = max(1500.0, min(cal_rms * 1.8, 15000.0))
        silence_duration = 1.2
        print(f"🎤 Шум тишины: {cal_rms:.0f}, порог речи: {silence_threshold:.0f}")

        def record_phrase():
            buf = []
            silent = 0
            speaking = False

            def audio_cb(indata, frames, time_info, status):
                nonlocal buf, silent, speaking
                if status:
                    pass
                if self.is_speaking or not self._queue.empty():
                    buf = []
                    silent = 0
                    speaking = False
                    return
                chunk = indata.copy()
                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))
                if rms > silence_threshold:
                    speaking = True
                    silent = 0
                    buf.append(chunk)
                else:
                    if speaking:
                        silent += 1
                        buf.append(chunk)

            stream = sd.InputStream(
                samplerate=sample_rate, channels=1, dtype="int16",
                blocksize=chunk_samples, callback=audio_cb,
                device=MIC_DEVICE,
            )
            stream.start()
            start = time.time()
            try:
                while time.time() - start < 6.0:
                    time.sleep(0.05)
                    if speaking and silent >= int(silence_duration / chunk_duration):
                        break
            finally:
                stream.stop()
                stream.close()

            if not buf:
                return None

            audio_data = np.concatenate(buf)
            rms = float(np.sqrt(np.mean(audio_data.astype(np.float32) ** 2)))
            if rms < silence_threshold * 0.7:
                return None

            wav_io = io.BytesIO()
            with wave.open(wav_io, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data.tobytes())
            wav_io.seek(0)
            return wav_io

        while not self._stop_worker:
            if wake_detector is not None:
                if not wake_detector.wait_for_wake(timeout=0.5):
                    continue
                wake_detector.reset()
                wake_detector.pause()
                time.sleep(0.8)
                print("🎯 wake-word получен, слушаю команду...")

                self.speak(random.choice([
                    "Слушаю, создатель.",
                    "Да, я здесь.",
                    "Ты меня звал?",
                    "Я на связи.",
                ]))
                self.wait(timeout=2)

                try:
                    MAX_ATTEMPTS = 3
                    got_text = False

                    for attempt in range(MAX_ATTEMPTS):
                        print(f"🎤 попытка {attempt + 1}/{MAX_ATTEMPTS}...")
                        wav_io = record_phrase()

                        if wav_io is None:
                            print("⚠️ тишина (record_phrase → None)")
                            if attempt < MAX_ATTEMPTS - 1:
                                self.speak("Не расслышал. Повтори.")
                                self.wait(timeout=2)
                            else:
                                self.speak("Ладно, потом.")
                            continue

                        tmp_wav = "data/_cmd_tmp.wav"
                        try:
                            with open(tmp_wav, "wb") as f:
                                f.write(wav_io.getvalue())

                            text = self._gigaam_recognize(tmp_wav, wake_detector=wake_detector)

                            if os.path.exists(tmp_wav):
                                os.remove(tmp_wav)

                            if text:
                                print(f"🎤 распознано (GigaAM): «{text}»")
                                callback(text.lower())
                                got_text = True
                                break
                            else:
                                print("⚠️ GigaAM не распознал")
                                if attempt < MAX_ATTEMPTS - 1:
                                    self.speak("Не расслышал. Повтори.")
                                    self.wait(timeout=2)
                                else:
                                    self.speak("Ладно, потом.")
                        except Exception as e:
                            print(f"⚠️ Ошибка распознавания: {e}")
                            if os.path.exists(tmp_wav):
                                os.remove(tmp_wav)
                            break

                    if not got_text:
                        print("⚠️ Все попытки исчерпаны")
                finally:
                    wake_detector.resume()
            else:
                if not self._can_listen():
                    time.sleep(0.15)
                    continue

                wav_io = record_phrase()
                if wav_io is None:
                    continue

                tmp_wav = "data/_cmd_tmp.wav"
                try:
                    with open(tmp_wav, "wb") as f:
                        f.write(wav_io.getvalue())
                    text = self._gigaam_recognize(tmp_wav, wake_detector=wake_detector)
                    if os.path.exists(tmp_wav):
                        os.remove(tmp_wav)
                    if text:
                        callback(text.lower())
                except Exception as e:
                    print(f"⚠️ Ошибка: {e}")
                    if os.path.exists(tmp_wav):
                        os.remove(tmp_wav)

    def set_speaker(self, name: str):
        valid = ("xenia", "aidar", "baya", "kseniya", "eugene")
        if name in valid:
            self.speaker = name
            return f"🎤 Голос: {name}"
        return f"❌ Голос '{name}' не найден."

    def get_status(self) -> dict:
        return {
            "engine": self.engine_type,
            "speaker": self.speaker,
            "mic": sd is not None,
        }

    def stop(self):
        self._stop_worker = True
        try:
            self._queue.put(None)
        except Exception:
            _log.debug("пропущено в core/voice.py (строка 493)")
        try:
            for _ in range(30):
                if not self.is_speaking:
                    break
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass