"""
Simülasyonda kullanılan Marmara Bölgesi genelindeki 15 adet sanal sismik istasyonun kimlik ve enlem-boylam koordinat 
tanımları
"""

from models import Station

STATIONS: list[Station] = [
    Station(id="phone_101", name="phone_101", lat=41.0630, lon=29.0610),
    Station(id="phone_102", name="phone_102", lat=41.0730, lon=28.2470),
    Station(id="phone_103", name="phone_103", lat=41.1750, lon=29.6130),
    Station(id="phone_104", name="phone_104", lat=40.9780, lon=27.5110),
    Station(id="phone_105", name="phone_105", lat=40.6550, lon=29.2770),
    Station(id="phone_106", name="phone_106", lat=40.1830, lon=29.0610),
    Station(id="phone_107", name="phone_107", lat=40.8020, lon=29.4310),
    Station(id="phone_108", name="phone_108", lat=39.6480, lon=27.8860),
    Station(id="phone_109", name="phone_109", lat=40.2280, lon=27.2420),
    Station(id="phone_110", name="phone_110", lat=40.7730, lon=30.4040),
    Station(id="phone_111", name="phone_111", lat=40.3750, lon=28.8820),
    Station(id="phone_112", name="phone_112", lat=40.6430, lon=29.1200),
    Station(id="phone_113", name="phone_113", lat=40.9900, lon=28.7100),
    Station(id="phone_114", name="phone_114", lat=40.7300, lon=29.8000),
    Station(id="phone_115", name="phone_115", lat=40.4200, lon=27.9500),
]
