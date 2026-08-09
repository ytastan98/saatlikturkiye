import requests

# Kendi Bot Token'ını buraya yaz
BOT_TOKEN = "8826516975:AAHOOUjMmDcxnqCO7mUj-e6YHmrSrRoH18c"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
response = requests.get(url).json()

try:
    # Son gelen mesajdan Chat ID'yi çek
    results = response.get("result", [])
    if results:
        chat_id = results[-1]["message"]["chat"]["id"]
        chat_title = results[-1]["message"]["chat"].get("title", "Grup")
        print(f"✅ BULUNDU!")
        print(f"Grup Adı: {chat_title}")
        print(f"Chat ID: {chat_id}")
    else:
        print("⚠️ Henüz mesaj bulunamadı. Kodu çalıştırmadan önce gruba herhangi bir mesaj atın.")
except Exception as e:
    print(f"❌ Bir hata oluştu: {e}")