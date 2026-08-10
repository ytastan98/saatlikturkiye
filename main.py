import os
import re
import json
import time
import requests
import feedparser
import subprocess
from io import BytesIO
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from moviepy import ImageClip, AudioFileClip

load_dotenv(override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
INSTAGRAM_SESSION_ID = os.getenv("INSTAGRAM_SESSION_ID")

RSS_FEEDS = [
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "https://www.aa.com.tr/tr/rss/default?cat=gundem",
    "https://www.ntv.com.tr/son-dakika.rss",
    "https://www.hurriyet.com.tr/rss/sondakika"
]

NEWS_JSON_PATH = "public/news.json"

HASHTAGS = """
#sondakika #haber #gundem #turkiye #sondakikahaber #saatlikturkiye #reels #keşfet #haberler #gündem
"""

def kategori_duzelt(cat):
    if not cat:
        return "SON DAKİKA"
    return str(cat).strip().upper()

def gorsel_url_bul(entry):
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
    if img_match: return img_match.group(1)

    haber_linki = entry.get("link", "")
    if haber_linki:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"}
            resp = requests.get(haber_linki, headers=headers, timeout=4)
            if resp.status_code == 200:
                og_match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text, re.IGNORECASE)
                if og_match: return og_match.group(1)
        except Exception:
            pass
    return ""

def git_push_degisiklikleri():
    try:
        subprocess.run(["git", "add", NEWS_JSON_PATH], check=True)
        subprocess.run(["git", "commit", "-m", f"auto: haber güncellendi ({datetime.now().strftime('%H:%M')})"], check=True)
        subprocess.run(["git", "push"], check=True)
        print("🚀 GitHub'a başarıyla aktarıldı!")
    except Exception as e:
        print(f"❌ Git hatası: {e}")

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
            if current_line: lines.append(' '.join(current_line))
            current_line = [word]
    if current_line: lines.append(' '.join(current_line))
    return lines

# ---------------------------------------------------------
# PROFESYONEL VE HATASIZ GÖRSEL ÜRETİMİ (TAŞMA KONTROLLÜ)
# ---------------------------------------------------------
def tekli_haber_gorseli_ciz(haber):
    W, H = 1080, 1350
    
    bg_img = None
    img_url = haber.get("imageUrl", "")
    if img_url:
        try:
            resp = requests.get(img_url, timeout=5)
            if resp.status_code == 200:
                raw_img = Image.open(BytesIO(resp.content)).convert("RGB")
                raw_w, raw_h = raw_img.size
                target_aspect = W / H
                current_aspect = raw_w / raw_h
                
                if current_aspect > target_aspect:
                    new_h = H
                    new_w = int(raw_w * (H / raw_h))
                else:
                    new_w = W
                    new_h = int(raw_h * (W / raw_w))
                
                raw_img = raw_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                left = (new_w - W) / 2
                top = (new_h - H) / 2
                bg_img = raw_img.crop((left, top, left + W, top + H))
        except Exception:
            pass

    if not bg_img:
        bg_img = Image.new("RGB", (W, H), color=(15, 23, 42))

    darken = Image.new("RGBA", (W, H), (0, 0, 0, 140))
    bg_img = Image.alpha_composite(bg_img.convert("RGBA"), darken).convert("RGB")

    draw = ImageDraw.Draw(bg_img)

    try:
        font_badge = ImageFont.truetype("arialbd.ttf", 30)
        font_sub = ImageFont.truetype("arialbd.ttf", 26)
        font_title = ImageFont.truetype("arialbd.ttf", 42)
        font_desc = ImageFont.truetype("arial.ttf", 26)
        font_footer = ImageFont.truetype("arialbd.ttf", 24)
    except IOError:
        font_badge = font_sub = font_title = font_desc = font_footer = ImageFont.load_default()

    # SOL ÜST: SON DAKİKA ROZETİ (DİNAMİK BOYUT)
    badge_text = "SON DAKİKA"
    badge_bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    text_w = badge_bbox[2] - badge_bbox[0]
    text_h = badge_bbox[3] - badge_bbox[1]
    
    badge_w = text_w + 44
    badge_h = text_h + 28
    badge_x, badge_y = 50, 50
    
    draw.rectangle([badge_x, badge_y, badge_x + badge_w, badge_y + badge_h], fill=(220, 38, 38))
    draw.text((badge_x + 22, badge_y + 14), badge_text, font=font_badge, fill=(255, 255, 255))

    max_text_width = W - 100 
    title_lines = metin_sardir(haber['title'], font_title, max_text_width - 40, draw)
    sub_lines = metin_sardir(haber['summary'], font_desc, max_text_width - 40, draw)

    box_padding_y = 40
    line_height_title = 52
    line_height_desc = 36
    
    total_text_h = box_padding_y + 35 + (len(title_lines) * line_height_title) + 15 + (len(sub_lines) * line_height_desc) + box_padding_y
    
    box_x = 50
    box_w = W - 100
    box_y = H - total_text_h - 110 

    shape_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shape_draw = ImageDraw.Draw(shape_layer)
    shape_draw.rectangle([box_x, box_y, box_x + box_w, box_y + 6], fill=(220, 38, 38, 255))
    shape_draw.rectangle([box_x, box_y + 6, box_x + box_w, box_y + total_text_h], fill=(15, 23, 42, 235))
    
    bg_img = Image.alpha_composite(bg_img.convert("RGBA"), shape_layer).convert("RGB")
    draw = ImageDraw.Draw(bg_img)

    curr_y = box_y + box_padding_y
    
    draw.text((box_x + 30, curr_y), haber['category'].upper(), font=font_sub, fill=(239, 68, 68))
    curr_y += 35

    for line in title_lines:
        draw.text((box_x + 30, curr_y), line, font=font_title, fill=(255, 255, 255))
        curr_y += line_height_title

    curr_y += 10

    for line in sub_lines:
        draw.text((box_x + 30, curr_y), line, font=font_desc, fill=(203, 213, 225))
        curr_y += line_height_desc

    footer_y = H - 80
    draw.rectangle([0, footer_y, W, H], fill=(10, 15, 25))
    draw.text((50, footer_y + 26), "SAATLİK TÜRKİYE", font=font_footer, fill=(255, 255, 255))
    draw.text((W - 270, footer_y + 26), "detaylar bio'da 👆", font=font_footer, fill=(239, 68, 68))

    out_path = "tekli_haber.png"
    bg_img.save(out_path)
    return out_path

def video_yap(gorsel_yolu):
    try:
        reels_bg_path = "reels_frame.png"
        video_out_path = "tekli_reels.mp4"
        audio_path = "news_bg.mp3"

        reels_w, reels_h = 1080, 1920
        bg_img = Image.new("RGB", (reels_w, reels_h), color=(7, 8, 10))
        bulten_img = Image.open(gorsel_yolu)
        offset_y = (reels_h - bulten_img.height) // 2
        bg_img.paste(bulten_img, (0, offset_y))
        bg_img.save(reels_bg_path)

        clip = ImageClip(reels_bg_path, duration=10)
        if os.path.exists(audio_path):
            audio = AudioFileClip(audio_path).subclipped(0, 10)
            clip = clip.with_audio(audio)

        clip.write_videofile(video_out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)
        return video_out_path
    except Exception as e:
        print(f"❌ Video hata: {e}")
        return None

def telegrama_gonder(gorsel_yolu, haber):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    caption = (
        f"🚨 **SON DAKİKA | {haber['category']}**\n\n"
        f"📌 **{haber['title']}**\n\n"
        f"✍️ {haber['summary']}\n\n"
        f"🔗 **Detaylar:** {haber['sourceUrl']}\n"
        f"🌐 https://saatlikturkiye.com"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(gorsel_yolu, "rb") as p:
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"photo": p}, timeout=15)
            print("✈️ Telegram'a gönderildi!")
    except Exception as e:
        print(f"❌ Telegram hata: {e}")

def instagrama_gonder(video_yolu, haber):
    if not INSTAGRAM_SESSION_ID: return
    try:
        from instagrapi import Client
        cl = Client()
        cl.login_by_sessionid(INSTAGRAM_SESSION_ID)
        caption = (
            f"🚨 {haber['title']}\n\n"
            f"{haber['summary']}\n\n"
            f"🤔 Bu gelişme hakkında ne düşünüyorsunuz? Yorumlarda buluşalım! 👇\n\n"
            f"📌 En taze son dakika haberleri için takip etmeyi unutmayın! 🔔\n"
            f"🔗 Detaylar: {haber['sourceUrl']}\n\n"
            f"{HASHTAGS}"
        )
        cl.clip_upload(video_yolu, caption=caption)
        print("📸 Instagram'a yüklendi!")
    except Exception as e:
        print(f"⚠️ Instagram hata: {e}")

def groq_ile_tek_haber_sec(ham_haberler):
    if not GROQ_API_KEY: return None
    list_prompt = [{"id": i, "baslik": h['orijinal_baslik']} for i, h in enumerate(ham_haberler)]
    prompt = f"""
    Aşağıdaki en taze ve güncel haberler arasından **en flaş, en çok tık getirecek ve en önemli 1 tanesini** seç. Eski veya sıradan haberleri kesinlikle seçme.
    
    KURALLAR:
    1. "orijinal_id": Seçtiğin haberin id numarası.
    2. "baslik": Sosyal medyada parmak durduracak çok vurucu son dakika başlığı (6-9 kelime).
    3. "kisa_aciklama": KESİNLİKLE TAM 2 CÜMLE. Olayı özetle ve merak uyandır.
    4. "kategori": SON DAKİKA / GÜNDEM / EKONOMİ vb.

    JSON Formatı:
    {{
      "baslik": "...",
      "kisa_aciklama": "...",
      "kategori": "...",
      "orijinal_id": 0
    }}
    Haberler: {json.dumps(list_prompt, ensure_ascii=False)}
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": "Return valid JSON."}, {"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if resp.status_code == 200:
            return json.loads(resp.json()['choices'][0]['message']['content'])
    except Exception:
        pass
    return None

def calistir():
    print(f"\n--- Tarama ve Paylaşım Başladı: {datetime.now().strftime('%d.%m.%Y - %H:%M:%S')} ---")
    mevcut = []
    paylasilanlar = set()
    if os.path.exists(NEWS_JSON_PATH):
        try:
            with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
                mevcut = json.load(f)
                paylasilanlar = {h.get("sourceUrl") for h in mevcut if "sourceUrl" in h}
        except Exception:
            pass

    ham = []
    simdi_utc = datetime.now(timezone.utc)
    
    for url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:12]:
                b = entry.get("title", "").strip()
                l = entry.get("link", "").strip()
                if not b or not l or l in paylasilanlar: continue
                
                pub_time = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub_time:
                    haber_tarihi = datetime.fromtimestamp(time.mktime(pub_time), tz=timezone.utc)
                    if simdi_utc - haber_tarihi > timedelta(hours=12):
                        continue

                if any(SequenceMatcher(None, b.lower(), h["orijinal_baslik"].lower()).ratio() > 0.5 for h in ham): continue
                
                ham.append({
                    "orijinal_baslik": b,
                    "link": l,
                    "gorsel_url": gorsel_url_bul(entry),
                    "kaynak": parsed.feed.get("title", "Son Dakika")
                })
        except Exception:
            pass

    if not ham:
        print("❌ Son 12 saate ait yeni ve taze haber bulunamadı.")
        return

    secilen_ai = groq_ile_tek_haber_sec(ham)
    if not secilen_ai:
        print("❌ AI seçimi başarısız.")
        return

    orig_id = secilen_ai.get("orijinal_id", 0)
    best_match = ham[orig_id] if 0 <= orig_id < len(ham) else ham[0]

    simdi_str = datetime.now().strftime("%d.%m.%Y - %H:%M")
    yeni_haber = {
        "id": f"{int(time.time())}",
        "category": kategori_duzelt(secilen_ai.get("kategori")),
        "title": secilen_ai.get("baslik"),
        "summary": secilen_ai.get("kisa_aciklama"),
        "imageUrl": best_match.get("gorsel_url", ""),
        "source": best_match["kaynak"],
        "sourceUrl": best_match["link"],
        "date": simdi_str
    }

    toplam = ([yeni_haber] + mevcut)[:100]
    os.makedirs(os.path.dirname(NEWS_JSON_PATH), exist_ok=True)
    with open(NEWS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(toplam, f, ensure_ascii=False, indent=2)

    git_push_degisiklikleri()

    gorsel_yolu = tekli_haber_gorseli_ciz(yeni_haber)
    video_yolu = video_yap(gorsel_yolu)

    if gorsel_yolu and os.path.exists(gorsel_yolu):
        telegrama_gonder(gorsel_yolu, yeni_haber)

    if video_yolu and os.path.exists(video_yolu):
        instagrama_gonder(video_yolu, yeni_haber)

    print("🎉 Tur başarıyla tamamlandı ve Instagram/Telegram'a gönderildi!")

if __name__ == "__main__":
    print("🚀 Prime-Time Saatli Flaş Haber Botu Aktif (Günde 4 Paylaşım)!")
    
    # En yüksek etkileşimli hedef saatler (Türkiye Saati ile)
    # 1. 08:00 -> Sabah İşe Gidiş / Toplu Taşıma
    # 2. 13:00 -> Öğle Arası
    # 3. 19:00 -> Akşam Eve Dönüş / Prime-Time Başlangıcı
    # 4. 21:30 -> Gece Kuşağı Yüksek Trafik
    HEDEF_SAATLER = [(8, 0), (13, 0), (19, 0), (21, 30)]
    son_calisilan_gun_saat = ""

    while True:
        simdi = datetime.now()
        bugun_str = simdi.strftime("%Y-%m-%d")
        simdi_saat = simdi.hour
        simdi_dakika = simdi.minute

        for saat, dakika in HEDEF_SAATLER:
            # Hedef saate gelindiyse ve bu saat dilimi için bugün henüz çalışmadıysa
            benzersiz_anahtar = f"{bugun_str}-{saat:02d}:{dakika:02d}"
            
            if simdi_saat == saat and abs(simdi_dakika - dakika) <= 3 and son_calisilan_gun_saat != benzersiz_anahtar:
                try:
                    calistir()
                    son_calisilan_gun_saat = benzersiz_anahtar
                except Exception as e:
                    print(f"Döngü hatası: {e}")
        
        # Her 2 dakikada bir saati kontrol et
        time.sleep(120)