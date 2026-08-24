"""
10 cihaz onay kuralıyla depremi doğrulayan, merkez üssü ve 
büyüklük kestirimlerini yaparak erken uyarı üreten karar motoru
"""

from __future__ import annotations  # İleriye dönük tür ipuçlarının modern sözdizimiyle çalışmasını sağlar
import logging  # Çalışma anındaki durum ve hata mesajlarını kaydetmek için kullanılır
from dataclasses import dataclass, field  # Sınıf değişkenlerini ve başlangıç yapılarını sade tanımlamak için kullanılır

from models import (  # Veri modellerini ve sabitleri içeri aktarma bloğunu başlatır
    Station,  # İstasyon koordinat ve kimlik veri modeli
    TriggerMessage,  # İstasyon tetiklenme bildirim modeli
    EpicenterEstimateMessage,  # Kestirilen merkez üssü koordinat mesaj modeli
    AlertMessage,  # Kullanıcı arayüzüne giden genel alarm bildirim modeli
    AlertLevel,  # 0-4 arası alarm seviyelerini temsil eden sabitler
)  
from sta_lta import STALTAManager  # Ağ genelindeki sismik tetiklenme analiz yöneticisini içeri aktarır
from preprocessing import SignalFilter  # Ham sinyali gürültüden arındıran filtre modülünü içeri aktarır
from centroid import estimate_epicenter_weighted  # Ağırlıklı merkez üssü kestirim fonksiyonunu içeri aktarır
from magnitude import estimate_magnitude_pd  # Tepe genlik ve mesafeden büyüklük hesaplayan fonksiyonu içeri aktarır
from seismo_math import haversine_km, calculate_lead_time  # Yüzey mesafesi ve net erken uyarı süresini hesaplayan fonksiyonları içeri aktarır

logger = logging.getLogger("eews.engine")  # Karar motoruna özel loglama nesnesi oluşturur

N_MIN = 10  # Depremin kesinleşmesi için gereken min tetiklenen cihaz sayısı


@dataclass  
class EventEngine:  # Erken uyarı karar süreçlerini yürüten ana motor sınıfını tanımlar
    stations: list[Station]  # Ağda tanımlı olan sismik istasyonların listesi
    sample_rate_hz: float = 50.0  # Örnekleme frekansı

    stalta_mgr: STALTAManager = field(init=False)  # Sınıf başlatılırken sonradan kurulacak STA/LTA yöneticisi alanı
    sig_filter: SignalFilter = field(init=False)  # Sınıf başlatılırken sonradan kurulacak sinyal filtreleme alanı
    station_map: dict[str, Station] = field(init=False)  # İstasyonlara hızlı erişim sağlayan sözlük alanı

    _triggers: dict[str, tuple[TriggerMessage, float, list[float]]] = field(default_factory=dict, init=False)  # Tetiklenen cihazları, zamanlarını ve genlik listelerini tutan sözlük
    _confirmed: bool = field(default=False, init=False)  # Depremin resmi olarak doğrulanıp doğrulanmadığını tutar
    _epicenter: tuple[float, float] | None = field(default=None, init=False)  # Kestirilen merkez üssü enlem ve boylam bilgisi

    def __post_init__(self):  # Sınıf oluşturulduktan hemen sonra otomatik çalışan kurulum fonksiyon
        ids = [s.id for s in self.stations]  # İstasyon listesinden tüm cihaz kimliklerini ayıklanır
        self.stalta_mgr = STALTAManager(station_ids=ids, sample_rate_hz=self.sample_rate_hz)  # İstasyonlar için STA/LTA yöneticisini başlatır
        self.sig_filter = SignalFilter()  # Sinyal filtreleme nesnesi
        self.station_map = {s.id: s for s in self.stations}  # Cihaz kimlikleriyle istasyon nesnelerini eşleyen sözlük

    def reset(self):  # Yeni bir deprem veya senaryo için karar motorunun tüm hafızasını sıfırlayan fonksiyon
        self.stalta_mgr.reset_all()  # Tüm cihazların STA/LTA analiz geçmişini sıfırlar
        self.sig_filter.reset()  # Sinyal filtrelerinin önceki veri hafızasını temizler
        self._triggers.clear()  # Tetiklenen cihazlar listesini tamamen boşaltır
        self._confirmed = False  # Doğrulamayı başlangıç durumuna yani doğrulanmadıya getirir
        self._epicenter = None  # Kayıtlı merkez üssü koordinatını temizler

    @property  
    def snapshot(self) -> dict:  # Sistemin o anki durumunu özet sözlük olarak döndüren fonksiyon
        return { 
            "confirmed": self._confirmed,  # Deprem doğrulandı mı bilgisi
            "triggers_count": len(self._triggers),  # Tetiklenen toplam benzersiz cihaz sayısı
            "epicenter": self._epicenter,  # Kestirilen tahmini merkez üssü koordinatı
        } 

    def process_sample(  # Sensörden gelen her tekil veri noktasını işleyen ana karar fonksiyonu
        self,  
        station_id: str,  # Verinin geldiği istasyon kimliği
        raw_amplitude: float,  # Sensörün ölçtüğü ham titreşim genliği
        elapsed_s: float,  # Simülasyonun başından itibaren geçen süre 
        event_id: str | None = None,  # Varsa depremin olay ıd si
    ) -> list[dict]:  # Frontend ve WebSocket için üretilen mesaj listesini döndürür
        clean = self.sig_filter.process(station_id, raw_amplitude)  # Ham sinyali yüksek geçiren filtreden geçirerek DC kaymasını temizler

        # Tetiklenen istasyonun ilk 3 saniyelik genlikleri toplanır
        if station_id in self._triggers:  # Eğer bu cihaz daha önce tetiklendiyse kontrolü yapar
            trg, t_start, amp_window = self._triggers[station_id]  # Cihazın tetikleme mesajını, ilk tetiklenme anını ve genlik listesini çeker
            if elapsed_s - t_start <= 3.0:  # Tetiklenme anından itibaren henüz 3 saniye geçmediyse kontrol eder
                amp_window.append(abs(clean))  # Büyüklük kestiriminde kullanılmak üzere mutlak genlik değerini listeye ekler

        trigger = self.stalta_mgr.process(station_id, clean, elapsed_s, event_id)  # Temizlenmiş sinyali STA/LTA analizine sokarak tetiklenme kontrolü yapar
        messages: list[dict] = []  # Üretilecek tüm bildirim mesajlarını toplamak için boş liste açar

        if trigger and trigger.phase == "P":  # İstasyon yeni bir P dalgası algıladıysa devreye girer
            if station_id not in self._triggers:  # Bu cihaz ilk kez tetikleniyorsa
                self._triggers[station_id] = (trigger, elapsed_s, [abs(clean)])  # Cihazı, tetiklenme süresini ve ilk genlik değerini hafızaya kaydeder
                messages.append(trigger.model_dump())  # İstasyonun tetiklendiğini bildiren mesajı listeye ekler

            n_unique = len(self._triggers)  # O ana kadar tetiklenen toplam benzersiz cihaz sayısını hesaplar

            # 1-9 CİHAZ ARASI: LEVEL 1
            if not self._confirmed and n_unique < N_MIN:  # Cihaz sayısı 10'dan azsa ve deprem henüz onaylanmadıysa
                messages.append(  # Arayüze sarı renkli doğrulama aşaması mesajı ekler
                    AlertMessage(  # Seviye 1 (Doğrulanıyor) alarm nesnesi oluşturur
                        level=AlertLevel.LEVEL_1_VERIFYING,  # Seviye 1 olarak ayarlar
                        event_id=event_id,  
                        confirming_devices=n_unique,  # Onay veren anlık cihaz sayısı
                        message=f"Sarsıntı algılandı – Doğrulanıyor ({n_unique}/{N_MIN} Cihaz)",  
                    ).model_dump()  # Mesajı sözlük formatına çevirip ekler
                )  

            # 10 CİHAZ TAMAMLANDIĞINDA: DEPREM DOĞRULANDI (LEVEL 4 / LEVEL 3)
            elif not self._confirmed and n_unique >= N_MIN:  # Tetiklenen cihaz sayısı 10'a ulaştığında ve deprem henüz kesinleşmediyse
                self._confirmed = True  # Depremi resmi olarak onaylandı olarak işaretler

                cluster_trigger_pairs = [(data[0], data[1]) for data in self._triggers.values()]  # Merkez üssü hesabı için tetiklenen cihazları ve varış zamanlarını eşler
                lat, lon = estimate_epicenter_weighted(cluster_trigger_pairs, self.station_map)  # Zaman ağırlıklı ortalama formülüyle merkez üssü enlem ve boylamını kestirir
                self._epicenter = (lat, lon)  # Kestirilen koordinatları sınıf hafızasına kaydeder

                messages.append(  # Harita ekranına tahmini merkez üssü mesajını ekler
                    EpicenterEstimateMessage(  # Merkez üssü kestirim veri nesnesi oluşturur
                        event_id=event_id,  
                        lat=lat,  # Kestirilen enlem
                        lon=lon,  # Kestirilen boylam
                        contributing_stations=list(self._triggers.keys()),  # Hesaba katılan 10 cihazın kimlik listesi
                    ).model_dump()  # Mesajı sözlük formatına çevirip ekler
                )  

                # Ortalama ağ mesafesi üzerinden dinamik büyüklük kestirimi 
                first_sid = list(self._triggers.keys())[0]  # Sarsıntıyı en erken algılayan ilk istasyonun kimliğini alır
                first_st = self.station_map.get(first_sid, self.stations[0])  # İlk istasyonun coğrafi konum nesnesini bulur
                dist_km = haversine_km(lat, lon, first_st.lat, first_st.lon)  # Merkez üssü ile ilk istasyon arasındaki yüzey mesafesini hesaplar

                all_amps = [max(data[2] or [0.1]) for data in self._triggers.values()]  # Tetiklenen her cihazın ilk 3 saniyedeki max genliğini toplar
                peak_pd = max(all_amps)  # Ağ genelinde ölçülen en yüksek tepe yer değiştirme genliğini seçer
                calc_mag = estimate_magnitude_pd(peak_pd, dist_km)  # Tepe genlik ve mesafeyi kullanarak depremin büyüklüğünü dinamik olarak hesaplar

                # Şehir merkezine yıkıcı sarsıntı ulaşmadan önceki tahmini önlem alma süresi
                target_dist = haversine_km(lat, lon, 41.0082, 28.9784)  # Kestirilen merkez üssü ile İstanbul merkezi arasındaki mesafeyi hesaplar
                net_lead_time = calculate_lead_time(max(target_dist, 40.0), t_network_s=0.3, t_cluster_s=0.4)  # Gecikmeleri düşerek kalan net erken uyarı süresini hesaplar

                level = AlertLevel.LEVEL_3_INFO if calc_mag < 3.0 else AlertLevel.LEVEL_4_EARLY_WARNING  # Büyüklük 3.0 altındaysa Seviye 3 (Bilgi), üstündeyse Seviye 4 (Kırmızı Alarm) belirler

                messages.append(  # Arayüze depremin kesinleştiğini ve büyüklüğünü bildiren erken uyarı mesajını ekler.
                    AlertMessage(  
                        level=level,  
                        event_id=event_id,  
                        estimated_magnitude=calc_mag,  # Dinamik kestirilen deprem büyüklüğü
                        confirming_devices=n_unique,  
                        lead_time_seconds=net_lead_time,  # Kalan net uyarı süresi
                        message=f"DEPREM DOĞRULANDI (M{calc_mag})" if calc_mag >= 3.0 else f"DÜŞÜK BÜYÜKLÜKTE SARSINTI (M{calc_mag})", 
                    ).model_dump()  
                )  

        return messages  # Üretilen tüm durum ve uyarı mesajlarını çağırana döndürür