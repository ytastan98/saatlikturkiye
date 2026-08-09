from PIL import Image, ImageDraw, ImageFont
import json
import textwrap

def profesyonel_gorsel_olustur(haber_json):
    # --- AYARLAR VE PALET ---
    genislik, yukseklik = 1080, 1080 # Instagram Kare
    arka_plan_rengi = (18, 18, 18) # Koyu Minimalist Siyah/Gri
    
    # Haber verisini json'dan oku
    try:
        data = json.loads(haber_json)
        baslik = data.get("baslik", "GÜNDEM")
        aciklama = data.get("aciklama", "Haber detayı bulunamadı.")
        kategori = data.get("kategori", "TÜRKİYE").upper()
    except:
        return "JSON Hatalı!"

    # Renk Paleti (Senin o minimalist çizgilerin için)
    palet = {
        "EKONOMİ": (76, 175, 80),  # Yeşil
        "SPOR": (255, 152, 0),     # Turuncu
        "DÜNYA": (33, 150, 243),   # Mavi
        "TEKNOLOJİ": (156, 39, 176),# Mor
        "TÜRKİYE": (244, 67, 54)   # Kırmızı
    }
    vurgu_rengi = palet.get(kategori, (255, 255, 255))

    # Boş Tuvali Minimalist Arka Planla Oluştur
    img = Image.new('RGB', (genislik, yukseklik), color=arka_plan_rengi)
    draw = ImageDraw.Draw(img)

    # --- YAZI TİPLERİ VE PROFESYONEL AYARLAR ---
    # Bilgisayarındaki en düzgün fontu seçmelisin (örn: arialbd.ttf).
    # Profesyonel görünüm için yazı boyutlarını ve aralıklarını hassas ayarladık.
    baslik_font_size = 72
    ozet_font_size = 48
    ust_bilgi_font_size = 36
    
    try:
        font_baslik = ImageFont.truetype("arialbd.ttf", baslik_font_size)
        font_ozet = ImageFont.truetype("arial.ttf", ozet_font_size)
        font_ust = ImageFont.truetype("arial.ttf", ust_bilgi_font_size)
    except:
        font_baslik = ImageFont.load_default()
        font_ozet = ImageFont.load_default()
        font_ust = ImageFont.load_default()

    # --- DÜZEN VE ÇİZİM (En Kritik Kısım) ---
    baslangic_x = 100
    sol_cizgi_genisligi = 15
    sol_cizgi_boyu = 550 # Yazı alanını kapsayacak şekilde
    
    # 1. Profesyonel Kategori Çizgisi
    draw.rectangle([baslangic_x, 300, baslangic_x + sol_cizgi_genisligi, 300 + sol_cizgi_boyu], fill=vurgu_rengi)

    # 2. Üst Bilgiler
    draw.text((baslangic_x + 50, 100), "SAATLİK GÜNDEM ÖZETİ", fill=(150, 150, 150), font=font_ust)
    draw.text((baslangic_x + 50, 150), kategori, fill=vurgu_rengi, font=font_ust)

    # 3. Yazıyı Otomatik Sığdırma (textwrap)
    yazi_baslangic_y = 300
    yazi_metin_x = baslangic_x + 60 # Çizgiden sağa boşluk
    
    # Başlığı böl (Maksimum 25 karakterde bir alt satıra geç)
    baslik_bolumler = textwrap.wrap(baslik, width=25)
    for line in baslik_bolumler:
        draw.text((yazi_metin_x, yazi_baslangic_y), line, fill=(255, 255, 255), font=font_baslik)
        yazi_baslangic_y += baslik_font_size + 10 # Satır aralığı
        
    yazi_baslangic_y += 30 # Başlık ile özet arasına boşluk

    # Özeti böl (Maksimum 45 karakterde bir alt satıra geç)
    ozet_bolumler = textwrap.wrap(aciklama, width=45)
    for line in ozet_bolumler:
        # Eğer yazi_baslangic_y çok aşağı inerse sığmaz, buraya sınır koyabiliriz
        if yazi_baslangic_y > 850:
             break
        draw.text((yazi_metin_x, yazi_baslangic_y), line, fill=(210, 210, 210), font=font_ozet)
        yazi_baslangic_y += ozet_font_size + 15 # Satır aralığı

    # --- KAYDET ---
    file_name = "profesyonel_gorsel.png"
    img.save(file_name)
    print(f"✅ Profesyonel minimalist görsel oluşturuldu: {file_name}")

# --- TEST VERİSİ (AI Studio'dan gelen veri gibi) ---
haber_verisi = '{"baslik": "Akaryakıta Dev İndirim Geliyor", "aciklama": "Motorin fiyatlarında bu gece yarısından itibaren 5 TL düşüş bekleniyor. Benzin fiyatlarında ise henüz bir değişiklik yok.", "kategori": "EKONOMİ"}'

# Kodu çalıştır
profesyonel_gorsel_olustur(haber_verisi)