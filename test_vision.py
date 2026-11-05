"""
test_vision.py — Тест зрения БЕЗ dsh.
Делаем скриншот через mss, сразу отправляем в API.
"""
import os
import base64
import time
from PIL import Image
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

def capture_screen():
    """Делает скриншот всего экрана через mss."""
    try:
        import mss
    except ImportError:
        print("❌ mss не установлен. Выполни: pip install mss pillow")
        return None
    
    with mss.mss() as sct:
        monitor = sct.monitors[1]  # первый монитор
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        temp_path = "test_screenshot.png"
        img.save(temp_path)
        return temp_path

def main():
    print("="*60)
    print("🧪 ТЕСТ ЗРЕНИЯ (через mss, без dsh)")
    print("="*60)

    api_key = os.getenv("API_KEY")
    base_url = os.getenv("API_URL", "https://api.provod.ai/v1")
    
    if not api_key:
        print("❌ Ошибка: API_KEY не найден в .env")
        return

    # 1. Скриншот
    print("\n1️⃣ Делаю скриншот через mss...")
    img_path = capture_screen()
    if not img_path:
        return
    print(f"   ✅ Скриншот сохранён: {img_path}")

    # 2. Отправка в API
    print("\n2️⃣ Отправляю картинку в DeepSeek V4.1 Flash...")
    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        
        with open(img_path, "rb") as f:
            b64_image = base64.b64encode(f.read()).decode("utf-8")

        start_time = time.time()
        
        # Пробуем модели
        models_to_try = [
            "deepseek/deepseek-v4.1-flash",
            "deepseek-flash",
            "deepseek/deepseek-v4-flash"
        ]
        
        response = None
        for model_name in models_to_try:
            try:
                print(f"   🔄 Пробую модель: {model_name}")
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Опиши, что на этом скриншоте. Ответь 1-2 предложениями."},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{b64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=300,
                    extra_body={"thinking": {"type": "disabled"}}
                )
                print(f"   ✅ Модель {model_name} ответила!")
                break
            except Exception as e:
                print(f"      ⚠️ Ошибка с {model_name}: {e}")
                if "model_not_found" not in str(e).lower() and "not found" not in str(e).lower():
                    raise e

        if not response:
            print("   ❌ Ни одна модель не сработала.")
            return

        elapsed = time.time() - start_time
        print(f"\n3️⃣ Ответ получен за {elapsed:.2f} сек:")
        print("-" * 60)
        print(response.choices[0].message.content)
        print("-" * 60)

    except Exception as e:
        print(f"\n❌ Ошибка при запросе к API: {e}")

if __name__ == "__main__":
    main()