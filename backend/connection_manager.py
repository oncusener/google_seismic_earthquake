"""
Sunucuya bağlı olan tüm istemcileri takip eder ve gönderilen mesajları bu istemcilerin tamamına iletir
"""
from __future__ import annotations
import asyncio                  #WebSocket bağlantıları gibi aynı anda gerçekleşen işlemleri asenkron olarak yönetir
import json                     #Verileri JSON formatına dönüştürür veya JSON verilerini okur
from fastapi import WebSocket   #FastAPI içinde WebSocket bağlantıları oluşturmak ve yönetmek için gereken WebSocket sınıfını içe aktarır

#WebSocket bağlantılarını yönetecek sınıf
class ConnectionManager:
    def __init__(self):
        self._connections: set[WebSocket] = set()   #Sunucuya bağlı olan tüm istemcileri benzersiz şekilde tutmak için boş bir küme oluşturur
        self._lock = asyncio.Lock()                 #Aynı anda birden fazla istemci bağlanıp ayrılırken listenin bozulmasını önleyen eşzamanlılık kilididir

    async def connect(self, ws: WebSocket):     #Yeni bir istemci bağlandığında çalışan fonksiyon
        await ws.accept()                       #Gelen WebSocket isteğini onaylar ve bağlantıyı açar
        async with self._lock:                  #Aynı anda başka bir işlem listeyi değiştirmesin diye güvenli kilit bloğunu açar
            self._connections.add(ws)           #Yeni bağlanan ekranı aktif istemciler listesine ekler

    async def disconnect(self, ws: WebSocket):  #Kullanıcı sayfayı kapattığında veya bağlantısı koptuğunda çalışan ayrılma fonksiyonu
        async with self._lock:                  #Bağlantı silme işlemi sırasında listeyi korumak için güvenlik kilidini devreye sokar
            self._connections.discard(ws)       #Ayrılan ekranı aktif bağlantı listesinden güvenli bir şekilde çıkartır

    async def broadcast(self, payload: dict):   #Gelen deprem verisini bağlı olan tüm ekranlara aynı anda canlı olarak yayınlayan fonksiyon
        if not self._connections:               #Eğer açık olan hiçbir ekran yoksa işlem yapmadan yayını sonlandırır
            return
        data = json.dumps(payload, ensure_ascii=False)  #Gönderilecek deprem verisini Türkçe karakterleri koruyarak standart JSON metnine dönüştürür
        dead: list[WebSocket] = []              #Mesaj gönderilirken bağlantısının koptuğu anlaşılan geçersiz ekranları toplamak için geçici bir liste oluşturur
        async with self._lock:                  #Yayın sırasında listenin yapısı bozulmasın diye o anki aktif ekranların güvenli bir anlık kopyasını alır
            connections = list(self._connections)
        for ws in connections:                  #Açık olan tüm ekranları tek tek dolaşacak bir döngü başlatır
            try:
                await ws.send_text(data)        #Hazırlanan JSON verisini ilgili ekrana canlı olarak iletir
            except Exception:
                dead.append(ws)                 #Mesaj iletilemeyen veya kapanmış olan ekranları temizlenmek üzere geçersizler listesine ekler
        if dead:
            async with self._lock:              #Bağlantısı kopmuş olan tüm ekranları ana listeden tamamen silerek bellek sızıntısını önler
                for ws in dead:
                    self._connections.discard(ws)

    #O anda sisteme bağlı olan toplam canlı ekran sayısını anlık olarak veren özelliktir
    @property
    def count(self) -> int:
        return len(self._connections)
