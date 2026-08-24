"""
Sensörlerden alınan tepe yer değiştirme genliği (P_d) ve istasyonların merkez üssüne olan mesafelerini kullanarak 
depremin moment büyüklüğünü tahmin eder ve farklı istasyonlardan elde edilen büyüklük tahminlerini birleştirir
"""
from __future__ import annotations
import math
import logging      #Programdaki olayları, işlemleri ve hataları takip etmek için kullanılır

logger = logging.getLogger("eews.magnitude")    #magnitude modülü için "eews.magnitude" adlı bir log kaydı oluşturma nesnesi tanımlar

def estimate_magnitude_pd(              #Sensörün ölçtüğü tepe genliği, merkez üssüne olan yüzey mesafesini ve varsayılan 
    peak_displacement: float,           #10 km odak derinliğini alarak tek bir istasyon için deprem büyüklüğünü hesaplayan fonksiyon
    epicentral_distance_km: float,
    depth_km: float = 10.0,
) -> float:
  
    if peak_displacement <= 0.05:       #Ölçülen titreşim genliğinin gürültü seviyesinde (0.05 cm veya daha küçük) olup olmadığını kontrol eder
        return 2.5                      #Genlik çok düşükse hesaplamaya girmeden doğrudan 2.5 taban büyüklüğünü döndürür

    hypo_km = math.sqrt(epicentral_distance_km**2 + depth_km**2)    #Pisagor teoremiyle yüzey mesafesi ve derinliği birleştirerek depremin odak noktasına olan 3 boyutlu hiposantr mesafesini hesaplar
    estimated_scale = max(0.5, peak_displacement / 0.45)            #Sensör simülatöründeki genlik katsayısının tersini alarak kaynaktaki ölçek çarpanını belirler ve minimum 0.5 ile sınırlandırır
    raw_m = 3.5 + (math.log10(max(0.1, estimated_scale * (hypo_km + 15.0) / 110.0)) / 0.55) #Ham büyüklük değerini hesaplar

    return round(max(2.0, min(8.2, raw_m)), 1)

#Farklı istasyonlardan gelen büyüklük tahminlerinin listesini parametre olarak alıp genel bir ağ büyüklüğü üreten fonksiyonu tanımlar
def aggregate_magnitude(estimates: list[float]) -> float:
    if not estimates:   #Fonksiyona gelen büyüklük listesinin boş olup olmadığını kontrol eder
        return 5.0      #Hiçbir istasyondan tahmin gelmediyse varsayılan güvenli değer olarak 5.0 büyüklüğünü döndürür
    return round(sum(estimates) / len(estimates), 1)  #Tüm istasyonların büyüklük tahminlerinin aritmetik ortalamasını alır