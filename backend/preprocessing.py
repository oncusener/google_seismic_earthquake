"""
ivmeölçer ve diğer sensörlerden alınan ham sismik verileri analiz öncesinde temizlemek için kullanılır; 
DC ofseti ve düşük frekanslı gürültüleri azaltmak amacıyla 1. derece yüksek geçiren (high-pass) filtre uygular
"""
from __future__ import annotations

#Tek bir sismik istasyona ait gelen ham sinyali temizleyen filtreleme sınıfını tanımlar
class SingleStationFilter:   
    def __init__(self, alpha: float = 0.95):    #Filtreyi başlatan ve filtreleme katsayısını varsayılan olarak bir değer belirleyen yapıcı fonksiyon
        self.alpha = alpha         #Yüksek geçiren filtrenin kesim frekansını ve sönümleme gücünü belirleyen katsayıyı sınıf içine kaydeder         
        self._prev_x = 0.0         #Filtreleme formülünde kullanılmak üzere bir önceki ham girdi sinyalini hafızada tutar
        self._prev_y = 0.0         #Filtreleme formülünde kullanılmak üzere bir önceki filtrelenmiş çıktı değerini hafızada tutar

    def reset(self):               #Yeni bir simülasyon veya test başladığında filtrenin önceki sinyal hafızasını sıfırlayan fonksiyondur
        self._prev_x = 0.0         #Önceki girdi ve çıktı hafıza değerlerini sıfıra eşitler
        self._prev_y = 0.0

    def filter(self, sample: float) -> float:       #Sensörden gelen tek bir ham genlik değerini işleyip filtrelenmiş halini döndüren fonksiyon
        # Basit 1. derece High-pass filtre: y[n] = alpha * (y[n-1] + x[n] - x[n-1])
        y = self.alpha * (self._prev_y + sample - self._prev_x)
        self._prev_x = sample
        self._prev_y = y
        return y            #Temizlenmiş gürültüden arındırılmış yeni sismik sinyal değeri

#Ağdaki tüm istasyonların bağımsız filtrelerini merkezi olarak yöneten kapsayıcı sınıf
class SignalFilter:
    def __init__(self, alpha: float = 0.95):        #Tüm ağ için genel filtre yöneticisini başlatan yapıcı fonksiyon
        self.alpha = alpha                          #Oluşturulacak tüm istasyon filtrelerinde kullanılacak ortak alfa katsayısını saklar
        self.filters: dict[str, SingleStationFilter] = {}   #Her istasyonun kendi bağımsız filtresini cihaz kimliğiyle (station_id) eşleştiren boş bir sözlük açar

    def reset(self):    #Sistemdeki tüm istasyon filtrelerinin sinyal hafızalarını topluca sıfırlayan fonksiyon
        for f in self.filters.values():
            f.reset()

    def process(self, station_id: str, raw_amplitude: float) -> float:      #Gelen sinyalin hangi cihaza ait olduğunu tespit edip o cihaza özel filtreyi çalıştıran ana işleme fonksiyonu
        if station_id not in self.filters:                                  #Bu istasyondan ilk defa veri geliyorsa kontrolü yapar
            self.filters[station_id] = SingleStationFilter(alpha=self.alpha)  #İstasyona özel yeni ve bağımsız bir filtre nesnesi oluşturup hafıza sözlüğüne ekler
        return self.filters[station_id].filter(raw_amplitude)               #İlgili istasyonun kendi filtresini çağırarak ham genliği filtreler ve temizlenmiş sismik veriyi döndürür