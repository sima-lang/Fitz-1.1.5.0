from yandex_music import Client

def on_code(code):
    print(f"\n👉 Открой эту ссылку: {code.verification_url}")
    print(f"👉 Введи этот код: {code.user_code}\n")
    print("После подтверждения токен появится ниже...")

client = Client()
token = client.device_auth(on_code=on_code)

print("\n" + "="*50)
print(f"ТВОЙ ТОКЕН (access_token):\n{token.access_token}")
print("="*50)
print("Скопируй его и вставь в конфиг yamusic-tui.")