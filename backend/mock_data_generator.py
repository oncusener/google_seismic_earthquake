"""
Fiziksel deprem dalgası denklemlerini kullanarak 50 Hz frekansında yapay sismik sinyaller üreten ve ağ gecikmesi, paket kaybı, gürültü gibi 
farklı test senaryolarını simüle eden veri üreticisidir
"""
from __future__ import annotations 
import asyncio  # Asenkron zamanlama ve eşzamanlı görev yönetimi için kullanılır
import math  
import random  
import uuid  # Her deprem olayı için benzersiz ID üretir.
from datetime import datetime, timedelta, timezone  # Zaman damgası ve zaman farkı hesaplamalarını sağlar
from typing import Callable, Awaitable  # Tip belirteçleri için çağrılabilir asenkron fonksiyon tiplerini içeri aktarır
import numpy as np  # Normal dağılımlı arka plan gürültü sinyali üretmek için kullanılır.

from models import Station, SimulatedEvent, WaveMessage  # Veri modellerini projeden içeri aktarır
from seismo_math import station_distance_and_times  # Mesafe ve dalga varış sürelerini hesaplayan fonksiyonu içeri aktarır

SAMPLE_RATE_HZ = 50.0  # Saniyedeki örnekleme frekansını 50 Hz olarak tanımlar
DT = 1.0 / SAMPLE_RATE_HZ  # İki örnek arasındaki zaman aralığını (0.02 saniye) belirler
BACKGROUND_NOISE_STD = 0.3  # Sensörlerdeki arka plan ortam gürültüsünün standart sapmasını belirler
BBOX = {"lat_min": 40.4, "lat_max": 41.0, "lon_min": 28.0, "lon_max": 29.5}  # Marmara Bölgesi rastgele deprem koordinat sınırlarını belirler


def create_random_event(  # Rastgele veya verilen parametrelerle sentetik deprem olayı oluşturan fonksiyondur
    magnitude: float | None = None,  # Deprem büyüklüğü parametresi
    depth_km: float | None = None,  # Odak derinliği parametresi
    lat: float | None = None,  # Merkez üssü enlem parametresi
    lon: float | None = None,  # Merkez üssü boylam parametresi
) -> SimulatedEvent:  # Oluşturulan simüle edilmiş deprem nesnesini döndürür
    return SimulatedEvent(  # Deprem parametrelerini içeren veri nesnesini başlatır
        event_id=str(uuid.uuid4())[:8],  # Deprem için 8 karakterlik benzersiz rastgele kimlik atar
        origin_time=datetime.now(timezone.utc).isoformat(),  # Depremin başlangıç anını UTC zaman damgasıyla kaydeder.
        epicenter_lat=lat if lat is not None else round(random.uniform(BBOX["lat_min"], BBOX["lat_max"]), 4),  # Enlemi sınırlar içinde rastgele belirler
        epicenter_lon=lon if lon is not None else round(random.uniform(BBOX["lon_min"], BBOX["lon_max"]), 4),  # Boylamı sınırlar içinde rastgele belirler
        depth_km=depth_km if depth_km is not None else round(random.uniform(8, 15), 1),  # Derinliği 8-15 km arasında rastgele seçer
        true_magnitude=magnitude if magnitude is not None else round(random.uniform(5.5, 6.8), 1),  # Büyüklüğü 5.5-6.8 arasında rastgele üretir
    )  

# Anlık sismik sinyal genliğini hesaplayan  fonksiyon
def _amplitude_at(elapsed_s: float, t_p: float, t_s: float, magnitude: float, hypo_km: float) -> float:  
    noise = float(np.random.normal(0, BACKGROUND_NOISE_STD))  # Gauss dağılımına sahip rastgele arka plan gürültüsü üretir
    if elapsed_s < t_p:  # Henüz P dalgası istasyona ulaşmadıysa kontrolü yapar
        return noise  # Dalga gelmediği için sadece ortam gürültüsünü döndürür

    scale = max(2.5, (10.0 ** ((magnitude - 3.5) * 0.55)) * (110.0 / (hypo_km + 15.0)))  # Büyüklük ve mesafeye bağlı fiziksel dalga genlik ölçeğini hesaplar

    if elapsed_s < t_s:  # P dalgası gelmiş fakat yıkıcı S dalgası henüz ulaşmamışsa kontrolü yapar
        p_progress = elapsed_s - t_p  # P dalgasının varışından itibaren geçen süreyi bulur
        p_wave = 0.55 * scale * min(1.0, p_progress / 0.3) * math.sin(2 * math.pi * 8 * p_progress)  # Yüksek frekanslı sinüs dalgasını üretir.
        return p_wave + noise  # P dalgasıyla ortam gürültüsünü toplayıp döndürür.

    s_progress = elapsed_s - t_s  # Yıkıcı S dalgasının varışından itibaren geçen süreyi bulur
    s_wave = scale * min(1.0, s_progress / 0.6) * math.exp(-s_progress / 8.0) * math.sin(2 * math.pi * 2.0 * s_progress)  # Düşük frekanslı (2 Hz) ve sönümlenen güçlü S dalgası üretir
    return s_wave + noise  # S dalgası ile ortam gürültüsünü toplayıp toplam genliği döndürür

# Simülasyonu çalıştırıp istasyonlara 50 Hz canlı veri akışı sağlayan fonksiyon
async def stream_event(  
    event: SimulatedEvent,  # Simüle edilen deprem bilgisi
    stations: list[Station],  # Ağdaki istasyonların listesi
    on_sample: Callable[[WaveMessage, float], Awaitable[None]],  # Üretilen her örneği ileten geri çağırım fonksiyonu
    duration_s: float = 25.0,  # Simülasyonun toplam süresi 
    speed_factor: float = 2.5,  # Simülasyonun kaç kat hızlı oynatılacağını belirleyen katsayı
    network_delay_ms: float = 0.0,  # Senaryo 3 için ağ gecikmesi süresi 
    packet_loss_rate: float = 0.0,  # Senaryo 5 için paket kaybı oranı (%0 - %100)
) -> None: 
    dist_cache = {  # Her istasyonun deprem merkezine olan mesafe ve dalga varış sürelerini önceden hesaplayıp önbelleğe alır
        s.id: station_distance_and_times(  # İstasyon koordinatlarına göre hesaplama yapar
            s.lat, s.lon, event.epicenter_lat, event.epicenter_lon, event.depth_km  # Fonksiyona koordinat ve derinlik parametrelerini iletir, hesaplama sonucunu sözlüğe yazar.
        )  
        for s in stations  # Listedeki her istasyon için bu işlemi tekrarlar
    }  
    origin_dt = datetime.fromisoformat(event.origin_time)  # Deprem başlangıç zamanını tarih saat nesnesine dönüştürür
    n_samples = int(duration_s * SAMPLE_RATE_HZ)  # Toplamda üretilecek örnek sayısını (25 x 50 = 1250 adım) hesaplar

    for i in range(n_samples):  # Her bir zaman adımı için döngü başlatır
        elapsed = i * DT  # Depremin başından itibaren geçen toplam simülasyon süresini hesaplar
        ts = origin_dt + timedelta(seconds=elapsed)  # O anki örneğin takvim zaman damgasını üretir

        for station in stations:  # Ağdaki her bir istasyon için sırayla veri üretir
            # Senaryo 5: Paket kaybı simülasyonu
            if packet_loss_rate > 0 and random.random() < packet_loss_rate:  # Belirlenen olasılığa göre paketin kaybolup kaybolmayacağını kontrol eder
                continue  # Paket kaybolduysa bu istasyona veri üretmeyip bir sonrakine geçer.

            d = dist_cache[station.id]  # İstasyonun önbelleğe alınmış mesafe ve süre bilgilerini çeker
            amp = _amplitude_at(elapsed, d["t_p_s"], d["t_s_s"], event.true_magnitude, d["hypocentral_km"])  # İstasyonun o andaki anlık sarsıntı genliğini hesaplar
            msg = WaveMessage(  # Frontend ve karar motoruna iletilecek sismik dalga mesaj paketini oluşturur
                station_id=station.id,  # Verinin ait olduğu istasyon kimliği
                t=ts.isoformat(),  # Örnekleme zaman damgası
                amplitude=round(float(amp), 4),  # 4 basamağa yuvarlanmış genlik değeri
                event_id=event.event_id,  # İlgili depremin kimlik kodu
            )  

            if network_delay_ms > 0:  # Senaryo 3 için ağ gecikmesi aktif mi kontrolü yapar
                jitter = random.uniform(0.15, network_delay_ms / 1000.0)  # Gerçekçi ağ gecikmesi için rastgele sapma süresi hesaplanır
                asyncio.create_task(_delayed_emit(on_sample, msg, elapsed, jitter))  # Mesajı gecikmeli iletmek için arka planda asenkron görev başlatır
            else:  
                await on_sample(msg, elapsed)  # Örneği doğrudan karar motoruna ve WebSocket istemcilerine iletir

        await asyncio.sleep(DT / speed_factor)  # 50 Hz akış hızını korumak için simülasyon hız çarpanına göre asenkron olarak bekler


async def _delayed_emit(on_sample, msg, elapsed, delay_s):  # Ağ gecikmeli paketleri belirlenen süre kadar bekletip ileten yardımcı fonksiyon
    await asyncio.sleep(delay_s)  # Belirlenen ağ gecikmesi süresi kadar bekler
    await on_sample(msg, elapsed)  # Süre dolduğunda mesajı sisteme iletir