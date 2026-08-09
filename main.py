import json
import textwrap
import time
import os
import re
import subprocess
from datetime import datetime
import requests
import feedparser
from PIL import Image, ImageDraw, ImageFont
from instagrapi import Client
from dotenv import load_dotenv

load_dotenv()

# ==========================================
# AYARLAR & API BİLGİLERİ (.env)
# ==========================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "-1004464489545")
INSTAGRAM_SESSION_ID = os.getenv("INSTAGRAM_SESSION_ID")

KANAL_ADI = "@saatlikturkiye"
WEBSITE_URL = "saatlikturkiye.com"

RSS_LISTE = [
    "https://www.aa.com.tr/tr/rss/default?cat=guncel",
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.ntv.com.tr/gundem.rss",
    "https://www.ensonhaber.com/rss/ensonhaber.xml"
]

HAFIZA_DOSYASI = "paylasilan_haberler.json"
WEB_JSON_DOSYASI = "public/news.json"
TG_OUTPUT_IMAGE = "kusursuz_gundem_telegram.png"
IG_OUTPUT_IMAGE = "kusursuz_gundem_instagram.png"

# ==========================================
# GERÇEK HABER GÖRSELİNİ RSS'DEN ÇEKME
# ==========================================
def gorsel_url_bul(entry):
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image'):
                return enc.get('href')

    if hasattr(entry, 'media_content') and entry.media_content:
        return entry.media_content[0].get('url')
    if hasattr(entry, 'media_thumbnail') and entry.media_thumbnail:
        return entry.media_thumbnail[0].get('url')

    metin = getattr(entry, 'summary', '') + getattr(entry, 'description', '')
    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', metin)
    if match:
        return match.group(1)

    return "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800&q=80"

# ==========================================
# HAFIZA İŞLEMLERİ
# ==========================================
def hafizayi_yukle():
    if os.path.exists(HAFIZA_DOSYASI):
        try:
            with open(HAFIZA_DOSYASI, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def hafizaya_kaydet(yeni_basliklar):
    hafiza = hafizayi_yukle()
    for b in yeni_basliklar:
        temiz = re.sub(r'[^\w\s]', '', b.lower().strip())
        hafiza.add(temiz)
    with open(HAFIZA_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(list(hafiza)[-300:], f, ensure_ascii=False, indent=2)

def haber_daha_once_paylasildi_mi(baslik, hafiza):
    temiz = re.sub(r'[^\w\s]', '', baslik.lower().strip())
    for kayitli in hafiza:
        if temiz in kayitli or kayitli in temiz:
            return True
    return False

# ==========================================
# 1. HABER ÇEKME VE AI ÖZETLEME (4 HABER)
# ==========================================
def haberleri_cek_ve_ozetle():
    print("🌐 1. RSS kaynaklarından haberler taranıyor...")
    hafiza = hafizayi_yukle()
    haber_havuzu = ""
    ham_haberler = []
    eklenen_sayi = 0

    for rss_url in RSS_LISTE:
        try:
            feed = feedparser.parse(rss_url)
            for entry in feed.entries[:8]:
                baslik = entry.title.strip()
                ozet = getattr(entry, 'summary', '')
                link = getattr(entry, 'link', WEBSITE_URL)
                gorsel = gorsel_url_bul(entry)
                
                if haber_daha_once_paylasildi_mi(baslik, hafiza):
                    continue
                
                eklenen_sayi += 1
                haber_havuzu += f"{eklenen_sayi}. Başlık: {baslik}\nÖzet/Detay: {ozet}\n\n"
                
                ham_haberler.append({
                    "id": eklenen_sayi,
                    "orijinal_baslik": baslik,
                    "link": link,
                    "gorsel": gorsel,
                    "kaynak": feed.feed.get('title', 'Basın Bülteni')
                })
                
                if eklenen_sayi >= 15:
                    break
        except Exception as e:
            print(f"⚠️ RSS Okuma Hatası ({rss_url}): {e}")
            continue

    if eklenen_sayi < 3:
        print("⚠️ Yeterli yeni haber bulunamadı.")
        return None, None

    print(f"✅ {eklenen_sayi} yeni haber toplandı. AI özetliyor...")

    prompt = f"""Aşağıdaki haber havuzunu incele ve en önemli 4 haberi seç.

    ÇOK ÖNEMLİ VE KESİN KURALLAR:
    1. 'baslik' alanı olayı net anlatan tam bir haber başlığı olsun.
    2. 'kisa_aciklama' alanı KESİNLİKLE BAŞLIĞIN BİREBİR TEKRARI OLMASIN! Olayın detayını, nedenini veya arka planını anlatan TAM 2 veya 3 CÜMLE (yaklaşık 120-150 karakter) olsun. Her cümlenin sonuna nokta (.) koy!
    3. 'detay' alanı Instagram açıklaması için 3-4 cümlelik detaylı metin olsun. Cümle sonlarına mutlaka nokta koy.
    4. KESİNLİKLE çift tırnak (") KULLANMA! Tırnak gerekirse tek tırnak (') kullan.

    SADECE geçerli JSON formatı döndür:
    {{
      "maddeler": [
        {{
          "id": 1,
          "baslik": "Netanyahu Ateşkes Planını Reddetti",
          "kisa_aciklama": "İsrail Başbakanı Netanyahu, sunulan son teklifin şartları karşılamadığını belirterek anlaşmayı imzalamadı. Karar sonrası bölgedeki gerilim yeniden tırmanışa geçti. Uluslararası kamuoyundan tepkiler yükseliyor.",
          "detay": "İsrail Başbakanı Binyamin Netanyahu, Hamas ile yürütülen müzakerelerde sunulan yeni ateşkes taslağını kabul etmediğini duyurdu. Güvenlik kabinesiyle yapılan toplantının ardından açıklama yapan yetkililer, askeri operasyonların devam edeceğini bildirdi.",
          "kategori": "ULUSLARARASI"
        }}
      ]
    }}

    Haber Havuzu:
    {haber_havuzu}"""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a senior news editor. Select exactly 4 key news items. Never repeat the news title inside the short summary."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            clean_json = response.json()['choices'][0]['message']['content']
            ai_data = json.loads(clean_json).get("maddeler", [])
            
            web_news_list = []
            islenen_basliklar = []
            simdi_str = datetime.now().strftime("%d %b %Y - %H:%M")

            for item in ai_data[:4]:
                item_id = item.get("id", 1)
                matching_raw = ham_haberler[item_id - 1] if item_id <= len(ham_haberler) else ham_haberler[0]
                
                web_news_list.append({
                    "id": item_id,
                    "category": item.get("kategori", "GÜNDEM"),
                    "title": item.get("baslik"),
                    "summary": item.get("kisa_aciklama"),
                    "fullText": f"<p>{item.get('detay')}</p>",
                    "image": matching_raw["gorsel"],
                    "source": matching_raw["kaynak"],
                    "sourceUrl": matching_raw["link"],
                    "date": simdi_str
                })
                islenen_basliklar.append(item.get("baslik"))

            os.makedirs(os.path.dirname(WEB_JSON_DOSYASI), exist_ok=True)

            with open(WEB_JSON_DOSYASI, "w", encoding="utf-8") as wf:
                json.dump(web_news_list, wf, ensure_ascii=False, indent=2)
            
            hafizaya_kaydet(islenen_basliklar)
            print("🌐 'public/news.json' başarıyla üretildi.")
            return ai_data[:4], web_news_list
    except Exception as e:
        print(f"❌ AI İşleme Hatası: {e}")
        return None, None

# ==========================================
# 2. BÜYÜTÜLMÜŞ FONT & 4 KARTLI GÖRSEL ÇİZİMİ
# ==========================================
# ==========================================
# 1. AI PROMPT GÜNCELLEMESİ (Haber Özeti Sınırı)
# ==========================================
# prompt değişkeni içindeki kisa_aciklama kuralını şu şekilde tutun:
# "kisa_aciklama": "Olayın detayını anlatan TAM 130-160 KARAKTER (yaklaşık 2 net cümle) yaz. Cümle sonuna nokta koy!"


# ==========================================
# 2. GÖRSEL ÇİZİM İŞLEMLERİ (Yeni Fontlar Uyumlu)
# ==========================================
def gorsel_olustur(ai_maddeler):
    print("🎨 Görseller yeni font boyutlarıyla çiziliyor...")
    
    def ciz(genislik, yukseklik, dosya_adi):
        img = Image.new("RGB", (genislik, yukseklik), color="#000000")
        draw = ImageDraw.Draw(img)
        
        try:
            font_logo = ImageFont.truetype("arialbd.ttf", 36)
            font_kategori = ImageFont.truetype("arialbd.ttf", 25)
            font_baslik = ImageFont.truetype("arialbd.ttf", 28)
            font_metin = ImageFont.truetype("arial.ttf", 25)
            font_footer = ImageFont.truetype("arialbd.ttf", 20)
        except Exception:
            font_logo = font_kategori = font_baslik = font_metin = font_footer = ImageFont.load_default()

        # Header (Üst Bar)
        draw.rectangle([(0, 0), (genislik, 95)], fill="#0d0d0d")
        draw.line([(0, 95), (genislik, 95)], fill="#e11d48", width=3)
        
        draw.text((40, 26), "SAATLİK", fill="#ffffff", font=font_logo)
        draw.text((225, 26), "TÜRKİYE", fill="#e11d48", font=font_logo)
        
        tarih_str = datetime.now().strftime("%d.%m.%Y  |  %H:%M")
        draw.text((genislik - 260, 34), tarih_str, fill="#f4f4f5", font=font_footer)

        # 4 Kart Düzeni (Yüksek Fontlara Göre Genişletilmiş)
        y_offset = 110
        kart_yukseklik = 215

        for i, item in enumerate(ai_maddeler[:4], 1):
            # Kart Arka Planı
            draw.rectangle([(30, y_offset), (genislik - 30, y_offset + kart_yukseklik)], fill="#111113", outline="#27272a", width=1)
            draw.rectangle([(30, y_offset), (38, y_offset + kart_yukseklik)], fill="#2563eb")
            
            # Kategori Etiketi (25px)
            kat_text = f"#{i}  {item.get('kategori', 'GÜNDEM').upper()}"
            draw.text((55, y_offset + 10), kat_text, fill="#60a5fa", font=font_kategori)
            
            # Başlık (28px - Kartın sağına kadar uzanır)
            baslik_satirlar = textwrap.wrap(item.get("baslik", ""), width=45)
            line_y = y_offset + 42
            for line in baslik_satirlar[:2]:
                draw.text((55, line_y), line, fill="#ffffff", font=font_baslik)
                line_y += 34

            # Nokta Kontrolü
            aciklama = item.get("kisa_aciklama", "").strip()
            if aciklama and aciklama[-1] not in [".", "!", "?"]:
                aciklama += "."

            # Açıklama Metni (25px - width=65 yapılarak sağ boşluk kapatıldı)
            ozet_satirlar = textwrap.wrap(aciklama, width=65)
            line_y += 6
            for ozet_line in ozet_satirlar[:3]:
                draw.text((55, line_y), ozet_line, fill="#d4d4d8", font=font_metin)
                line_y += 30

            y_offset += kart_yukseklik + 12

        # Footer (Alt Bar)
        draw.rectangle([(0, yukseklik - 55), (genislik, yukseklik)], fill="#0d0d0d")
        draw.line([(0, yukseklik - 55), (genislik, yukseklik - 55)], fill="#27272a", width=1)
        
        draw.text((40, yukseklik - 38), f"🌐 {WEBSITE_URL.upper()}", fill="#ffffff", font=font_footer)
        draw.text((genislik - 340, yukseklik - 38), f"📢 Telegram: {KANAL_ADI}", fill="#38bdf8", font=font_footer)

        img.save(dosya_adi)

    ciz(1080, 1080, TG_OUTPUT_IMAGE)
    ciz(1080, 1080, IG_OUTPUT_IMAGE)
    print("🎨 2. Görseller çiziliyor (Büyük fontlu 4 kart)...")
    
    def ciz(genislik, yukseklik, dosya_adi):
        img = Image.new("RGB", (genislik, yukseklik), color="#000000")
        draw = ImageDraw.Draw(img)
        
        try:
            font_logo = ImageFont.truetype("arialbd.ttf", 36)
            font_kategori = ImageFont.truetype("arialbd.ttf", 25) # Büyütüldü
            font_baslik = ImageFont.truetype("arialbd.ttf", 28)   # Büyütüldü
            font_metin = ImageFont.truetype("arial.ttf", 25)      # Büyütüldü
            font_footer = ImageFont.truetype("arialbd.ttf", 20)
        except Exception:
            font_logo = font_kategori = font_baslik = font_metin = font_footer = ImageFont.load_default()

        # Header
        draw.rectangle([(0, 0), (genislik, 95)], fill="#0d0d0d")
        draw.line([(0, 95), (genislik, 95)], fill="#e11d48", width=3)
        
        draw.text((40, 28), "SAATLİK", fill="#ffffff", font=font_logo)
        draw.text((225, 28), "TÜRKİYE", fill="#e11d48", font=font_logo)
        
        tarih_str = datetime.now().strftime("%d.%m.%Y  |  %H:%M")
        draw.text((genislik - 240, 36), tarih_str, fill="#f4f4f5", font=font_footer)

        # 4 Kart için Y Düzeneği (Daha geniş kartlar)
        y_offset = 115
        kart_yukseklik = 210  # Kartlar genişletildi

        for i, item in enumerate(ai_maddeler[:4], 1):
            # Kart Arka Planı
            draw.rectangle([(30, y_offset), (genislik - 30, y_offset + kart_yukseklik)], fill="#111113", outline="#27272a", width=1)
            draw.rectangle([(30, y_offset), (37, y_offset + kart_yukseklik)], fill="#2563eb")
            
            # Kategori Etiketi
            kat_text = f"#{i}  {item.get('kategori', 'GÜNDEM').upper()}"
            draw.text((55, y_offset + 12), kat_text, fill="#60a5fa", font=font_kategori)
            
            # Başlık (Büyük Font)
            baslik_satirlar = textwrap.wrap(item.get("baslik", ""), width=56)
            line_y = y_offset + 38
            for line in baslik_satirlar[:2]:
                draw.text((55, line_y), line, fill="#ffffff", font=font_baslik)
                line_y += 28

            # Nokta Kontrolü
            aciklama = item.get("kisa_aciklama", "").strip()
            if aciklama and aciklama[-1] not in [".", "!", "?"]:
                aciklama += "."

            # Açıklama Metni (Büyük Font)
            ozet_satirlar = textwrap.wrap(aciklama, width=70)
            line_y += 6
            for ozet_line in ozet_satirlar[:3]:
                draw.text((55, line_y), ozet_line, fill="#d4d4d8", font=font_metin)
                line_y += 23

            y_offset += kart_yukseklik + 15  # Kart arası boşluk

        # Footer
        draw.rectangle([(0, yukseklik - 55), (genislik, yukseklik)], fill="#0d0d0d")
        draw.line([(0, yukseklik - 55), (genislik, yukseklik - 55)], fill="#27272a", width=1)
        
        draw.text((40, yukseklik - 38), f"🌐 {WEBSITE_URL.upper()}", fill="#ffffff", font=font_footer)
        draw.text((genislik - 320, yukseklik - 38), f"📢 Telegram: {KANAL_ADI}", fill="#38bdf8", font=font_footer)

        img.save(dosya_adi)

    ciz(1080, 1080, TG_OUTPUT_IMAGE)
    ciz(1080, 1080, IG_OUTPUT_IMAGE)
    print("✅ Görseller büyük fontlarla başarıyla oluşturuldu.")

# ==========================================
# 3. TELEGRAM PAYLAŞIMI
# ==========================================
def telegram_paylas(ai_maddeler):
    print("✈️ 3. Telegram'a gönderiliyor...")
    caption = f"🔴 **SAATLİK TÜRKİYE — SON DAKİKA GÜNDEM**\n\n"
    caption += f"🌐 Canlı haber akışı ve detaylar: {WEBSITE_URL}\n"
    caption += f"📢 Resmi Kanalımız: {KANAL_ADI}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(TG_OUTPUT_IMAGE, "rb") as photo:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            files = {"photo": photo}
            res = requests.post(url, data=payload, files=files)
            if res.status_code == 200:
                print("✅ Telegram paylaşımı BAŞARILI!")
            else:
                print(f"❌ Telegram Hatası: {res.text}")
    except Exception as e:
        print(f"❌ Telegram İstek Hatası: {e}")

# ==========================================
# 4. INSTAGRAM PAYLAŞIMI
# ==========================================
def instagram_paylas(ai_maddeler):
    print("📸 4. Instagram'a gönderiliyor...")
    if not INSTAGRAM_SESSION_ID:
        print("⚠️ Instagram Session ID bulunamadı.")
        return

    caption = "🔴 SAATLİK TÜRKİYE — GÜNÜN ÖNE ÇIKAN HABERLERİ\n\n"
    for i, item in enumerate(ai_maddeler[:4], 1):
        detay_metni = item.get('detay', '').strip()
        if detay_metni and detay_metni[-1] not in [".", "!", "?"]:
            detay_metni += "."
            
        caption += f"📌 {i}. {item.get('baslik').upper()}\n"
        caption += f"{detay_metni}\n\n"
    
    caption += f"🔗 Tüm haberlerin detayları ve canlı akış için biyografideki linke tıklayın! ({WEBSITE_URL})\n\n#sondakika #haber #gundem #turkiye #saatlikturkiye"

    try:
        cl = Client()
        cl.login_by_sessionid(INSTAGRAM_SESSION_ID)
        cl.photo_upload(IG_OUTPUT_IMAGE, caption)
        print("✅ Instagram paylaşımı BAŞARILI!")
    except Exception as e:
        print(f"⚠️ Instagram Paylaşım Hatası (Akış devam ediyor): {e}")

# ==========================================
# 5. VERCEL WEB SİTESİ GÜNCELLEME
# ==========================================
def git_vercel_guncelle():
    print("🚀 5. Web sitesi Vercel üzerine aktarılıyor...")
    try:
        subprocess.run(["git", "add", WEB_JSON_DOSYASI], check=True)
        commit_msg = f"Auto news update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("⚡ GitHub Push tamamlandı. Vercel siteyi canlıya alıyor!")
    except subprocess.CalledProcessError as e:
        print(f"ℹ️ Git güncelleme uyarısı (Değişiklik olmamış olabilir): {e}")
    except Exception as e:
        print(f"❌ Vercel Güncelleme Hatası: {e}")

# ==========================================
# 6. OTO-DÖNGÜ ÇALIŞTIRICI
# ==========================================
def gorevi_calistir():
    print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Yeni tarama döngüsü başladı...")
    ai_maddeler, web_news = haberleri_cek_ve_ozetle()
    
    if ai_maddeler:
        gorsel_olustur(ai_maddeler)
        telegram_paylas(ai_maddeler)
        instagram_paylas(ai_maddeler)
        git_vercel_guncelle()
        print("🎉 Bu saatlik tur tamamlandı.")
    else:
        print("ℹ️ Yeni paylaşılan haber yok veya sınır dolmadı.")

if __name__ == "__main__":
    print("🚀 SAATLİK TÜRKİYE BOTU CANLIYA ALINDI.")
    print("🔄 Bot kesintisiz olarak her 1 saatte bir çalışacak...")
    
    while True:
        try:
            gorevi_calistir()
        except Exception as global_err:
            print(f"❌ Beklenmeyen sistem hatası: {global_err}")
            
        print("⏳ 1 saat boyunca bekleniyor (Sonraki tarama otomatik yapılacak)...\n")
        time.sleep(3600)