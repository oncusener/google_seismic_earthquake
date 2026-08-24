"""
Sismolojide deprem dalgalarının geliş anını otomatik olarak tespit etmek için kullanılan 
STA/LTA (Kısa Süreli Ortalama / Uzun Süreli Ortalama) algoritması uygulanır
"""
from __future__ import annotations
from datetime import datetime, timezone
from models import TriggerMessage, Station  #Projedeki istasyon modeliyle tetiklenme mesaj veri modelini içeri aktarır

#Tek bir istasyon için STA/LTA enerji oranını hesaplayan analiz sınıfını tanımlar
class RecursiveSTALTA:
    def __init__(
        self,                          
        station_id: str,               #İstasyon kimliğini
        sample_rate_hz: float = 50.0,  #örnekleme frekansını (50 Hz),
        sta_len_s: float = 0.5,        #kısa pencere süresini (0.5 sn), 
        lta_len_s: float = 10.0,       #uzun pencere süresini (10.0 sn)
        threshold: float = 4.5,        #ve tetiklenme eşiğini (4.5) belirleyen yapıcı fonksiyon
    ):
        self.station_id = station_id
        self.sample_rate_hz = sample_rate_hz
        self.sta_len = max(2, int(sta_len_s * sample_rate_hz))  #Sensörden saniyede 50 veri geldiği için, anlık sarsıntıyı takip edecek 0.5 saniyelik kısa aralıkta hafızada toplam kaç adet veri noktası tutulacağını belirler
        self.lta_len = max(5, int(lta_len_s * sample_rate_hz))  #Ortamın genel gürültüsünü takip edecek 10 saniyelik uzun aralıkta hafızada toplam kaç adet veri noktası saklanacağını belirler
        self.threshold = threshold          #Tetiklenme için aşılması gereken min STA/LTA oran eşiğini saklar

        self.buffer: list[float] = []       #Gelen son sinyal genliklerini kayan pencere mantığıyla tutacak boş bir veri tamponu açar
        self._triggered = False             #İstasyonun o an tetiklenmiş olup olmadığını takip eder
        self._refractory_counter = 0        #Tetiklenme sonrası tekrar eden alarmları engellemek için geri sayım sayacını sıfır olarak başlatır 
        self._refractory_samples = int(4.0 * sample_rate_hz)  #Bir kez tetiklendikten sonra 4 sn boyunca yeniden tetiklenmeyi engelleyen bekleme penceresini tanımlar

    #Yeni bir simülasyonda analiz geçmişini temizleyen sıfırlama fonksiyonu
    def reset(self):    
        self.buffer.clear()             #Geçmiş sinyal örneklerinin tutulduğu tampon listeyi tamamen boşaltır
        self._triggered = False         #Tetiklenme durumunu başlangıç durumuna (tetiklenmedi) getirir
        self._refractory_counter = 0    #Bekleme sayacını sıfırlar

    #Sensörden gelen her yeni örnekte enerji oranını hesaplayan ve tetikleme mesajı üreten ana fonksiyon
    def update(
        self, 
        sample: float, 
        elapsed_s: float, 
        event_id: str | None = None
    ) -> TriggerMessage | None:
        
        self.buffer.append(sample)          #Gelen yeni sinyal örneğini tampon dizinin sonuna ekler
        if len(self.buffer) > self.lta_len: #Hafızadaki veri sayısı 500'ü aştığında en eski veriyi silerek listeyi her zaman son 10 saniyelik veriyle sınırlar
            self.buffer.pop(0)

        if self._refractory_counter > 0:  #Cihazın az önce bir deprem algılayıp bekleme sürecine girip girmediğini kontrol eder
            self._refractory_counter -= 1 #Cihaz bekleme sürecindeyse bu bekleme sayacını her adımda bir azaltır
            return None                   #Cihaz bekleme sürecinden henüz çıkmadığı için yeni bir uyarı üretmeden işlemi sonlandırır

        if len(self.buffer) < self.sta_len: #Hafızada henüz 0.5 saniyelik (25 adet) veri birikmediyse hesaplama yapmadan yeni verilerin gelmesini bekler
            return None

        sta = sum(x * x for x in self.buffer[-self.sta_len:]) / self.sta_len    #Son yarım saniyede gelen verilerin şiddet ortalamasını alarak anlık sarsıntı seviyesini hesaplar
        lta = sum(x * x for x in self.buffer) / len(self.buffer)                #Hafızadaki tüm verilerin ortalamasını alarak ortamın normal arka plan gürültü seviyesini hesaplar

        if lta <= 1e-5:     #Ortam gürültüsü sıfıra çok yakınsa bölme işleminde sıfıra bölünme hatası almamak için işlemi durdurur
            return None

        ratio = sta / lta   #Anlık sarsıntı şiddetini normal ortam gürültüsüne bölerek deprem oran katsayısını bulur

        if ratio >= self.threshold and not self._triggered:    #Hesaplanan oran 4.5 eşiğini aşmışsa ve cihaz henüz alarm vermemişse deprem algılama adımlarını başlatır
            self._triggered = True                             #Cihazın durumunu "tetiklendi" olarak günceller.
            self._refractory_counter = self._refractory_samples #Aynı sarsıntı için art arda gereksiz alarmlar üretilmesini engellemek amacıyla 4 sn lik bir susturma sayacı başlatır

            return TriggerMessage(                  #Tetiklenen cihazın kimliğini, zamanını ve hesaplanan oranını içeren bir bildirim paketi oluşturup gönderir
                station_id=self.station_id,
                phase="P",
                detected_at=datetime.now(timezone.utc).isoformat(),
                sta_lta_ratio=round(ratio, 2),
                event_id=event_id,
            )

        if ratio < self.threshold * 0.5:  #Sarsıntı şiddeti normale dönüp oran 2.25'in altına indi mi diye kontrol eder
            self._triggered = False       #Ortam tamamen sakinleştiğinde cihazı bir sonraki olası depremi algılayabilmesi için yeniden hazır hale getirir
        return None

#Ağdaki 15 cihazın deprem analiz süreçlerini tek bir merkezden yöneten sınıf
class STALTAManager:
    def __init__(           #Yöneticiyi ayağa kaldırırken sisteme bağlı cihazların listesini ve saniyedeki veri hızını belirler
        self, 
        stations: list[Station] | None = None, 
        station_ids: list[str] | None = None,
        sample_rate_hz: float = 50.0
    ):
        self.sample_rate_hz = sample_rate_hz        #Saniyede gelen 50 örnek frekans bilgisini sınıf hafızasına kaydeder
        ids = station_ids if station_ids is not None else [s.id for s in (stations or [])]  #Sisteme verilen cihaz listesinden sadece cihaz ID lerini ayıklar
        self.filters: dict[str, RecursiveSTALTA] = {                            #Her bir cihaz için arka planda bağımsız birer analiz motoru oluşturup sözlük yapısına kaydeder
            sid: RecursiveSTALTA(station_id=sid, sample_rate_hz=sample_rate_hz)
            for sid in ids
        }

    #Bağlı tüm cihazların hafızalarındaki sinyal geçmişini aynı anda sıfırlayan fonksiyon
    def reset_all(self):
        for f in self.filters.values():
            f.reset()

    #Tüm sistemi sıfırlama işlemini tek bir komutla çağırmaya yarar
    def reset(self):
        self.reset_all()

    #Sensörden yeni bir veri geldiğinde bunu doğru cihaza iletip deprem kontrolü yaptıran ana dağıtıcı fonksiyon
    def process(
        self, 
        station_id: str, 
        sample: float, 
        elapsed_s: float, 
        event_id: str | None = None
    ) -> TriggerMessage | None:
        
        filt = self.filters.get(station_id)         #Gelen verinin ait olduğu cihazın analiz motorunu listeden bulup getirir
        if not filt:                                #Eğer veri sisteme kayıtlı olmayan yabancı bir cihazdan geldiyse işlemi dikkate almaz
            return None
        return filt.update(sample, elapsed_s, event_id=event_id)    #Veriyi ilgili cihazın kendi analiz motoruna teslim eder ve sarsıntı varsa üretilen uyarıyı döndürür