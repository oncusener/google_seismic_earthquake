"""
Sistemde kullanılan verilerin hangi yapıda olacağını, hangi veri türlerini içereceğini ve geçerli olup olmadığını kontrol eden veri modellerini tanımlar
"""
from __future__ import annotations
from enum import IntEnum                #koddaki karmaşık sayıları (0, 1, 2, 3, 4) doğrudan kullanmak yerine onlara anlaşılır isimler verebilmek için Pythonın hazır numaralandırma yapısı (IntEnum) kullanılır
from typing import Literal              #Belirli değişkenlerin yalnızca önceden tanımlanmış metin değerlerini almasını sağlar
from datetime import datetime, timezone #Olayların gerçekleşme zamanını UTC zaman diliminde kaydetmek için kullanılır
from pydantic import BaseModel, Field, model_validator  #Veri modellerini oluşturmak, varsayılan değerleri belirlemek ve gelen verilerin doğruluğunu kontrol etmek için Pydantic araçlarını içeri aktarır

#Sistemde kullanılacak alarm seviyelerini ve bu seviyelere karşılık gelen sayısal değerleri tanımlar
class AlertLevel(IntEnum):
    LEVEL_0_NORMAL = 0
    LEVEL_1_VERIFYING = 1
    LEVEL_2_REJECTED = 2
    LEVEL_3_INFO = 3
    LEVEL_4_EARLY_WARNING = 4

#Haritada bulunan bir sismik istasyonun kimlik, ad, enlem ve boylam bilgilerini tutan veri modelidir
class Station(BaseModel):
    id: str
    name: str
    lat: float
    lon: float

#Simülasyonda oluşturulan deprem senaryosunun büyüklük, merkez üssü, derinlik ve oluşma zamanı gibi temel özelliklerini tanımlar
class SimulatedEvent(BaseModel):
    event_id: str
    lat: float = 40.8
    lon: float = 28.5
    true_lat: float = 40.8
    true_lon: float = 28.5
    epicenter_lat: float = 40.8
    epicenter_lon: float = 28.5
    depth_km: float = 10.0
    true_magnitude: float = 6.0
    origin_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    scenario_type: str = "earthquake"

    #Gelen veriler SimulatedEvent modeline aktarılmadan önce özel bir doğrulama veya düzenleme işleminin yapılmasını sağlar
    @model_validator(mode="before")
    @classmethod
    def sync_coords(cls, data: dict):
        if isinstance(data, dict):
            # Enlem senkronizasyonu (lat, true_lat, epicenter_lat)
            val_lat = data.get("lat") or data.get("true_lat") or data.get("epicenter_lat") or 40.8
            data["lat"] = val_lat
            data["true_lat"] = val_lat
            data["epicenter_lat"] = val_lat

            # Boylam senkronizasyonu (lon, true_lon, epicenter_lon)
            val_lon = data.get("lon") or data.get("true_lon") or data.get("epicenter_lon") or 28.5
            data["lon"] = val_lon
            data["true_lon"] = val_lon
            data["epicenter_lon"] = val_lon
        return data

#Sensörden alınan tek bir sismik verinin bilgilerini taşır.
class SeismicSample(BaseModel):
    type: Literal["sample"] = "sample"
    station_id: str
    amplitude: float
    timestamp: str
    event_id: str | None = None

#Deprem dalgalarının harita üzerindeki hareketini göstermek için P ve S dalgalarının yarıçap ve çizim bilgilerini taşır
class WaveMessage(BaseModel):
    type: Literal["wave"] = "wave"
    event_id: str | None = None
    station_id: str | None = None
    phase: Literal["P", "S"] | None = None
    t: str | None = None
    amplitude: float | None = None
    epicenter_lat: float | None = None
    epicenter_lon: float | None = None
    radius_km: float | None = None

#Bir istasyonun sismik sinyalde belirlenen eşiği aşarak sarsıntı algıladığını bildiren tetiklenme mesajını temsil eder
class TriggerMessage(BaseModel):
    type: Literal["trigger"] = "trigger"
    station_id: str
    phase: Literal["P", "S"]
    detected_at: str
    sta_lta_ratio: float
    event_id: str | None = None

#Yeterli sayıda istasyondan doğrulama geldiğinde depremin sistem tarafından doğrulandığını bildiren mesajı temsil eder
class EventConfirmedMessage(BaseModel):
    type: Literal["event_confirmed"] = "event_confirmed"
    event_id: str | None = None
    n_stations: int
    confirmation_mode: str = "fast"
    time_window_s: float = 15.0

#Hesaplanan tahmini merkez üssünün enlem, boylam ve hesaplamaya dahil edilen istasyon bilgilerini taşır
class EpicenterEstimateMessage(BaseModel):
    type: Literal["epicenter_estimate"] = "epicenter_estimate"
    event_id: str | None = None
    lat: float
    lon: float
    contributing_stations: list[str] = Field(default_factory=list)

#Bir istasyondan alınan P_d genliği kullanılarak hesaplanan tahmini deprem büyüklüğünü taşır
class MagnitudeEstimateMessage(BaseModel):
    type: Literal["magnitude_estimate"] = "magnitude_estimate"
    event_id: str | None = None
    station_id: str
    estimated_magnitude: float

#Depremle ilgili hesaplamalar tamamlandığında oluşturulan kritik bilgileri taşır
class EarlyWarningMessage(BaseModel):
    type: Literal["early_warning"] = "early_warning"
    event_id: str | None = None
    magnitude: float
    epicenter_lat: float
    epicenter_lon: float
    lead_time_seconds: float

#Arayüzde gösterilecek alarm seviyesini, onaylayan istasyon sayısını ve durum bilgisini taşıyan genel uyarı mesajıdır
class AlertMessage(BaseModel):
    type: Literal["alert"] = "alert"
    level: int = AlertLevel.LEVEL_0_NORMAL
    event_id: str | None = None
    estimated_magnitude: float | None = None
    confirming_devices: int | None = None
    lead_time_seconds: float | None = None
    message: str = ""

#Sistemin bağlantı, çalışma durumu ve hata gibi genel bilgilendirme mesajlarını taşır.
class SystemMessage(BaseModel):
    type: Literal["system"] = "system"
    message: str