export const metadata = {
  title: 'Saatlik Türkiye — Canlı Haber Akışı',
  description: 'Saatlik güncellenen Türkiye ve dünya gündemi.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="tr">
      <body style={{ margin: 0, padding: 0, backgroundColor: '#000' }}>
        {children}
      </body>
    </html>
  );
}