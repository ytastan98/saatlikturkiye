import os
from instagrapi import Client

IG_USERNAME = "saatlikturkiye"
IG_PASSWORD = "np8ncleb48"
SESSION_FILE = "ig_session.json"

def challenge_code_handler(username, choice):
    """Instagram kod istediğinde terminalden kodu girmene yarar."""
    print(f"\n📩 Instagram ({choice.upper()}) üzerinden doğrulama kodu gönderdi!")
    code = input("👉 Lütfen gelen 6 haneli doğrulama kodunu buraya yazıp Enter'a bas: ")
    return code

cl = Client()

# Instagram güvenlik kodunu terminalden alacak fonksiyonu bağla
cl.challenge_code_handler = challenge_code_handler

print("🔐 Instagram hesabı doğrulanıyor...")

try:
    cl.login(IG_USERNAME, IG_PASSWORD)
    cl.dump_settings(SESSION_FILE)
    print("\n🎉 MÜKEMMEL! Oturum anahtarı başarıyla oluşturuldu.")
    print(f"💾 '{SESSION_FILE}' dosyası klasörüne kaydedildi.")
    print("🚀 Artık bu dosyayı kapatıp ana botu (main.py) çalıştırabilirsin!")

except Exception as e:
    print(f"\n❌ Giriş esnasında bir hata oluştu: {e}")