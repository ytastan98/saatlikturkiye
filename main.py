import os
import re
import json
import time
import requests
import feedparser
import subprocess
from datetime import datetime
from difflib import SequenceMatcher
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip
from moviepy import AudioFileClip
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

HASHTAGS = """
#sondakika #haber #gundem #turkiye #sondakikahaber #saatlikturkiye #reels #keşfet #haberler #gündem #canlıyayın #dünya #ekonomi #teknoloji
"""


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
    """RSS entry içerisinden veya haberin web sayfasından (og:image) görsel çeker."""
    if 'media_content' in entry and len(entry.media_content) > 0:
        url = entry.media_content[0].get('url')
        if url: return url

    if 'enclosures' in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image/') or enc.get('href', '').endswith(('.jpg', '.jpeg', '.png', '.webp')):
                return enc.get('href')

    if 'media_thumbnail' in entry and len(entry.media_thumbnail) > 0:
        url = entry.media_thumbnail[0].get('url')
        if url: return url

    html_content = entry.get('summary', '') + entry.get('description', '')
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    haber_linki = entry.get("link", "")
    if haber_linki:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(haber_linki, headers=headers, timeout=4)
            if resp.status_code == 200:
                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                if not og_match:
                    og_match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', resp.text, re.IGNORECASE)
                
                if og_match:
                    return og_match.group(1)
        except Exception:
            pass

    return ""


# ---------------------------------------------------------
# 1. OTOMATİK GIT PUSH
# ---------------------------------------------------------

def git_push_degisiklikleri():
    try:
        print("🔄 GitHub'a pushlanıyor (Vercel tetikleniyor)...")
        subprocess.run(["git", "add", NEWS_JSON_PATH], check=True)
        commit_msg = f"auto: haberler güncellendi ({datetime.now().strftime('%H:%M')})"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 GitHub'a başarıyla pushlandı!")
    except subprocess.CalledProcessError:
        print("⚠️ Git push yapılamadı (Değişiklik yok veya Git hatası).")
    except Exception as e:
        print(f"❌ Git hatası: {e}")


# ---------------------------------------------------------
# 2. GÖRSEL VE VİDEO İŞLEME
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

    draw.text((50, 45), "SAATLİK ", font=font_header_bold, fill=(255, 255, 255))
    bbox = draw.textbbox((50, 45), "SAATLİK ", font=font_header_bold)
    draw.text((bbox[2], 45), "TÜRKİYE", font=font_header_bold, fill=(229, 62, 62))

    draw.text((W - 320, 55), tarih_str, font=font_small, fill=(226, 232, 240))
    draw.line([(50, 115), (W - 50, 115)], fill=(229, 62, 62), width=3)

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

    footer_y = H - 85
    draw.line([(50, footer_y), (W - 50, footer_y)], fill=(26, 32, 44), width=2)

    draw.text((50, footer_y + 25), "🌐 SAATLIKTURKIYE.COM", font=font_small, fill=(255, 255, 255))
    draw.text((W - 380, footer_y + 25), "📢 Telegram: @saatlikturkiye", font=font_small, fill=(49, 130, 206))

    out_path = "bulten.png"
    img.save(out_path)
    print("🎨 Bülten kartı çizildi!")
    return out_path


def bulten_reels_videosu_yap(gorsel_yolu):
    try:
        reels_bg_path = "bulten_reels_frame.png"
        video_out_path = "bulten_reels.mp4"
        audio_path = "news_bg.mp3"

        reels_w, reels_h = 1080, 1920
        bg_img = Image.new("RGB", (reels_w, reels_h), color=(7, 8, 10))

        bulten_img = Image.open(gorsel_yolu)
        offset_y = (reels_h - bulten_img.height) // 2
        bg_img.paste(bulten_img, (0, offset_y))
        bg_img.save(reels_bg_path)

        # MoviePy v2.x uyumlu süre tanımlaması
        clip = ImageClip(reels_bg_path, duration=10)

        if os.path.exists(audio_path):
            # v2.x sürümünde subclip yerine subclipped kullanılmaktadır
            audio = AudioFileClip(audio_path).subclipped(0, 10)
            clip = clip.with_audio(audio)

        clip.write_videofile(
            video_out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None
        )
        print("🎥 Reels videosu (MP4) başarıyla üretildi!")
        return video_out_path
    except Exception as e:
        print(f"❌ Reels video üretme hatası: {e}")
        return None
    try:
        reels_bg_path = "bulten_reels_frame.png"
        video_out_path = "bulten_reels.mp4"
        audio_path = "news_bg.mp3"

        reels_w, reels_h = 1080, 1920
        bg_img = Image.new("RGB", (reels_w, reels_h), color=(7, 8, 10))

        bulten_img = Image.open(gorsel_yolu)
        offset_y = (reels_h - bulten_img.height) // 2
        bg_img.paste(bulten_img, (0, offset_y))
        bg_img.save(reels_bg_path)

        # MoviePy v2.x uyumlu süre ve ses tanımlaması
        clip = ImageClip(reels_bg_path, duration=10)

        if os.path.exists(audio_path):
            audio = AudioFileClip(audio_path).subclip(0, 10)
            clip = clip.with_audio(audio)

        clip.write_videofile(
            video_out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None
        )
        print("🎥 Reels videosu (MP4) başarıyla üretildi!")
        return video_out_path
    except Exception as e:
        print(f"❌ Reels video üretme hatası: {e}")
        return None
    try:
        reels_bg_path = "bulten_reels_frame.png"
        video_out_path = "bulten_reels.mp4"
        audio_path = "news_bg.mp3"

        reels_w, reels_h = 1080, 1920
        bg_img = Image.new("RGB", (reels_w, reels_h), color=(7, 8, 10))

        bulten_img = Image.open(gorsel_yolu)
        offset_y = (reels_h - bulten_img.height) // 2
        bg_img.paste(bulten_img, (0, offset_y))
        bg_img.save(reels_bg_path)

        clip = ImageClip(reels_bg_path).set_duration(10)

        if os.path.exists(audio_path):
            audio = AudioFileClip(audio_path).subclip(0, 10)
            clip = clip.set_audio(audio)

        clip.write_videofile(
            video_out_path, 
            fps=24, 
            codec="libx264", 
            audio_codec="aac", 
            logger=None
        )
        print("🎥 Reels videosu (MP4) başarıyla üretildi!")
        return video_out_path
    except Exception as e:
        print(f"❌ Reels video üretme hatası: {e}")
        return None


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


def instagrama_reels_at(video_yolu):
    if not INSTAGRAM_SESSION_ID:
        return
    try:
        from instagrapi import Client
        cl = Client()
        cl.login_by_sessionid(INSTAGRAM_SESSION_ID)

        caption_text = f"🚨 SAATLİK TÜRKİYE | ÖNE ÇIKANLAR\n\n📌 Saat başı öne çıkan başlıklar ve gündem detayları sitemizde!\n🔗 Detaylar için profildeki linke tıklayın: https://saatlikturkiye.com\n\n{HASHTAGS}"
        cl.clip_upload(video_yolu, caption=caption_text)
        print("📸 Reels videosu Instagram'a başarıyla yüklendi!")
    except Exception as e:
        print(f"⚠️ Instagram Reels yükleme hatası: {e}")


# ---------------------------------------------------------
# 4. AI ÖZET VE ANA AKIŞ
# ---------------------------------------------------------

def groq_ile_ozetle(ham_haberler):
    if not GROQ_API_KEY:
        print("❌ HATA: GROQ_API_KEY bulunamadı!")
        return None

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
    5. TEKİLLEŞTİRME: Seçtiğin 4 haberin konusu BİRBİRİNDEN TAMAMEN FARKLI olmalıdır.

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
            {"role": "system", "content": "You are a senior Turkish news editor. Always return valid JSON containing 'maddeler' array."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            clean_json = response.json()['choices'][0]['message']['content']
            parsed_data = json.loads(clean_json)
            
            if isinstance(parsed_data, dict):
                items = parsed_data.get("maddeler") or parsed_data.get("news") or parsed_data.get("haberler")
                if not items and len(parsed_data.values()) > 0:
                    first_val = list(parsed_data.values())[0]
                    if isinstance(first_val, list):
                        items = first_val
                return items
            elif isinstance(parsed_data, list):
                return parsed_data
        else:
            print(f"❌ Groq API Hatası: {response.status_code}")
    except Exception as e:
        print(f"❌ Groq İşleme Hatası: {e}")

    return None


def haberleri_islemden_gecir():
    print(f"\n--------------------------------------------------")
    print(f"⏰ Güncelleme Başladı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    
    # 1. ÖNCEDEN PAYLAŞILMIŞ HABERLERİN LİNKLERİNİ YÜKLE (TEKRARI ÖNLEMEK İÇİN)
    mevcut_haberler = []
    paylasilan_linkler = set()
    if os.path.exists(NEWS_JSON_PATH):
        try:
            with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
                mevcut_haberler = json.load(f)
                # Daha önce paylaşılan haberlerin linklerini sete ekle
                paylasilan_linkler = {h.get("sourceUrl") for h in mevcut_haberler if "sourceUrl" in h}
        except Exception:
            mevcut_haberler = []

    print("🔄 RSS akışları taranıyor...")
    ham_haberler = []

    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:8]: # Havuzu biraz genişlettik (ilk 8 haber)
                baslik = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                
                if not baslik or not link:
                    continue

                # EĞER BU HABER DAHA ÖNCE PAYLAŞILDDIYSA ATLA!
                if link in paylasilan_linkler:
                    continue

                # Benzer başlık kontrolü (Farklı kaynaklar aynı haberi farklı başlıkla verdiyse)
                zaten_var = False
                for h in ham_haberler:
                    benzerlik = SequenceMatcher(None, baslik.lower(), h["orijinal_baslik"].lower()).ratio()
                    if benzerlik > 0.50:
                        zaten_var = True
                        break
                
                if zaten_var:
                    continue

                ham_haberler.append({
                    "orijinal_baslik": baslik,
                    "ozet": entry.get("summary", ""),
                    "link": link,
                    "gorsel_url": gorsel_url_bul(entry),
                    "kaynak": parsed.feed.get("title", "Haber Kaynağı")
                })
        except Exception as e:
            print(f"⚠️ RSS hatası ({feed_url}): {e}")

    if not ham_haberler:
        print("❌ Yeni ve taze haber bulunamadı (Tüm haberler daha önce paylaşılmış). Bu tur pas geçiliyor.")
        return

    print(f" Toplam {len(ham_haberler)} yeni ve benzersiz haber toplandı. Groq AI ile işleniyor...")

    ai_data = groq_ile_ozetle(ham_haberler)
    if not ai_data:
        print("❌ AI aşaması başarısız olduğu için bu tur pas geçiliyor.")
        return

    simdi = datetime.now()
    simdi_str = simdi.strftime("%d.%m.%Y - %H:%M")
    tarih_kart_str = simdi.strftime("%d.%m.%Y | %H:%M")
    
    yeni_eklenenler = []

    for item in ai_data:
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

    # Toplam haberleri birleştir (En yeni eklenenler en başta yer alır)
    toplam_haberler = yeni_eklenenler + mevcut_haberler
    toplam_haberler = toplam_haberler[:100]  # Sitede en fazla 100 haber tutulur

    os.makedirs(os.path.dirname(NEWS_JSON_PATH), exist_ok=True)
    with open(NEWS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(toplam_haberler, f, ensure_ascii=False, indent=2)

    print(f"✅ 'news.json' güncellendi. Toplam {len(toplam_haberler)} haber veritabanında saklanıyor.")

    git_push_degisiklikleri()

    gorsel_dosyasi = bulten_gorseli_ciz(yeni_eklenenler, tarih_kart_str)
    video_dosyasi = bulten_reels_videosu_yap(gorsel_dosyasi)

    if gorsel_dosyasi and os.path.exists(gorsel_dosyasi):
        telegrama_gorsel_at(gorsel_dosyasi)

    if video_dosyasi and os.path.exists(video_dosyasi):
        instagrama_reels_at(video_dosyasi)

    print(f"🎉 Saatlik tur başarıyla tamamlandı!")
    print(f"\n--------------------------------------------------")
    print(f"⏰ Güncelleme Başladı: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
    print("🔄 RSS akışları taranıyor...")
    ham_haberler = []

    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:6]:
                baslik = entry.get("title", "").strip()
                if not baslik:
                    continue

                zaten_var = False
                for h in ham_haberler:
                    benzerlik = SequenceMatcher(None, baslik.lower(), h["orijinal_baslik"].lower()).ratio()
                    if benzerlik > 0.50:
                        zaten_var = True
                        break
                
                if zaten_var:
                    continue

                ham_haberler.append({
                    "orijinal_baslik": baslik,
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

    print(f" Toplam {len(ham_haberler)} benzersiz haber toplandı. Groq AI ile işleniyor...")

    ai_data = groq_ile_ozetle(ham_haberler)
    if not ai_data:
        print("❌ AI aşaması başarısız olduğu için bu tur pas geçiliyor.")
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

    toplam_haberler = yeni_eklenenler + mevcut_haberler
    toplam_haberler = toplam_haberler[:100]  # Sitede en fazla 100 haber tutulur

    os.makedirs(os.path.dirname(NEWS_JSON_PATH), exist_ok=True)
    with open(NEWS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(toplam_haberler, f, ensure_ascii=False, indent=2)

    print(f"✅ 'news.json' güncellendi. Toplam {len(toplam_haberler)} haber veritabanında saklanıyor.")

    git_push_degisiklikleri()

    gorsel_dosyasi = bulten_gorseli_ciz(yeni_eklenenler, tarih_kart_str)
    video_dosyasi = bulten_reels_videosu_yap(gorsel_dosyasi)

    if gorsel_dosyasi and os.path.exists(gorsel_dosyasi):
        telegrama_gorsel_at(gorsel_dosyasi)

    if video_dosyasi and os.path.exists(video_dosyasi):
        instagrama_reels_at(video_dosyasi)

    print(f"🎉 Saatlik tur başarıyla tamamlandı!")


# ---------------------------------------------------------
# 5. OTOMATİK SAATLİK DÖNGÜ (WHILE LOOP)
# ---------------------------------------------------------

if __name__ == "__main__":
    print("🚀 Saatlik Türkiye Otomasyon Botu Başlatıldı!")
    print("📌 Bot her 60 dakikada bir otomatik çalışacaktır. Kapatmak için CTRL+C yapabilirsin.\n")
    
    while True:
        try:
            haberleri_islemden_gecir()
        except Exception as e:
            print(f"❌ Ana döngü hatası oluştu: {e}")
        
        print("⏳ Bir sonraki güncelleme için 1 saat (3600 sn) bekleniyor...")
        time.sleep(3600)