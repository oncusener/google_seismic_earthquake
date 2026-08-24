"""
Deprem dalgalarının hızları ve bu hızlar kullanılarak mesafe ile varış zamanı hesaplamaları yapılır
"""
import math

EARTH_RADIUS_KM = 6371.0   #Dünyanın küresel yarıçapı
VP_KM_S = 6.0   #P dalga hızı 
VS_KM_S = 3.5   #S dalga hızı 

#Dünya yüzeyindeki iki coğrafi koordinat arasındaki en kısa kuş uçuşu mesafeyi hesaplayan fonksiyon
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2) #Birinci ve ikinci noktaların enlem dereceleri trigonometrik hesaplama için radyana çevrilir
    dphi = math.radians(lat2 - lat1)                    #İki noktanın enlemleri arasındaki farkı radyan cinsinden hesaplar
    dlambda = math.radians(lon2 - lon1)                 #İki noktanın boylamları arasındaki farkı radyan cinsinden hesaplar

    #Dünyanın eğriliğini dikkate alan Haversine formülünün açısal ara adımını hesaplar
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c

#Depremin yüzeydeki merkez üssü mesafesi ve odak derinliğini kullanarak yeraltındaki asıl kırılma noktasına olan 3 boyutlu mesafeyi hesaplayan fonksiyon
def hypocentral_distance_km(epicentral_km: float, depth_km: float) -> float:
    return math.sqrt(epicentral_km ** 2 + depth_km ** 2)

#Verilen mesafeye göre P ve S dalgalarının istasyona ne kadar sürede varacağını hesaplayan fonksiyon
def travel_times_s(distance_km: float, vp: float = VP_KM_S, vs: float = VS_KM_S) -> tuple[float, float]:
    return distance_km / vp, distance_km / vs

#Kullanıcılara yıkıcı S dalgası ulaşmadan önce verilebilecek net erken uyarı süresini hesaplar
def calculate_lead_time(
    distance_km: float,
    t_network_s: float = 0.3,
    t_cluster_s: float = 0.4,
    vp: float = VP_KM_S,
    vs: float = VS_KM_S,
) -> float:
    
    t_gain = distance_km * (1.0 / vs - 1.0 / vp)    #Hızlı olan P dalgası ile yıkıcı S dalgası arasındaki varış zaman farkını hesaplar
    net_lead = t_gain - (t_network_s + t_cluster_s) #Kazanılan bu süreden sunucu ağ gecikmesi ve karar motorunun depremi doğrulama süresini düşerek gerçek uyarı süresini bulur
    return round(net_lead, 1)

#Bir istasyonun deprem merkezine olan tüm mesafelerini ve dalga varış sürelerini topluca hesaplayıp bir paket halinde sunan fonksiyon
def station_distance_and_times(
    station_lat: float, station_lon: float,
    epicenter_lat: float, epicenter_lon: float, depth_km: float,
) -> dict:
    
    epi_km = haversine_km(station_lat, station_lon, epicenter_lat, epicenter_lon)   #İstasyon ile merkez üssü arasındaki yüzey mesafesini hesaplar
    hypo_km = hypocentral_distance_km(epi_km, depth_km)                             #İstasyon ile depremin yeraltındaki odak noktası arasındaki 3 boyutlu mesafeyi hesaplar
    t_p, t_s = travel_times_s(hypo_km)                                              #P ve S dalgalarının bu istasyona kaçar saniye sonra ulaşacağını bulur

    #Hesaplanan yüzey mesafesini, derinlikli mesafeyi ve P/S dalga sürelerini 3 basamak hassasiyetle bir dict olarak döndürür.
    return {
        "epicentral_km": round(epi_km, 3),
        "hypocentral_km": round(hypo_km, 3),
        "t_p_s": round(t_p, 3),
        "t_s_s": round(t_s, 3),
    }