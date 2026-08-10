from PIL import Image

def mukemmel_profil_fotosu_yap():
    # 1080x1080 tam kare boyutunda sıfır hata, dümdüz siyah arka plan oluşturuyoruz
    w, h = 1080, 1080
    profil_img = Image.new("RGB", (w, h), color=(0, 0, 0)) # Tam siyah (0,0,0)
    
    # Kendi logonun dosya adını buraya yaz (Örn: logo.png)
    # Logonun arka planının şeffaf (PNG) olması en iyi sonucu verir
    try:
        logo = Image.open("logo.png").convert("RGBA")
        
        # Logonun boyutunu kareye uygun şekilde ölçekle (isteğe göre ayarlanabilir)
        logo.thumbnail((700, 700))
        
        # Logoyu tam ortaya yerleştir
        pos_x = (w - logo.width) // 2
        pos_y = (h - logo.height) // 2
        
        # Şeffaflığı koruyarak siyah arka planın üzerine yapıştır
        profil_img.paste(logo, (pos_x, pos_y), logo)
    except Exception as e:
        print(f"Logo eklenirken hata: {e}")
        
    profil_img.save("profil_siyah.png")
    print("✅ Dümdüz siyah arka planlı profil fotoğrafı 'profil_siyah.png' olarak hazırlandı!")

if __name__ == "__main__":
    mukemmel_profil_fotosu_yap()