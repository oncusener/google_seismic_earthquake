"""
Depremi algılayan istasyonların konumları ve sarsıntıyı algılama zamanları kullanılarak deprem merkez üssünün yaklaşık 
koordinatları tahmin edilir.
"""
from __future__ import annotations          #Kodun tip tanımlarının daha sorunsuz çalışmasını sağlar
from typing import Sequence                 #Sıralı veri yapılarını belirtmek için kullanılan bir tiptir
from models import TriggerMessage, Station  #Başka bir dosyada tanımlanan TriggerMessage ve Station veri modellerini bu dosyada kullanabilmek için içe aktarır


#Tetiklenen istasyon mesajları ile algılama zamanlarını ve istasyon listesini parametre olarak alıp tahmini 
#(enlem, boylam) çifti döndüren ana fonksiyonu tanımlar
# w_i = 1 / (t_varis + 0.1) -> İlk tetiklenen cihaz merkez üssüne en yakındır
def estimate_epicenter_weighted(
    triggers_with_time: list[tuple[TriggerMessage, float]],
    stations: dict[str, Station] | list[Station],
) -> tuple[float, float]:
    
    if not triggers_with_time:      #Eğer henüz tetiklenen hiçbir istasyon yoksa kontrolü yapar.
        return 40.8, 28.5           #Hiç veri yoksa varsayılan Marmara Denizi merkez koordinatını döndürür

    #İstasyonlar liste olarak geldiyse kimliklerine göre hızlı erişim sağlamak amacıyla dict yapısına dönüştürür
    st_map = {s.id: s for s in stations} if isinstance(stations, list) else stations

    weighted_lat_sum = 0.0      #Başlangıç enlem değişkeni
    weighted_lon_sum = 0.0      #Başlangıç boylam değişkeni
    total_weight = 0.0

    min_t = min(t for _, t in triggers_with_time)   #Tüm tetiklenmeler arasındaki en erken sarsıntı algılama anını bulur

    for trg, t_arr in triggers_with_time:       #Tetiklenen her bir cihaz mesajı ve o cihaza ait varış zamanı için döngü başlatır
        st = st_map.get(trg.station_id)         #Tetiklenen cihazın coğrafi konum bilgilerini dict ten çeker
        if st:                                  #İstasyon harita üzerinde kayıtlı ve mevcutsa hesaplama adımına geçer
            # Bağıl gecikmeye göre ağırlıklandırma
            rel_time = max(0.01, t_arr - min_t + 0.2)
            weight = 1.0 / rel_time
            weighted_lat_sum += st.lat * weight
            weighted_lon_sum += st.lon * weight
            total_weight += weight

    if total_weight == 0:     #Toplam ağırlık sıfır kalmışsa olası bir sıfıra bölme hatasını yakalar
        return 40.8, 28.5     #Ağırlık toplamı sıfırsa varsayılan koordinatı döndürür
    #Ağırlıklı koordinatları toplam ağırlığa bölerek depremin tahmini enlem ve boylamını virgülden sonra 4 basamak yuvarlayarak döndürür
    return round(weighted_lat_sum / total_weight, 4), round(weighted_lon_sum / total_weight, 4)

#Zaman damgası içermeyen eski çağrı biçimlerini desteklemek için takma ad fonksiyonunu tanımlar
def estimate_epicenter_centroid(triggers, stations):
    #Fonksiyona gelen verinin içinde hem istasyon mesajının hem de sarsıntının algılandığı zaman bilgisinin birlikte bulunup bulunmadığını kontrol eder
    if triggers and isinstance(triggers[0], tuple):
        return estimate_epicenter_weighted(triggers, stations)
    fake_timed = [(t, 1.0) for t in triggers]           #Zaman bilgisi yoksa her istasyona eşit 1.0 zaman damgası atayarak geçici bir dizi oluşturur.
    return estimate_epicenter_weighted(fake_timed, stations)