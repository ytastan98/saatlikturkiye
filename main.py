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
# KATEGORİ TÜRKÇE DÜZELTİCİ
# ==========================================
def kategori_duzelt(kat):
    if not kat:
        return "GÜNDEM"
    kat = kat.strip().upper()
    mapping = {
        "SUC": "SUÇ",
        "TRAFIG": "TRAFİK",
        "TRAFIK": "TRAFİK",
        "EKONOMI": "EKONOMİ",
        "IC HABERLER": "İÇ HABERLER",
        "SAGLIK": "SAĞLIK",
        "EGITIM": "EĞİTİM",
        "POLITIKA": "POLİTİKA",
        "DUNYA": "DÜNYA",
        "TEKNOLOJI": "TEKNOLOJİ",
        "SPOR": "SPOR",
        "MAGAZIN": "MAGAZİN"
    }
    return mapping.get(kat, kat)

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
        json.dump(list(hafiza)[-500:], f, ensure_ascii=False, indent=2)

def haber_daha_once_paylasildi_mi(baslik, hafiza):
    temiz = re.sub(r'[^\w\s]', '', baslik.lower().strip())
    for kayitli in hafiza:
        if temiz in kayitli or kayitli in temiz:
            return True
    return False

# ==========================================
# HABER ÇEKME VE ARŞİV BİRİKTİRME
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

    ÇOK ÖNEMLİ KURALLAR:
    1. 'kisa_aciklama' alanı TAM 130-160 KARAKTER (yaklaşık 2 net cümle) olsun. Kesinlikle yarım bırakma ve nokta (.) koy!
    2. 'kategori' alanını tam Türkçe büyük harflerle yaz (Örn: SUÇ, TRAFİK, EKONOMİ, İÇ HABERLER, DÜNYA, SAĞLIK, EĞİTİM, POLİTİKA, SPOR). Sakın 'SUC' veya 'TRAFIG' yazma!
    3. KESİNLİKLE çift tırnak (") KULLANMA!

    SADECE geçerli JSON formatı döndür:
    {{
      "maddeler": [
        {{
          "id": 1,
          "baslik": "Netanyahu Ateşkes Planını Reddetti",
          "kisa_aciklama": "İsrail Başbakanı Netanyahu, sunulan son teklifin şartları karşılamadığını belirterek anlaşmayı imzalamadı. Bölgedeki gerilim yeniden tırmanışa geçti.",
          "detay": "İsrail Başbakanı Binyamin Netanyahu, Hamas ile yürütülen müzakerelerde sunulan yeni ateşkes taslağını kabul etmediğini duyurdu.",
          "kategori": "DÜNYA"
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
            {"role": "system", "content": "You are a senior Turkish news editor."},
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
            
            yeni_web_haberleri = []
            islenen_basliklar = []
            simdi_str = datetime.now().strftime("%d.%m.%Y - %H:%M")

            for item in ai_data[:4]:
                item_title = item.get("baslik", "").lower()
                
                # Akıllı Eşleştirme: AI başlığı ile orijinal RSS başlığı arasındaki kelimeleri karşılaştırır
                best_match = ham_haberler[0]
                max_score = 0
                
                for raw in ham_haberler:
                    raw_title = raw["orijinal_baslik"].lower()
                    # Ortak kelime sayısını bul
                    score = sum(1 for word in item_title.split() if len(word) > 3 and word in raw_title)
                    if score > max_score:
                        max_score = score
                        best_match = raw

                temiz_kategori = kategori_duzelt(item.get("kategori"))
                item["kategori"] = temiz_kategori
                
                yeni_web_haberleri.append({
                    "id": f"{int(time.time())}_{item.get('id', 1)}",
                    "category": temiz_kategori,
                    "title": item.get("baslik"),
                    "summary": item.get("kisa_aciklama"),
                    "fullText": item.get('detay'),
                    "image": best_match["gorsel"],  # Artık %100 doğru haber resmi!
                    "source": best_match["kaynak"],
                    "sourceUrl": best_match["link"],
                    "date": simdi_str
                })
                islenen_basliklar.append(item.get("baslik"))
                item_id = item.get("id", 1)
                matching_raw = ham_haberler[item_id - 1] if item_id <= len(ham_haberler) else ham_haberler[0]
                
                temiz_kategori = kategori_duzelt(item.get("kategori"))
                item["kategori"] = temiz_kategori # Görsel çizimi için de güncelle
                
                yeni_web_haberleri.append({
                    "id": f"{int(time.time())}_{item_id}",
                    "category": temiz_kategori,
                    "title": item.get("baslik"),
                    "summary": item.get("kisa_aciklama"),
                    "fullText": item.get('detay'),
                    "image": matching_raw["gorsel"],
                    "source": matching_raw["kaynak"],
                    "sourceUrl": matching_raw["link"],
                    "date": simdi_str
                })
                islenen_basliklar.append(item.get("baslik"))

            # ESKİ HABERLERİ YÜKLE VE ÜSTÜNE EKLE (ARŞİV OLUŞTURMA)
            mevcut_haberler = []
            if os.path.exists(WEB_JSON_DOSYASI):
                try:
                    with open(WEB_JSON_DOSYASI, "r", encoding="utf-8") as rf:
                        mevcut_haberler = json.load(rf)
                except Exception:
                    mevcut_haberler = []

            # Yeni haberleri en üste koy, eskileri altına diz (Maksimum 100 haber tut)
            toplam_haberler = yeni_web_haberleri + mevcut_haberler
            
            # Mükerrer başlık kontrolü
            gorulen_basliklar = set()
            benzersiz_haberler = []
            for h in toplam_haberler:
                if h["title"] not in gorulen_basliklar:
                    gorulen_basliklar.add(h["title"])
                    benzersiz_haberler.append(h)

            os.makedirs(os.path.dirname(WEB_JSON_DOSYASI), exist_ok=True)

            with open(WEB_JSON_DOSYASI, "w", encoding="utf-8") as wf:
                json.dump(benzersiz_haberler[:100], wf, ensure_ascii=False, indent=2)
            
            hafizaya_kaydet(islenen_basliklar)
            print("🌐 'public/news.json' arşiv güncellendi.")
            return ai_data[:4], benzersiz_haberler
    except Exception as e:
        print(f"❌ AI İşleme Hatası: {e}")
        return None, None

# ==========================================
# GÖRSEL ÇİZİMİ
# ==========================================
def gorsel_olustur(ai_maddeler):
    print("🎨 Görseller çiziliyor...")
    
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

        # Header
        draw.rectangle([(0, 0), (genislik, 95)], fill="#0d0d0d")
        draw.line([(0, 95), (genislik, 95)], fill="#e11d48", width=3)
        
        draw.text((40, 26), "SAATLİK", fill="#ffffff", font=font_logo)
        draw.text((225, 26), "TÜRKİYE", fill="#e11d48", font=font_logo)
        
        tarih_str = datetime.now().strftime("%d.%m.%Y  |  %H:%M")
        draw.text((genislik - 260, 34), tarih_str, fill="#f4f4f5", font=font_footer)

        y_offset = 110
        kart_yukseklik = 215

        for i, item in enumerate(ai_maddeler[:4], 1):
            draw.rectangle([(30, y_offset), (genislik - 30, y_offset + kart_yukseklik)], fill="#111113", outline="#27272a", width=1)
            draw.rectangle([(30, y_offset), (38, y_offset + kart_yukseklik)], fill="#2563eb")
            
            # Kategori
            kat_text = f"#{i}  {kategori_duzelt(item.get('kategori'))}"
            draw.text((55, y_offset + 10), kat_text, fill="#60a5fa", font=font_kategori)
            
            # Başlık
            baslik_satirlar = textwrap.wrap(item.get("baslik", ""), width=45)
            line_y = y_offset + 42
            for line in baslik_satirlar[:2]:
                draw.text((55, line_y), line, fill="#ffffff", font=font_baslik)
                line_y += 34

            aciklama = item.get("kisa_aciklama", "").strip()
            if aciklama and aciklama[-1] not in [".", "!", "?"]:
                aciklama += "."

            # Açıklama Metni (Metin sağı dolsun diye width=65 tutuldu)
            ozet_satirlar = textwrap.wrap(aciklama, width=65)
            line_y += 6
            for ozet_line in ozet_satirlar[:3]:
                draw.text((55, line_y), ozet_line, fill="#d4d4d8", font=font_metin)
                line_y += 30

            y_offset += kart_yukseklik + 12

        # Footer
        draw.rectangle([(0, yukseklik - 55), (genislik, yukseklik)], fill="#0d0d0d")
        draw.line([(0, yukseklik - 55), (genislik, yukseklik - 55)], fill="#27272a", width=1)
        
        draw.text((40, yukseklik - 38), f"🌐 {WEBSITE_URL.upper()}", fill="#ffffff", font=font_footer)
        draw.text((genislik - 340, yukseklik - 38), f"📢 Telegram: {KANAL_ADI}", fill="#38bdf8", font=font_footer)

        img.save(dosya_adi)

    ciz(1080, 1080, TG_OUTPUT_IMAGE)
    ciz(1080, 1080, IG_OUTPUT_IMAGE)
    print("✅ Görseller başarıyla oluşturuldu.")

def telegram_paylas(ai_maddeler):
    print("✈️ Telegram'a gönderiliyor...")
    caption = f"🔴 **SAATLİK TÜRKİYE — SON DAKİKA GÜNDEM**\n\n"
    caption += f"🌐 Tüm geçmiş haberler ve detaylar: {WEBSITE_URL}\n"
    caption += f"📢 Resmi Kanalımız: {KANAL_ADI}"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(TG_OUTPUT_IMAGE, "rb") as photo:
            payload = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            files = {"photo": photo}
            requests.post(url, data=payload, files=files)
            print("✅ Telegram paylaşımı BAŞARILI!")
    except Exception as e:
        print(f"❌ Telegram Hatası: {e}")

def instagram_paylas(ai_maddeler):
    print("📸 Instagram'a gönderiliyor...")
    if not INSTAGRAM_SESSION_ID:
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
        print(f"⚠️ Instagram Hatası: {e}")

def git_vercel_guncelle():
    print("🚀 Web sitesi Vercel üzerine aktarılıyor...")
    try:
        subprocess.run(["git", "add", WEB_JSON_DOSYASI], check=True)
        commit_msg = f"Auto news update: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("⚡ GitHub Push tamamlandı.")
    except Exception as e:
        print(f"ℹ️ Git güncelleme bildirimi: {e}")

def gorevi_calistir():
    print(f"\n⏰ [{datetime.now().strftime('%H:%M:%S')}] Yeni tarama döngüsü başladı...")
    ai_maddeler, web_news = haberleri_cek_ve_ozetle()
    
    if ai_maddeler:
        gorsel_olustur(ai_maddeler)
        telegram_paylas(ai_maddeler)
        instagram_paylas(ai_maddeler)
        git_vercel_guncelle()
        print("🎉 Saatlik tur tamamlandı.")

if __name__ == "__main__":
    print("🚀 SAATLİK TÜRKİYE BOTU CANLIYA ALINDI.")
    while True:
        try:
            gorevi_calistir()
        except Exception as global_err:
            print(f"❌ Sistem Hatası: {global_err}")
        time.sleep(3600)