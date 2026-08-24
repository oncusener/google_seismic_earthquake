"""
Simülasyon senaryolarını başlatan, karar motorunu çalıştıran ve 
sonuçları WebSocket üzerinden canlı yayınlayan FastAPI ana sunucu modülü
"""
from __future__ import annotations  # İleriye dönük Python tür ipuçlarının modern sözdizimiyle çalışmasını sağlar
import asyncio  # Asenkron görev yönetimi, uyutma ve eşzamanlı süreçleri kontrol etmek için kullanılır
import logging  # Uygulama çalışma kayıtlarını ve durum mesajlarını loglamak için içeri aktarılır

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # FastAPI ana uygulama çatısını ve WebSocket sınıflarını içeri aktarır
from fastapi.middleware.cors import CORSMiddleware  # Tarayıcıların frontend-backend iletişimindeki CORS(bir web sitesinin, tarayıcı üzerinden farklı bir adreste çalışan sunucuya istek atmasını engelleyen) engeline takılmasını önler
from models import SystemMessage, AlertMessage, AlertLevel, WaveMessage  # Veri modellerini ve alarm seviyesi sabitlerini içeri aktarır
from station_config import STATIONS  # Marmara Bölgesi 15 istasyon listesini içeri aktarır
from mock_data_generator import create_random_event, stream_event, SAMPLE_RATE_HZ  # Sentetik veri üretici fonksiyonları ve frekans sabitini içeri aktarır
from event_engine import EventEngine  # Sarsıntı algılama, büyüklük ve merkez üssü kestirimini yöneten karar motorunu içeri aktarır
from connection_manager import ConnectionManager  # Bağlı tüm WebSocket istemcilerine veri dağıtan bağlantı yöneticisini içeri aktarır

logging.basicConfig(level=logging.INFO)  # Loglama seviyesini bilgi düzeyine ayarlar
logger = logging.getLogger("eews")  # Deprem erken uyarı sistemine özel logger nesnesi oluşturur
app = FastAPI(title="Deprem Erken Uyarı Sistemi")  # FastAPI uygulama örneğini başlığıyla birlikte başlatır

app.add_middleware(  # Uygulamaya ara yazılım (middleware) ekleme adımını başlatır.
    CORSMiddleware,  # CORS ara yazılımını etkinleştirir.
    allow_origins=["*"],  # Herhangi bir kaynaktan gelen isteklere izin verir
    allow_methods=["*"],  # Tüm HTTP metodlarına (GET, POST vb.) izin verir
    allow_headers=["*"],  # Tüm HTTP başlıklarına izin verir
)  

manager = ConnectionManager()  # Canlı veri yayını yapacak merkezi WebSocket yöneticisini başlatır
engine = EventEngine(stations=STATIONS, sample_rate_hz=SAMPLE_RATE_HZ)  # 15 istasyon ve 50 Hz frekansla karar motorunu başlatır
_simulation_task: asyncio.Task | None = None  # Arka planda çalışan aktif simülasyon görevini takip eden global değişkendir


@app.get("/stations")  # İstasyon listesini döndüren REST API uç noktasını tanımlar
def get_stations():  # İstasyon listesini getiren fonksiyonu tanımlar
    return [s.model_dump() for s in STATIONS]  # 15 istasyonun koordinat ve kimlik bilgilerini JSON uyumlu liste olarak döndürür


@app.websocket("/ws")  # Frontend ekranlarının canlı veri dinleyeceği WebSocket uç noktasını tanımlar
async def websocket_endpoint(ws: WebSocket):  # Yeni bağlanan WebSocket istemcilerini yöneten fonksiyondur
    await manager.connect(ws)  # İstemcinin bağlantı isteğini onaylayıp aktif bağlantılar havuzuna ekler
    print(f"--> [WS] İstemci bağlandı. Toplam: {manager.count}")  # Sunucu konsoluna yeni bağlantıyı ve toplam istemci sayısını yazar
    await ws.send_text(  # Yeni bağlanan ekrana ilk durum mesajını iletir
        AlertMessage(  # Normal durum alarm nesnesi oluşturur
            level=AlertLevel.LEVEL_0_NORMAL,  # Seviye 0 (Normal) olarak belirler
            message="Sistem normal – aktif sarsıntı algılanmadı."  # Başlangıç durum metnini tanımlar
        ).model_dump_json()  # Alarm nesnesini JSON formatına çevirip iletir
    )  # İlk mesaj gönderimini tamamlar
    try:  # İstemci bağlı kaldığı sürece çalışacak dinleme bloğunu başlatır
        while True:  # İstemciden gelebilecek mesajları sürekli dinleyen döngüdür.
            await ws.receive_text()  # İstemciden metin mesajı bekler
    except WebSocketDisconnect:  # Kullanıcı sayfayı kapattığında veya bağlantı koptuğunda devreye girer
        await manager.disconnect(ws)  # Kopan istemciyi aktif bağlantı listesinden çıkarır
        print("--> [WS] İstemci ayrıldı.")  # Konsola istemcinin ayrıldığını bildirir


@app.post("/simulate")  # Deprem simülasyonunu başlatan HTTP POST uç noktasını tanımlar
async def start_simulation(  # Simülasyon parametrelerini alıp süreci başlatan fonksiyondur
    duration_s: float = 25.0,  # Toplam simülasyon süresi 
    speed_factor: float = 2.5,  # Simülasyon hızlandırma çarpanı
    network_delay_ms: float = 0.0,  # Senaryo 3 için ağ gecikmesi süresi 
    magnitude: float | None = None,  # Belirlenen özel büyüklük değeri 
    packet_loss_rate: float = 0.0  # Senaryo 5 için paket kaybı oranı
):  # Fonksiyon gövdesi başlangıcı.
    global _simulation_task  # Global görev değişkenine erişim sağlar
    if _simulation_task and not _simulation_task.done():  # Zaten çalışan aktif bir simülasyon var mı kontrol eder
        _simulation_task.cancel()  # Önceki simülasyon görevi devam ediyorsa iptal eder

    event = create_random_event(magnitude=magnitude)  # Senaryoya uygun sentetik bir deprem olayı nesnesi üretir
    engine.reset()  # Karar motorunun geçmiş hafızasını ve istasyon filtrelerini sıfırlar

    print(f"\n==================================================")  
    print(f"[SENARYO BAŞLADI] M{event.true_magnitude} | ID: {event.event_id}")  # Başlatılan depremin büyüklüğünü ve kimliğini konsola yazar.
    print(f"==================================================")  

    async def on_sample(msg: WaveMessage, elapsed_s: float):  # Üretilen her sismik sinyal örneğinde çalışan iç geri çağırım fonksiyonudur
        for out_msg in engine.process_sample(msg.station_id, msg.amplitude, elapsed_s, msg.event_id):  # Örneği karar motorunda işler ve çıkan sonuçları döngüye alır
            if out_msg.get("type") == "trigger":  # Eğer bir istasyon sarsıntı algılayıp tetiklendiyse
                print(f"  [TETİKLENDİ] {out_msg['station_id']}")  # Tetiklenen istasyonun kimliğini konsola basar
            elif out_msg.get("type") == "alert" and out_msg.get("level") == 4:  # Eğer deprem kesinleşip Seviye 4 Erken Uyarı üretildiyse
                print(f"\n>>> [DEPREM DOĞRULANDI] M{out_msg.get('estimated_magnitude')} <<<\n")  # Kestirilen büyüklükle birlikte erken uyarıyı konsola yazar
            await manager.broadcast(out_msg)  # Üretilen tüm mesajları bağlı olan ekranlara canlı olarak yayınlar

    async def run():  # Simülasyon akışını yöneten arka plan asenkron fonksiyonudur
        # Arayüze doğrudan temizleme ve başlatma sinyali
        await manager.broadcast(  # Arayüz paneline simülasyonun başladığına dair sistem mesajı yayınlar
            SystemMessage(message=f"Başlatıldı: M{event.true_magnitude}").model_dump()  # Mesaj içeriğini sözlük yapısına çevirip iletir
        )  
        await stream_event(  # 50 Hz sentetik sismik sinyal akışını başlatan fonksiyonu çağırır
            event,  # Simüle edilecek deprem nesnesi
            STATIONS,  # 15 istasyon listesi
            on_sample,  # Her veri adımında çalışacak fonksiyon
            duration_s=duration_s,  # Simülasyon süresi
            speed_factor=speed_factor,  # Hızlandırma katsayısı
            network_delay_ms=network_delay_ms,  # Ağ gecikmesi parametresi
            packet_loss_rate=packet_loss_rate  # Paket kaybı oranı parametresi
        )  
        print("[SENARYO BİTTİ]\n")  
        await manager.broadcast(SystemMessage(message="Simülasyon tamamlandı.").model_dump())  # Ekranlara tamamlanma bildirimini yayınlar

    _simulation_task = asyncio.create_task(run())  # Simülasyonu sunucuyu kilitlemeden arka planda asenkron görev olarak başlatır
    return {"status": "started", "event_id": event.event_id}  # İsteği yapan istemciye simülasyonun başladığını ve olay kimliğini döner


@app.post("/simulate_noise")  # Yanlış alarm / gürültü testi senaryosunu başlatan uç noktadır
async def start_noise_simulation(duration_s: float = 12.0, speed_factor: float = 2.0):  # Gürültü simülasyonu parametrelerini alır
    global _simulation_task  # Global görev referansına erişir
    if _simulation_task and not _simulation_task.done():  # Önceden çalışan simülasyon varsa kontrol eder
        _simulation_task.cancel()  # Aktif görevi iptal eder

    engine.reset()  # Karar motorunu sıfırlar
    n_samples = int(duration_s * SAMPLE_RATE_HZ)  # Gürültü testi için toplam örnek sayısını hesaplar

    async def run():  # Arka planda gürültü verisi üreten asenkron fonksiyondur.
        await manager.broadcast(SystemMessage(message="Başlatıldı: Gürültü Testi").model_dump())  # Ekranlara gürültü testinin başladığını bildirir
        import random as _random  # Rastgele sayı modülünü içeri aktarır
        for i in range(n_samples):  # Her bir zaman adımı için döngü çalıştırır
            elapsed = i / SAMPLE_RATE_HZ  # Geçen simülasyon süresini hesaplar
            for station in STATIONS:  # Tüm istasyonları tek tek dolaşır
                amp = _random.gauss(0, 0.4)  # Sensörlere sismik olmayan rastgele çevre gürültüsü üretir
                for out_msg in engine.process_sample(station.id, amp, elapsed, None):  # Gürültüyü karar motorunda işler
                    await manager.broadcast(out_msg)  # Varsa motor çıktılarını ekranlara yayınlar
            await asyncio.sleep((1.0 / SAMPLE_RATE_HZ) / speed_factor)  # Frekansa uygun süre kadar bekler

        await manager.broadcast(  # Gürültü testi bittiğinde yanlış alarm engellendi mesajı yayınlar
            AlertMessage(  # Seviye 2 (Reddedildi/Yanlış Alarm) mesaj nesnesi oluşturur
                level=AlertLevel.LEVEL_2_REJECTED,  # Seviye 2 olarak ayarlar
                message="Sinyal gürültü analizi tamamlandı – Yanlış alarm engellendi."  
            ).model_dump()  # Mesajı JSON sözlüğüne çevirip iletir
        )  

    _simulation_task = asyncio.create_task(run())  # Gürültü simülasyonunu arka plan görevi olarak başlatır
    return {"status": "started", "mode": "noise_only"}  # İstemciye gürültü testinin başladığını döner


@app.post("/stop")  # Çalışan simülasyonu manuel olarak durduran HTTP POST uç noktasıdır
async def stop_simulation():  # Simülasyonu sonlandırıp sistemi normale döndüren fonksiyondur
    global _simulation_task  # Global görev değişkenini çağırır
    if _simulation_task and not _simulation_task.done():  # Eğer çalışan bir simülasyon varsa
        _simulation_task.cancel()  # Görevi anında iptal edip durdurur
    engine.reset()  # Karar motorunu ve istasyon hafızalarını sıfırlar
    await manager.broadcast(  # Tüm bağlı ekranlara sistemin normale döndüğünü bildirir
        AlertMessage(  # Normal durum bildirim nesnesi oluşturur
            level=AlertLevel.LEVEL_0_NORMAL,  # Seviye 0 (Normal) olarak belirler
            message="Sistem normal – aktif sarsıntı algılanmadı."  
        ).model_dump()  
    ) 
    return {"status": "stopped"}  