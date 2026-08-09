import os
import json
import time
import requests
import feedparser
from bs4 import BeautifulSoup
from datetime import datetime
import google.generativeai as genai

# ---------------------------------------------------------
# 1. AYARLAR VE KÜTÜPHANE HAZIRLIKLARI
# ---------------------------------------------------------

# Gemini API Anahtarı (GitHub Actions varsayılan ortam değişkeni)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "BURAYA_GEMINI_API_KEY_YAZABILIRSINIZ")
genai.configure(api_key=GEMINI_API_KEY)

# Çekilecek RSS Kaynakları
RSS_FEEDS = [
    "https://www.ensonhaber.com/rss/ensonhaber.xml",
    "https://www.trthaber.com/sondakika_articles.rss",
    "https://www.aa.com.tr/tr/rss/default?cat=gundem"
]

NEWS_JSON_PATH = "public/news.json"


# ---------------------------------------------------------
# 2. YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------

def kategori_duzelt(cat):
    """Yazım hatalı etiketleri düzeltir."""
    if not cat:
        return "GÜNDEM"
    c = str(cat).strip().upper()
    mapping = {
        'SUC': 'SUÇ',
        'TRAFIG': 'TRAFİK',
        'TRAFIK': 'TRAFİK',
        'EKONOMI': 'EKONOMİ',
        'IC HABERLER': 'İÇ HABERLER',
        'SAGLIK': 'SAĞLIK',
        'EGITIM': 'EĞİTİM',
        'POLITIKA': 'POLİTİKA',
        'DUNYA': 'DÜNYA',
        'TEKNOLOJI': 'TEKNOLOJİ'
    }
    return mapping.get(c, c)


def haber_gorseli_getir(entry):
    """
    Haberin GERÇEK kapak fotoğrafını bulur:
    1. RSS medya etiketlerini kontrol eder.
    2. RSS özetindeki <img> etiketini arar.
    3. BULAMAZSA: Haberin web sayfasına gidip 'og:image' resmini çekerek stok resmi önler.
    """
    # 1. RSS Enclosures
    if 'enclosures' in entry and len(entry.enclosures) > 0:
        for enc in entry.enclosures:
            if enc.get('type', '').startswith('image') or enc.get('href', '').endswith(('.jpg', '.png', '.jpeg', '.webp')):
                return enc.href

    # 2. Media Content
    if 'media_content' in entry and len(entry.media_content) > 0:
        return entry.media_content[0].get('url')

    # 3. HTML Description içindeki img
    content_html = entry.get('summary', '') + entry.get('description', '')
    if '<img' in content_html:
        try:
            soup = BeautifulSoup(content_html, 'html.parser')
            img = soup.find('img')
            if img and img.get('src'):
                return img['src']
        except Exception:
            pass

    # 4. KESİN ÇÖZÜM: Web sitesine gidip <meta property="og:image"> oku
    link = entry.get('link')
    if link:
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            res = requests.get(link, headers=headers, timeout=4)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                og_img = soup.find('meta', property='og:image') or soup.find('meta', attrs={'name': 'og:image'})
                if og_img and og_img.get('content'):
                    return og_img['content']
        except Exception as e:
            print(f"⚠️ Görsel kazınamadı ({link}): {e}")

    # Nötr varsayılan manzara görseli
    return "https://images.unsplash.com/photo-1585829365295-ab7cd400c167?w=800"


# ---------------------------------------------------------
# 3. ANA AKIŞ FONKSİYONU
# ---------------------------------------------------------

def haberleri_islemden_gecir():
    print("🔄 RSS akışları taranıyor...")
    ham_haberler = []

    # 1. RSS Verilerini Topla
    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:5]:  # Kaynak başına 5 haber
                gorsel = haber_gorseli_getir(entry)
                ham_haberler.append({
                    "orijinal_baslik": entry.get("title", ""),
                    "ozet": entry.get("summary", ""),
                    "link": entry.get("link", ""),
                    "kaynak": parsed.feed.get("title", "Haber Kaynağı"),
                    "gorsel": gorsel
                })
        except Exception as e:
            print(f"⚠️ RSS çekme hatası ({feed_url}): {e}")

    if not ham_haberler:
        print("❌ Hiç haber çekilemedi.")
        return

    print(f" Toplam {len(ham_haberler)} haber toplandı. Yapay zeka ile işleniyor...")

    # 2. Yapay Zekaya Gönderilecek Prompt (Instagram Karakter Sınırı Korumalı)
    prompt = f"""
    Aşağıdaki haber listesini incele. En önemli ve ilgi çekici 4 haberi seç.
    Seçtiğin haberleri Türkçe olarak yeniden özgünleştir.

    ÖNEMLİ KURAL: Instagram metin sınırına takılmamak için özetleri kısa ve öz tut!

    İstenen JSON Yapısı (Sadece geçerli bir JSON listesi döndür, ekstra metin yazma):
    [
      {{
        "id": 1,
        "baslik": "Maksimum 8-10 kelimelik dikkat çekici başlık",
        "kisa_aciklama": "Maksimum 15-20 kelimelik (en fazla 140 karakter) öz ve net haber özeti.",
        "detay": "Haberin detaylı açıklaması",
        "kategori": "GÜNDEM / İÇ HABERLER / SUÇ / TRAFİK / EKONOMİ / DÜNYA / TEKNOLOJİ"
      }}
    ]

    Haber Listesi:
    {json.dumps([h['orijinal_baslik'] for h in ham_haberler], ensure_ascii=False)}
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        ai_data = json.loads(cleaned_response)
    except Exception as e:
        print(f"❌ Yapay Zeka hatası: {e}")
        return

    # 3. Mevcut JSON Verisini Oku
    mevcut_haberler = []
    if os.path.exists(NEWS_JSON_PATH):
        try:
            with open(NEWS_JSON_PATH, "r", encoding="utf-8") as f:
                mevcut_haberler = json.load(f)
        except Exception:
            mevcut_haberler = []

    simdi_str = datetime.now().strftime("%d.%m.%Y - %H:%M")
    yeni_eklenenler = []

    # 4. Akıllı Görsel Eşleştirme ve Hazırlık
    for item in ai_data:
        item_title = item.get("baslik", "").lower()
        
        # Kelime bazlı doğru resmi bulma algoritması
        best_match = ham_haberler[0]
        max_score = -1

        for raw in ham_haberler:
            raw_title = raw["orijinal_baslik"].lower()
            score = sum(1 for word in item_title.split() if len(word) > 3 and word in raw_title)
            if score > max_score:
                max_score = score
                best_match = raw

        temiz_kategori = kategori_duzelt(item.get("kategori"))

        yeni_haber = {
            "id": f"{int(time.time())}_{item.get('id', 1)}",
            "category": temiz_kategori,
            "title": item.get("baslik"),
            "summary": item.get("kisa_aciklama"),
            "fullText": item.get("detay"),
            "image": best_match["gorsel"],  # %100 Doğru kapak fotoğrafı
            "source": best_match["kaynak"],
            "sourceUrl": best_match["link"],
            "date": simdi_str
        }
        yeni_eklenenler.append(yeni_haber)

    # 5. Yeni Haberleri En Üste Ekle ve Maksimum 30 Haber Tut
    toplam_haberler = yeni_eklenenler + mevcut_haberler
    toplam_haberler = toplam_haberler[:30]

    # 6. JSON Dosyasına Yaz
    with open(NEWS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(toplam_haberler, f, ensure_ascii=False, indent=2)

    print(f" Başarıyla {len(yeni_eklenenler)} haber eklendi ve kaydedildi!")


if __name__ == "__main__":
    haberleri_islemden_gecir()