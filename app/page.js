import fs from 'fs';
import path from 'path';

export const revalidate = 0; // Her istekte anlık güncel haber okur

export default function Home() {
  const filePath = path.join(process.cwd(), 'public', 'news.json');
  let news = [];

  try {
    const fileData = fs.readFileSync(filePath, 'utf8');
    news = JSON.parse(fileData);
  } catch (err) {
    news = [];
  }

  return (
    <div style={{ backgroundColor: '#09090b', color: '#f4f4f5', minHeight: '100vh', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
      {/* HEADER */}
      <header style={{ borderBottom: '1px solid #27272a', backgroundColor: '#000', padding: '15px 20px', sticky: 'top' }}>
        <div style={{ maxWidth: '1100px', margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '800', letterSpacing: '-0.5px' }}>
            SAATLİK<span style={{ color: '#e11d48' }}>TÜRKİYE</span>
          </h1>
          <span style={{ backgroundColor: '#e11d48', color: '#fff', padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 'bold' }}>
            🔴 CANLI YAYIN
          </span>
        </div>
      </header>

      {/* İÇERİK */}
      <main style={{ maxWidth: '1100px', margin: '30px auto', padding: '0 20px' }}>
        <h2 style={{ fontSize: '18px', color: '#a1a1aa', marginBottom: '20px', textTransform: 'uppercase', letterSpacing: '1px' }}>
          Öne Çıkan Son Dakika Haberleri
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
          {news.map((item, index) => (
            <article key={item.id || index} style={{ backgroundColor: '#111113', border: '1px solid #27272a', borderRadius: '12px', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {item.image && (
                <img src={item.image} alt={item.title} style={{ width: '100%', height: '200px', objectFit: 'cover' }} />
              )}
              <div style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <span style={{ color: '#3b82f6', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                    #{item.category || 'GÜNDEM'}
                  </span>
                  <h3 style={{ fontSize: '18px', fontWeight: '700', margin: '10px 0', lineHeight: '1.4', color: '#fff' }}>
                    {item.title}
                  </h3>
                  <p style={{ color: '#a1a1aa', fontSize: '14px', lineHeight: '1.6', margin: '0 0 15px 0' }}>
                    {item.summary}
                  </p>
                </div>
                <div style={{ borderTop: '1px solid #27272a', paddingTop: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: '#71717a' }}>
                  <span>{item.date}</span>
                  {item.sourceUrl && (
                    <a href={item.sourceUrl} target="_blank" rel="noreferrer" style={{ color: '#f4f4f5', textDecoration: 'none', fontWeight: '600' }}>
                      Kaynak Kaynağı →
                    </a>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      </main>

      {/* FOOTER */}
      <footer style={{ borderTop: '1px solid #27272a', textAlign: 'center', padding: '30px', marginTop: '50px', color: '#71717a', fontSize: '14px' }}>
        <p>© {new Date().getFullYear()} Saatlik Türkiye — Tüm Hakları Saklıdır.</p>
      </footer>
    </div>
  );
}