from instagrapi import Client

# Tarayıcıdan kopyaladığın sessionid değerini buraya yapıştır
SESSION_ID = "38738040467%3ALZcAGc3M971GAU%3A16%3AAYiTXqFddbhJvkRjeCF7i4EhSto7AYZMJTBfiALYOg"

cl = Client()

try:
    print("⏳ Oturum çerezle doğrulanıyor...")
    # Session ID ile giriş yap
    cl.login_by_sessionid(SESSION_ID)
    
    # Ana botun kullanacağı ig_session.json dosyasını kaydet
    cl.dump_settings("ig_session.json")
    print("\n🎉 HARİKA! 'ig_session.json' dosyası başarıyla oluşturuldu.")
    print("🚀 Artık mail doğrulamasına gerek kalmadan main.py dosyasını çalıştırabilirsin!")

except Exception as e:
    print(f"❌ Hata oluştu: {e}")