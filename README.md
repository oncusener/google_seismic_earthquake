# Deprem Erken Uyarı Sistemi Simülasyonu

Marmara Bölgesi istasyon ağını simüle eden, P dalgalarını gerçek zamanlı STA/LTA algoritmasıyla algılayan ve $N \ge 10$ cihaz eşiğiyle depremi doğrulayarak erken uyarı üreten uçtan uca simülasyon platformu.

---
## 📌 Proje Özellikleri

* **Gerçek Zamanlı Sinyal İşleme:** Sensörlerden alınan ham sismik verilerdeki sabit kaymalar (DC ofset) ve düşük frekanslı gürültüler, 1. derece yüksek geçiren (High-Pass) filtre kullanılarak azaltılır. Filtrede $\alpha = 0.95$ katsayısı kullanılır.
* **P Dalgası Algılama:** Her istasyonun sismik verisi bağımsız olarak analiz edilir[cite: 11]. 0.5 saniyelik kısa süreli ortalama (STA) ve 10.0 saniyelik uzun süreli ortalama (LTA) karşılaştırılarak P dalgası algılanır. $\text{STA}/\text{LTA}$ oranı 4.5 veya üzerine çıktığında istasyon tetiklenir.
* **10 Cihaz Onay Kuralı:** Tek bir istasyonun oluşturabileceği yanlış alarmları önlemek amacıyla deprem, en az 10 bağımsız istasyon tarafından algılanana kadar doğrulama aşamasında (`Level 1`) tutulur.
* **Dinamik Merkez Üssü ve Büyüklük Hesabı:** Depremi algılayan istasyonların konumları ve algılama zamanları kullanılarak merkez üssünün yaklaşık enlem ve boylamı zaman ağırlıklı ortalama yöntemiyle hesaplanır. Ayrıca sensörlerden elde edilen tepe yer değiştirme genliği ($P_d$) ve hiposantr mesafesi kullanılarak deprem büyüklüğü ($M$) kestirilir.
* **Net Erken Uyarı Süresi (Lead Time):** P ve S dalgalarının farklı hızlarda ilerlemesi esas alınarak ($V_p = 6.0\text{ km/s}$, $V_s = 3.5\text{ km/s}$), P dalgasının algılanması ile yıkıcı S dalgasının hedef noktaya ulaşması arasındaki süre hesaplanır. Bu süreden ağ ve sunucu gecikmeleri düşülerek kalan net tahmini uyarı süresi belirlenir.
* **Canlı WebSocket Yayını ve Leaflet Arayüzü:** FastAPI üzerinden WebSocket bağlantısı kullanılarak istasyonlardan gelen sarsıntı bilgileri, P/S dalgalarının yayılımı, merkez üssü animasyonu ve alarm durumları gerçek zamanlı olarak React ve Leaflet tabanlı kontrol paneline aktarılır.
---
## 📁 Proje Mimarisi
```text
├── backend/
│   ├── centroid.py              # Zaman ağırlıklı merkez üssü kestirim algoritması
│   ├── connection_manager.py    # WebSocket istemci havuz yöneticisi
│   ├── event_engine.py          # Erken uyarı karar motoru ve onay kuralları
│   ├── magnitude.py             # Pd tepe genliği ve hiposantr üzerinden büyüklük hesabı
│   ├── main.py                  # FastAPI sunucusu ve WebSocket uç noktası
│   ├── mock_data_generator.py   # 50 Hz sentetik sismik dalga üreticisi
│   ├── models.py                # Pydantic veri modelleri ve alarm seviyeleri
│   ├── preprocessing.py         # 1. derece High-pass sinyal filtresi
│   ├── requirements.txt         # Backend Python bağımlılıkları
│   ├── seismo_math.py           # Haversine, mesafe ve lead time hesapları
│   ├── sta_lta.py               # Recursive STA/LTA algoritması
│   └── station_config.py        # Marmara Bölgesi 15 istasyon koordinat listesi
├── DepremSimulasyon/
│   └── SeismicDashboard.jsx     # React & Leaflet tabanlı canlı kontrol paneli
├── package.json                 # Frontend bağımlılıkları ve scriptleri
├── .gitignore                   # Git harici tutulacak dosyalar
└── README.md                    # Proje dokümantasyonu
```

---
# Alarm Seviyeleri

| Seviye | Adı | Açıklama |
| :---: | :--- | :--- |
| **0** | `LEVEL_0_NORMAL` | Sistem normal, aktif sarsıntı yok. |
| **1** | `LEVEL_1_VERIFYING` | 1–9 arası cihaz tetiklendi, deprem doğrulanıyor. |
| **2** | `LEVEL_2_REJECTED` | Sinyal gürültü testi yapıldı, yanlış alarm engellendi. |
| **3** | `LEVEL_3_INFO` | 10 cihaz onayladı ancak deprem büyüklüğü $M < 3.0$. |
| **4** | `LEVEL_4_EARLY_WARNING` | 10 cihaz onayladı ve $M \ge 3.0$ (Kritik Erken Uyarı). |

---

## Kurulum ve Çalıştırma Rehberi

### 📋 Ön Gereksinimler
- [Python 3.9+](https://www.python.org/downloads/)
- [Node.js (v18+) & npm](https://nodejs.org/)
- [Git](https://git-scm.com/)

---

### 1️⃣ Backend'i Başlatma (FastAPI)

1. **Backend klasörüne gidin:**
   ```bash
   cd backend
   ```

2. **Python sanal ortamı (venv) oluşturun ve aktif edin:**
   - **Windows:**
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **macOS / Linux:**
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

3. **Gerekli bağımlılıkları yükleyin:**
   ```bash
   pip install -r requirements.txt
   ```

4. **FastAPI sunucusunu başlatın:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   > Backend `http://127.0.0.1:8000` adresinde çalışacaktır.

---

### 2️⃣ Frontend'i Başlatma (React)

1. **Frontend klasörüne gidin ve paketleri yükleyin:**
   ```bash
   cd DepremSimulasyon
   npm install
   ```

2. **Geliştirici sunucusunu başlatın:**
   ```bash
   npm run dev
   ```

---

## Test Senaryoları (Simülasyon Butonları)

Arayüzün alt panelindeki butonları kullanarak sistemin tepkilerini test edebilirsiniz:

1. **1. Gerçek Deprem:** $M \ge 6.0$ büyüklüğünde sentetik deprem üretir; 10 cihaz onaylandığında Seviye 4 (Kırmızı Alarm) devreye girer.
2. **2. Düşük Şiddet:** $M < 3.0$ mikro sarsıntı testi; sistem doğrular fakat büyüklük düşük olduğu için Seviye 3 (Bilgi Alarmı) üretir.
3. **3. Ağ Gecikmesi:** İstasyon verilerine 350 ms rastgele gecikme ekler; sistemin asenkron çalışma performansını test eder.
4. **4. Gürültü Testi:** Rastgele sismik olmayan gürültü verisi gönderir; eşik değer aşılmadığı için sistem Seviye 2 (Yanlış Alarm Engellendi) durumuna geçer.
5. **5. Paket Kaybı:** %25 paket kaybı simüle edilir; eksik verilere rağmen sistemin 10 cihaz onayını başarıyla yakalaması test edilir.
6. **Durdur:** Simülasyonu anında durdurur ve sistemi Seviye 0 (Normal) durumuna sıfırlar.