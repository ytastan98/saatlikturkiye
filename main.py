import os
import re
import json
import time
import requests
import feedparser
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

# .env değişkenlerini yükle
load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
INSTAGRAM_SESSION_ID = os.getenv("INSTAGRAM_SESSION_ID")

RSS_FEEDS = [
    "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.aa.com.tr/tr/rss/default?cat=gundem"
]

NEWS_JSON_PATH = "public/news.json"


def kategori_duzelt(cat):
    if not cat:
        return "GÜNDEM"
    c = str(cat).strip().upper()
    mapping = {
        'SUC': 'SUÇ', 'TRAFIG': 'TRAFİK', 'TRAFIK': 'TRAFİK', 'TRAFFIK': 'TRAFİK',
        'EKONOMI': 'EKONOMİ', 'IC HABERLER': 'İÇ HABERLER', 'IC': 'İÇ HABERLER',
        'SAGLIK': 'SAĞLIK', 'EGITIM': 'EĞİTİM', 'POLITIKA': 'POLİTİKA',
        'DUNYA': 'DÜNYA', 'TEKNOLOJI': 'TEKNOLOJİ'
    }
    return mapping.get(c, c)


def gorsel_url_bul(entry):
    """RSS entry içerisinden haberin görsel URL'sini çeker."""
    # 1. media_content kontrolü
    if 'media_content' in entry and len(entry.media_content) > 0:
        url = entry.media_content[0].get('url')
        if url: return url

    # 2. enclosures (ekler) kontrolü
    if 'enclosures' in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/') or enc.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return enc.get('href')

    # 3. media_thumbnail kontrolü
    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        url = entry.media_thumbnail[0].get('url')
        if url: return url

    # 4. Summary veya Content içindeki HTML <img> etiketi
    html_content = entry.get('summary', '') + entry.get('description', '')
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    return ""


# ---------------------------------------------------------
# 1. OTOMATİK GIT PUSH (VERCEL TEK TETİKLEME)
# ---------------------------------------------------------

def git_push_degisiklikleri():
    """public/news.json dosyasını otomatik GitHub'a pushlar ve Vercel'i tetikler."""
    try:
        print("🔄 GitHub'a pushlanıyor (Vercel tetikleniyor)...")
        subprocess.run(["git", "add", NEWS_JSON_PATH], check=True)
        commit_msg = f"auto: haberler ve görseller güncellendi ({datetime.now().strftime('%H:%M')})"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 GitHub'a başarıyla pushlandı! Vercel canlıyı güncelliyor.")
    except subprocess.CalledProcessError:
        print("⚠️ Git push yapılamadı (Değişiklik yok veya Git hatası).")
    except Exception as e:
        print(f"❌ Git hatası: {e}")


# ---------------------------------------------------------
# 2. PIL İLE BİREBİR TASARIMLI GÖRSEL KART ÇİZİCİ
# ---------------------------------------------------------

def metin_sardir(text, font, max_width, draw):
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
    if current_line:
        lines.append(' '.join(current_line))
    return lines


def bulten_gorseli_ciz(haberler, tarih_str):
    W, H = 1080, 1350
    bg_color = (7, 8, 10)
    img = Image.new("RGB", (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_header_bold = ImageFont.truetype("arialbd.ttf", 46)
        font_title_bold = ImageFont.truetype("arialbd.ttf", 32)
        font_cat_bold = ImageFont.truetype("arialbd.ttf", 28)
        font_body = ImageFont.truetype("arial.ttf", 23)
        font_small = ImageFont.truetype("arial.ttf", 22)
    except IOError:
        font_header_bold = font_title_bold = font_cat_bold = font_body = font_small = ImageFont.load_default()

    # --- HEADER ---
    draw.text((50, 45), "SAATLİK ", font=font_header_bold, fill=(255, 255, 255))
    bbox = draw.textbbox((50, 45), "SAATLİK ", font=font_header_bold)
    draw.text((bbox[2], 45), "TÜRKİYE", font=font_header_bold, fill=(229, 62, 62))

    draw.text((W - 320, 55), tarih_str, font=font_small, fill=(226, 232, 240))
    draw.line([(50, 115), (W - 50, 115)], fill=(229, 62, 62), width=3)

    # --- HABERLER ---
    start_y = 135
    box_height = 275

    for idx, h in enumerate(haberler, 1):
        y = start_y + (idx - 1) * box_height
        
        cat_text = f"#{idx}  {h['category']}"
        draw.text((50, y), cat_text, font=font_cat_bold, fill=(49, 130, 206))

        title_lines = metin_sardir(h['title'], font_title_bold, W - 100, draw)[:2]
        curr_y = y + 38
        for line in title_lines:
            draw.text((50, curr_y), line, font=font_title_bold, fill=(255, 255, 255))
            curr_y += 38

        summary_lines = metin_sardir(h['summary'], font_body, W - 100, draw)[:3]
        curr_y += 6
        for line in summary_lines:
            draw.text((50, curr_y), line, font=font_body, fill=(160, 174, 192))
            curr_y += 30

        if idx < 4:
            draw.line([(50, y + box_height - 10), (W - 50, y + box_height - 10)], fill=(26, 32, 44), width=2)

    # --- FOOTER ---
    footer_y = H - 85
    draw.line([(50, footer_y), (W - 50, footer_y)], fill=(26, 32, 44), width=2)

    draw.text((50, footer_y + 25), "🌐 SAATLIKTURKIYE.COM", font=font_small, fill=(255, 255, 255))
    draw.text((W - 380, footer_y + 25), "📢 Telegram: @saatlikturkiye", font=font_small, fill=(49, 130, 206))

    out_path = "bulten.png"
    img.save(out_path)
    print("🎨 Bülten kartı çizildi!")
    return out_path


# ---------------------------------------------------------
# 3. SOSYAL MEDYA GÖNDERİM
# ---------------------------------------------------------

def telegrama_gorsel_at(gorsel_yolu):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    caption_text = "🚨 **SAATLİK TÜRKİYE ÖNE ÇIKANLAR**\n\n🔗 Tüm haberlerin detayları sitemizde:\nhttps://saatlikturkiye.com"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(gorsel_yolu, "rb") as photo_file:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption_text, "parse_mode": "Markdown"}, files={"photo": photo_file}, timeout=15)
            print("✈️ Tasarımlı kart Telegram'a gönderildi!")
    except Exception as e:
        print(f"❌ Telegram Hatası: {e}")


def instagrama_gorsel_at(gorsel_yolu):
    if not INSTAGRAM_SESSION_ID:
        return
    try:
        from instagrapi import Client
        cl = Client()
        cl.login_by_sessionid(INSTAGRAM_SESSION_ID)
        cl.photo_upload(gorsel_yolu, caption="📌 SAATLİK TÜRKİYE ÖNE ÇIKANLAR\n\n👉 Detaylar profilimizdeki linkte!\n\n#sondakika #haber #gundem #turkiye")
        print("📸 Tasarımlı kart Instagram'a yüklendi!")
    except Exception as e:
        print(f"⚠️ Instagram hatası: {e}")


# ---------------------------------------------------------
# 4. AI ÖZET VE ANA AKIŞ
# ---------------------------------------------------------

def groq_ile_ozetle(ham_haberler):
    if not GROQ_API_KEY:
        return None

    # AI'ya haberleri indeksleriyle gönderiyoruz
    haber_listesi_prompt = [
        {"orijinal_id": idx, "baslik": h['orijinal_baslik']}
        for idx, h in enumerate(ham_haberler)
    ]

    prompt = f"""
    Aşağıdaki haber listesini incele. En önemli ve ilgi çekici 4 haberi seç.
    Seçtiğin haberleri Türkçe olarak yeniden özgünleştir.

    ÖNEMLİ KURALLAR:
    1. "orijinal_id": Seçtiğin haberin aşağıdaki listedeki "orijinal_id" numarasını AYNEN YAZMALISIN.
    2. "baslik": Haber başlığı çarpıcı ve net olmalı (6-10 kelime).
    3. "kisa_aciklama": HER HABER İÇİN KESİNLİKLE VE İSTİSNASIZ TAM 2 CÜMLE YAZACAKSIN.
    4. "kategori": GÜNDEM / İÇ HABERLER / SUÇ / TRAFİK / EKONOMİ / DÜNYA / TEKNOLOJİ kategorilerinden biri olmalı.

    İstenen JSON Yapısı:
    {{
      "maddeler": [
        {{
          "id": 1,
          "orijinal_id": 0,
          "baslik": "Dikkat çekici haber başlığı",
          "kisa_aciklama": "Olayı anlatan birinci cümle. Detay veren ikinci cümle.",
          "detay": "Haberin detaylı açıklaması",
          "kategori": "GÜNDEM"
        }}
      ]
    }}

    Haber Listesi:
    {json.dumps(haber_listesi_prompt, ensure_ascii=False)}
    """

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": "You are a senior Turkish news editor."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            clean_json = response.json()['choices'][0]['message']['content']
            return json.loads(clean_json).get("maddeler", [])
    except Exception as e:
        print(f"❌ Groq Bağlantı Hatası: {e}")
    return None


def haberleri_islemden_gecir():
    print("🔄 RSS akışları taranıyor...")
    ham_haberler = []

    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:5]:
                ham_haberler.append({
                    "orijinal_baslik": entry.get("title", ""),
                    "ozet": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                    "gorsel_url": gorsel_url_bul(entry),
                    "kaynak": parsed.feed.get("title", "Haber Kaynağı")
                })
        except Exception as e:
            print(f"⚠️ RSS hatası ({feed_url}): {e}")

    if not ham_haberler:
        print("❌ Hiç haber çekilemedi.")
        return

    print(f" Toplam {len(ham_haberler)} haber toplandı. Groq AI ile işleniyor...")

    ai_data = groq_ile_ozetle(ham_haberler)
    if not ai_data:
        return

    mevcut_haberler = []
    if os.path.exists(NEWS_JSON_PATH):
        try:
            with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
                mevcut_haberler = json.load(f)
        except Exception:
            mevcut_haberler = []

    simdi = datetime.now()
    simdi_str = simdi.strftime("%d.%m.%Y - %H:%M")
    tarih_kart_str = simdi.strftime("%d.%m.%Y | %H:%M")
    
    yeni_eklenenler = []

    for item in ai_data:
        # BİREBİR EŞLEŞTİRME DÜZELTMESİ
        orig_id = item.get("orijinal_id")
        if orig_id is not None and isinstance(orig_id, int) and 0 <= orig_id < len(ham_haberler):
            best_match = ham_haberler[orig_id]
        else:
            best_match = ham_haberler[0]

        temiz_kategori = kategori_duzelt(item.get("kategori"))

        yeni_haber = {
            "id": f"{int(time.time())}_{item.get('id', 1)}",
            "category": temiz_kategori,
            "title": item.get("baslik"),
            "summary": item.get("kisa_aciklama"),
            "fullText": item.get("detay"),
            "imageUrl": best_match.get("gorsel_url", ""),
            "source": best_match["kaynak"],
            "sourceUrl": best_match["link"],
            "date": simdi_str
        }
        yeni_eklenenler.append(yeni_haber)

    # 1. LOCAL JSON YAZMA
    toplam_haberler = yeni_eklenenler + mevcut_haberler
    toplam_haberler = toplam_haberler[:30]

    os.makedirs(os.path.dirname(NEWS_JSON_PATH), exist_ok=True)
    with open(NEWS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(toplam_haberler, f, ensure_ascii=False, indent=2)

    # 2. VERCEL / GITHUB OTOMATİK PUSH
    git_push_degisiklikleri()

    # 3. PIL İLE TASARIM KARTINI OLUŞTUR
    gorsel_dosyasi = bulten_gorseli_ciz(yeni_eklenenler, tarih_kart_str)

    # 4. SOSYAL MEDYAYA GÖNDER
    if gorsel_dosyasi and os.path.exists(gorsel_dosyasi):
        telegrama_gorsel_at(gorsel_dosyasi)
        instagrama_gorsel_at(gorsel_dosyasi)

    print(f"\n🎉 Görselleri içeren haberler GitHub/Vercel'e pushlandı!")


if __name__ == "__main__":
    haberleri_islemden_gecir()