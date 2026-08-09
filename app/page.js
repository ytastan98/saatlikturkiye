import fs from 'fs';
import path from 'path';

export const revalidate = 0; // Her istekte güncel json'ı okur

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
    <main style={{ backgroundColor: '#000', color: '#fff', minHeight: '100vh', padding: '20px', fontFamily: 'sans-serif' }}>
      <h1 style={{ color: '#e11d48', textAlign: 'center', marginBottom: '30px' }}>SAATLİK TÜRKİYE — CANLI HABER AKIŞI</h1>
      
      <div style={{ maxWidth: '800px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {news.map((item) => (
          <div key={item.id} style={{ border: '1px solid #27272a', padding: '20px', borderRadius: '8px', backgroundColor: '#111113' }}>
            <span style={{ color: '#60a5fa', fontWeight: 'bold', fontSize: '12px' }}>#{item.category}</span>
            <h2 style={{ fontSize: '20px', margin: '10px 0' }}>{item.title}</h2>
            <p style={{ color: '#d4d4d8', lineHeight: '1.5' }}>{item.summary}</p>
            <small style={{ color: '#71717a', display: 'block', marginTop: '10px' }}>Tarih: {item.date}</small>
          </div>
        ))}
      </div>
    </main>
  );
}