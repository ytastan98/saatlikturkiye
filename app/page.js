'use client';
import { useState, useEffect } from 'react';

const normalizeCat = (cat) => {
  if (!cat) return 'GÜNDEM';
  const c = cat.trim().toUpperCase();
  const map = {
    'SUC': 'SUÇ',
    'TRAFIG': 'TRAFİK',
    'TRAFIK': 'TRAFİK',
    'TRAFFIK': 'TRAFİK',
    'EKONOMI': 'EKONOMİ',
    'IC HABERLER': 'İÇ HABERLER',
    'SAGLIK': 'SAĞLIK',
    'EGITIM': 'EĞİTİM',
    'POLITIKA': 'POLİTİKA',
    'DUNYA': 'DÜNYA',
    'TEKNOLOJI': 'TEKNOLOJİ'
  };
  return map[c] || c;
};

export default function Home() {
  const [news, setNews] = useState([]);
  const [filteredNews, setFilteredNews] = useState([]);
  const [search, setSearch] = useState('');
  const [selectedCat, setSelectedCat] = useState('TÜMÜ');
  const [weather, setWeather] = useState(null);
  const [prayerTimes, setPrayerTimes] = useState(null);
  const [city, setCity] = useState('Konum alınıyor...');

  useEffect(() => {
    // 1. Haberleri Çek
    fetch('/news.json')
      .then((res) => res.json())
      .then((data) => {
        const cleanedData = data.map(item => ({
          ...item,
          category: normalizeCat(item.category)
        }));
        setNews(cleanedData);
        setFilteredNews(cleanedData);
      })
      .catch(() => setNews([]));

    // 2. Yedekli IP Konum Servisi (İstemci Tabanlı)
    const getLocationAndWidgets = async () => {
      let userCity = 'İstanbul';
      let lat = 41.0082;
      let lon = 28.9784;

      try {
        // 1. Tercih: ipapi.co
        const res1 = await fetch('https://ipapi.co/json/');
        if (res1.ok) {
          const geo1 = await res1.json();
          if (geo1.city && geo1.latitude && geo1.longitude) {
            userCity = geo1.city;
            lat = geo1.latitude;
            lon = geo1.longitude;
          }
        } else {
          throw new Error('ipapi limit');
        }
      } catch (err1) {
        try {
          // 2. Tercih (Yedek Servis): ip-api.com
          const res2 = await fetch('https://ip-api.com/json/?fields=status,city,lat,lon');
          const geo2 = await res2.json();
          if (geo2.status === 'success' && geo2.city) {
            userCity = geo2.city;
            lat = geo2.lat;
            lon = geo2.lon;
          }
        } catch (err2) {
          console.log('Konum servislerine ulaşılamadı, varsayılan İstanbul kullanılıyor.');
        }
      }

      setCity(userCity);

      // Hava Durumu Verisi
      fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current_weather=true`)
        .then(res => res.json())
        .then(w => setWeather(w.current_weather))
        .catch(() => {});

      // Ezan Vakiti Verisi
      fetch(`https://api.aladhan.com/v1/timings?latitude=${lat}&longitude=${lon}&method=13`)
        .then(res => res.json())
        .then(p => setPrayerTimes(p.data?.timings))
        .catch(() => {});
    };

    getLocationAndWidgets();
  }, []);

  useEffect(() => {
    let result = news;
    if (selectedCat !== 'TÜMÜ') {
      result = result.filter(item => item.category === selectedCat);
    }
    if (search.trim() !== '') {
      result = result.filter(item => 
        item.title.toLowerCase().includes(search.toLowerCase()) || 
        item.summary.toLowerCase().includes(search.toLowerCase())
      );
    }
    setFilteredNews(result);
  }, [search, selectedCat, news]);

  const categories = ['TÜMÜ', ...Array.from(new Set(news.map(item => item.category)))];

  return (
    <div style={{ backgroundColor: '#09090b', color: '#f4f4f5', minHeight: '100vh', fontFamily: 'system-ui, sans-serif', overflowX: 'hidden' }}>
      
      {/* HEADER */}
      <header style={{ borderBottom: '1px solid #27272a', backgroundColor: '#000', padding: '12px 16px', position: 'sticky', top: 0, zIndex: 50, width: '100%', boxSizing: 'border-box' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          
          <h1 style={{ margin: 0, fontSize: '20px', fontWeight: '800', letterSpacing: '-0.5px' }}>
            SAATLİK<span style={{ color: '#e11d48' }}>TÜRKİYE</span>
          </h1>

          <div style={{ flex: '1 1 180px', maxWidth: '300px', width: '100%' }}>
            <input 
              type="text" 
              placeholder="Haberlerde ara..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ 
                backgroundColor: '#18181b', 
                border: '1px solid #27272a', 
                color: '#fff', 
                padding: '8px 14px', 
                borderRadius: '20px', 
                width: '100%', 
                fontSize: '13px',
                boxSizing: 'border-box',
                outline: 'none'
              }}
            />
          </div>

        </div>
      </header>

      <main style={{ maxWidth: '1200px', margin: '20px auto', padding: '0 16px', boxSizing: 'border-box' }}>
        
        {/* BİLGİ WİDGETLARI */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px', marginBottom: '20px' }}>
          
          {/* Hava Durumu */}
          <div style={{ backgroundColor: '#111113', border: '1px solid #27272a', borderRadius: '12px', padding: '14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <span style={{ fontSize: '11px', color: '#a1a1aa' }}>📍 Canlı Hava Durumu</span>
              <h4 style={{ margin: '4px 0 0 0', fontSize: '16px', color: '#ffffff' }}>{city}</h4>
            </div>
            {weather ? (
              <div style={{ textAlign: 'right' }}>
                <span style={{ fontSize: '24px', fontWeight: 'bold', color: '#38bdf8' }}>{Math.round(weather.temperature)}°C</span>
                <span style={{ display: 'block', fontSize: '10px', color: '#a1a1aa' }}>Rüzgar: {weather.windspeed} km/s</span>
              </div>
            ) : <span style={{ fontSize: '12px', color: '#71717a' }}>Yükleniyor...</span>}
          </div>

          {/* Ezan Saatleri */}
          <div style={{ backgroundColor: '#111113', border: '1px solid #27272a', borderRadius: '12px', padding: '14px' }}>
            <span style={{ fontSize: '11px', color: '#a1a1aa', display: 'block', marginBottom: '6px' }}>🕌 Günlük Ezan Saatleri ({city})</span>
            {prayerTimes ? (
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#f4f4f5' }}>
                <div><small style={{ color: '#71717a' }}>İmsak</small><br/><b>{prayerTimes.Fajr}</b></div>
                <div><small style={{ color: '#71717a' }}>Öğle</small><br/><b>{prayerTimes.Dhuhr}</b></div>
                <div><small style={{ color: '#71717a' }}>İkindi</small><br/><b>{prayerTimes.Asr}</b></div>
                <div><small style={{ color: '#71717a' }}>Akşam</small><br/><b>{prayerTimes.Maghrib}</b></div>
                <div><small style={{ color: '#71717a' }}>Yatsı</small><br/><b>{prayerTimes.Isha}</b></div>
              </div>
            ) : <span style={{ fontSize: '12px', color: '#71717a' }}>Vakitler yükleniyor...</span>}
          </div>

        </div>

        {/* KATEGORİ FİLTRELERİ */}
        <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '10px', marginBottom: '15px', WebkitOverflowScrolling: 'touch' }}>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCat(cat)}
              style={{
                backgroundColor: selectedCat === cat ? '#e11d48' : '#18181b',
                color: '#fff',
                border: '1px solid #27272a',
                padding: '5px 14px',
                borderRadius: '16px',
                cursor: 'pointer',
                fontSize: '12px',
                whiteSpace: 'nowrap',
                fontWeight: selectedCat === cat ? 'bold' : 'normal'
              }}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* HABER LİSTESİ */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
          {filteredNews.length > 0 ? (
            filteredNews.map((item) => {
              const imageSrc = item.imageUrl || item.image; // GÖRSEL DÜZELTMESİ
              return (
                <article key={item.id} style={{ backgroundColor: '#111113', border: '1px solid #27272a', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                  {imageSrc && (
                    <img src={imageSrc} alt={item.title} style={{ width: '100%', height: '170px', objectFit: 'cover' }} />
                  )}
                  <div style={{ padding: '16px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                    <div>
                      <span style={{ color: '#60a5fa', fontSize: '11px', fontWeight: 'bold', letterSpacing: '0.5px' }}>
                        #{item.category}
                      </span>
                      <h3 style={{ fontSize: '16px', fontWeight: '700', margin: '6px 0', lineHeight: '1.4' }}>
                        {item.title}
                      </h3>
                      <p style={{ color: '#a1a1aa', fontSize: '13px', lineHeight: '1.5', margin: '0 0 12px 0' }}>
                        {item.summary}
                      </p>
                    </div>
                    <div style={{ borderTop: '1px solid #27272a', paddingTop: '8px', display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#71717a' }}>
                      <span>📅 {item.date}</span>
                      {item.sourceUrl && (
                        <a href={item.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#38bdf8', textDecoration: 'none', fontWeight: '600' }}>
                          Detay →
                        </a>
                      )}
                    </div>
                  </div>
                </article>
              );
            })
          ) : (
            <p style={{ color: '#71717a', gridColumn: '1/-1', textAlign: 'center', padding: '30px' }}>Haber bulunamadı.</p>
          )}
        </div>
      </main>
    </div>
  );
}