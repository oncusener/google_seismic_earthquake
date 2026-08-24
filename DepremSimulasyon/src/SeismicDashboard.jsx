import React, { useEffect, useRef, useState, useCallback } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";


// İSTASYON VERİLERİ (MARMARA BÖLGESİ)
// Marmara Bölgesi çevresine dağıtılmış 15 istasyonun koordinat ve tanımlamaları
const STATIONS = [
  { id: "phone_101", name: "Istanbul-Kandilli", lat: 41.0630, lon: 29.0610 },
  { id: "phone_102", name: "Istanbul-Silivri", lat: 41.0730, lon: 28.2470 },
  { id: "phone_103", name: "Istanbul-Sile", lat: 41.1750, lon: 29.6130 },
  { id: "phone_104", name: "Tekirdag-Merkez", lat: 40.9780, lon: 27.5110 },
  { id: "phone_105", name: "Yalova-Merkez", lat: 40.6550, lon: 29.2770 },
  { id: "phone_106", name: "Bursa-Merkez", lat: 40.1830, lon: 29.0610 },
  { id: "phone_107", name: "Kocaeli-Gebze", lat: 40.8020, lon: 29.4310 },
  { id: "phone_108", name: "Balikesir-Merkez", lat: 39.6480, lon: 27.8860 },
  { id: "phone_109", name: "Canakkale-Biga", lat: 40.2280, lon: 27.2420 },
  { id: "phone_110", name: "Sakarya-Adapazari", lat: 40.7730, lon: 30.4040 },
  { id: "phone_111", name: "Bursa-Mudanya", lat: 40.3750, lon: 28.8820 },
  { id: "phone_112", name: "Yalova-Cinarcik", lat: 40.6430, lon: 29.1200 },
  { id: "phone_113", name: "Tekirdag-Corlu", lat: 41.1590, lon: 27.7980 },
  { id: "phone_114", name: "Kocaeli-Izmit", lat: 40.7650, lon: 29.9400 },
  { id: "phone_115", name: "Canakkale-Gelibolu", lat: 40.4100, lon: 26.6700 },
];

export default function SeismicDashboard() {
  // REFERANSLAR 
  const wsRef = useRef(null);                        // Sunucuyla sürekli açık kalan WebSocket bağlantısını tutar
  const mapContainerRef = useRef(null);              // Haritanın ekranda tam olarak hangi <div> etiketinin içine yerleşeceğini Leaflet kütüphanesine işaret eder
  const mapInstanceRef = useRef(null);               // Haritayı bir kez başlatıp saklar,böylece her renderda harita sıfırdan açılıp çökmez
  const markersRef = useRef({});                     // Harita üzerindeki 15 istasyon noktasını hafızada tutar.
  const waveLayersRef = useRef([]);                  // Merkez üssü ve P/S dalga animasyonu katmanları
  const triggeredStationsRef = useRef(new Set());    // Depremi algılayan istasyonların isimlerini benzersiz olarak toplar

  const eventStartTimeRef = useRef(null);            // İlk algılama zaman damgası 
  const timerIntervalRef = useRef(null);             // Canlı süreyi güncelleyen sayacı tutar

  //REACT STATE TANIMLARI
  const [connStatus, setConnStatus] = useState("disconnected"); // Backend ile WebSocket bağlantısının o anki halini tutar
  const [durationSec, setDurationSec] = useState(0);            // Ekranda gösterilen geçen süre 
  const [logs, setLogs] = useState([                            // Sağ panelde akan olay geçmişini dizi halinde tutar
    { text: "Sistem başlatıldı", kind: "system" },              // Sistem açıldığındaki başlangıç değerleri
    { text: "15 cihaz bağlandı", kind: "system" }
  ]);

  // Deprem alarmı ve büyüklük durumunu tutan ana nesne
  const [alertState, setAlertState] = useState({
    level: 0,              // 0: Normal, 1: Doğrulanıyor, 2: Reddedildi, 3: Düşük Şiddet, 4: Erken Uyarı
    magnitude: null,       // Kestirilen büyüklük (M)
    confirmingDevices: 0,  // Doğrulayan toplam cihaz sayısı
  });

  const [deviceStatuses, setDeviceStatuses] = useState({});     // Cihazların anlık durumları (tetiklendi / bekleniyor)
  const [epicenter, setEpicenter] = useState(null);             // Kestirilen merkez üssü koordinatları { lat, lon }

  // olay geçmişine yeni bir bildirim ekler ve listenin aşırı uzayıp tarayıcıyı kasmasını önlemek için en son 60 kaydı hafızada tutar
  const addLog = useCallback((text, kind = "system") => {       //useCallback ile hafızaya sabitlenmiş addLog(text, kind) fonksiyonu sayesinde yeni bildirimleri performansı düşürmeden alır
    setLogs((prev) => [{ text, kind }, ...prev].slice(0, 60));  //setLogs((prev) => ...) ile mevcut listeyi güncelleyip yeni mesajı [{ text, kind }, ...prev] ile en başa ekler ve slice(0, 60) ile listenin sadece en güncel 60 kaydını tutar
  }, []);

  // Yeni senaryo başladığında veya durdurulduğunda yerel arayüzü sıfırlayan fonksiyon
  const resetLocalState = useCallback(() => {
    if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    eventStartTimeRef.current = null;
    setDurationSec(0);
    triggeredStationsRef.current.clear();
    setDeviceStatuses({});
    setEpicenter(null);
    setAlertState({ level: 0, magnitude: null, confirmingDevices: 0 });
  }, []);

  //HARİTA BAŞLATMA VE MARKER KURULUMU
  useEffect(() => {  //Reactte bir işlem gerçekleştiğinde kod çalıştırmak için kullanılır
    if (!mapContainerRef.current) return; //mapContainerRef: haritanın HTML'de yerleşeceği alanı gösterir
                                          //Haritanın yerleşeceği HTML kutusu (<div>) henüz ekranda oluşmadıysa hata vermemek için işlemi durdurur ve bekler

    // Harita daha önce başlatılmadıysa Marmara merkezli olarak oluşturulur
    if (!mapInstanceRef.current) {
      const map = L.map(mapContainerRef.current).setView([40.7, 28.9], 8);  //HTML kutusunun içine Leaflet haritasını yerleştirir; merkezi Marmara Denizi koordinatlarına (40.7 enlem, 28.9 boylam) ayarlar 
                                                                            //ve yakınlaştırma seviyesini 8 yapar
      mapInstanceRef.current = map; //Oluşturulan bu harita örneğini daha sonra dalga çizmek veya istasyon renklerini değiştirmek için mapInstanceRef referansında saklar

      // CartoDB Voyager altlık harita katmanı
      L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {  //Haritanın arkasındaki sokakları, denizleri ve karaları gösteren CartoDB Voyager görsel harita resimlerini indirip haritaya giydirir
        attribution: '&copy; CARTO'       //Haritanın altında kaynak gösterilmesini sağlar
      }).addTo(map);

      // Tanımladığımız 15 istasyonluk dizideki her bir istasyon için sırayla işlem başlatır
      STATIONS.forEach((st) => {   
        const marker = L.circleMarker([st.lat, st.lon], {    //İstasyonun enlem/boylamına harita üzerinde dairesel bir işaretçi (nokta) ekler
          radius: 6,
          color: "#2B303A",
          fillColor: "#4A5568",
          fillOpacity: 0.9,
          weight: 1.5,
        }).addTo(map);

        marker.bindPopup(`<b>${st.name}</b><br/>Durum: Bekleniyor`); //Haritadaki o noktaya tıklandığında istasyonun adını ve "Durum: Bekleniyor" yazısını gösteren açılır pencere oluşturur
        markersRef.current[st.id] = marker; //Oluşturulan bu noktayı istasyon ID'siyle (phone_101 gibi) hafızadaki sözlüğe kaydeder böylece deprem anında doğrudan rengini kırmızıya çevirir
      });
    }

    return () => {  //Kullanıcı sayfadan ayrıldığında veya bileşen kapandığında çalışır
      if (mapInstanceRef.current) {     //Haritayı ve tüm noktaları tarayıcı belleğinden tamamen siler
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
        markersRef.current = {};
      }
    };
  }, []);

  //İSTASYON RENK GÜNCELLEMELERİ
  // Cihaz tetiklendiğinde harita üzerindeki rengi gri -> kırmızıya döner
  useEffect(() => {   //[deviceStatuses] sayesinde, cihazların durumunda herhangi bir değişiklik olduğunda (örneğin bir telefon sarsıntı algıladığında) bu bloğu otomatik olarak çalıştırır
    STATIONS.forEach((st) => {
      const marker = markersRef.current[st.id];  //O an incelenen istasyonun haritadaki görsel işaretçisini hafızadan bulup marker değişkenine atar
      if (marker) {
        const isTriggered = deviceStatuses[st.id]?.status === "tetiklendi";  //Bu istasyonun durumu backend'den gelen veriye göre "tetiklendi" mi yoksa hala "bekleniyor" mu diye bakar, sonucu true veya false olarak saklar
        marker.setStyle({                                         //Harita üzerindeki noktanın stilini anında değiştirir
          color: isTriggered ? "#D9534F" : "#2B303A",
          fillColor: isTriggered ? "#FF4D4D" : "#4A5568",
          radius: isTriggered ? 9 : 6,
          weight: isTriggered ? 2.5 : 1.5
        });
      }
    });
  }, [deviceStatuses]);

  // DALGA ANİMASYONU 
  // Merkez üssü hesaplandığı anda dışa doğru yayılan dairesel dalga simülasyonu
  useEffect(() => {  //[epicenter] sayesinde, backend merkez üssü koordinatlarını hesaplayıp gönderdiği anda bu bloğu otomatik olarak çalıştırır.
    const map = mapInstanceRef.current; //Hafızada tutulan aktif Leaflet harita nesnesini çağırır
    if (!map) return;

    // Önceki dalga katmanlarını temizle
    waveLayersRef.current.forEach((layer) => map.removeLayer(layer)); 
    waveLayersRef.current = [];

    if (!epicenter) return;   //Yeni bir merkez üssü bilgisi yoksa (örneğin sistem sıfırlandıysa) animasyon başlatmadan çıkar

    const center = [epicenter.lat, epicenter.lon]; //Kestirilen deprem merkezinin enlem ve boylamını dizi olarak ayarlar

    // Kırmızı merkez üssü nokta işareti
    const centerMarker = L.circleMarker(center, {
      radius: 9,
      color: "#FFFFFF",
      fillColor: "#D9534F",
      fillOpacity: 1,
      weight: 2.5,
    }).addTo(map);

    // P Dalgası (Hızlı yayılan mavi çember)
    const pCircle = L.circle(center, { radius: 100, color: "#5EC8D8", weight: 2, fillOpacity: 0.05 }).addTo(map);
    // S Dalgası (Yavaş yayılan yıkıcı kırmızı çember)
    const sCircle = L.circle(center, { radius: 100, color: "#D9534F", weight: 3, fillOpacity: 0.12 }).addTo(map);

    waveLayersRef.current = [centerMarker, pCircle, sCircle]; //Oluşturulan bu 3 şekli daha sonra kolayca silebilmek için referans listesine kaydeder

    const startTime = performance.now();  //Dalganın yayılma süresini hesaplamak için anlık milisaniye zaman damgasını alır
    let frameId;

    // 60 FPS dalga yayılma animasyon döngüsü
    const animate = () => {   //Her ekran yenilenmesinde dalga çaplarını büyütecek fonksiyonu başlatır
      const elapsed = (performance.now() - startTime) / 1000;   //Animasyonun başladığı andan itibaren geçen süreyi saniye cinsinden hesaplar
      const pMeter = elapsed * 6500 * 3; // 6.5 km/s P dalgası hızı
      const sMeter = elapsed * 3600 * 3; // 3.6 km/s S dalgası hızı

      pCircle.setRadius(pMeter);    //P dalgası çemberinin haritadaki yarıçapını yeni hesaplanan metre değerine göre genişletir
      sCircle.setRadius(sMeter);    //S dalgası çemberinin haritadaki yarıçapını yeni hesaplanan metre değerine göre genişletir

      if (sMeter < 500000) {    //Dalga yarıçapı 500 km ye ulaşana kadar bir sonraki ekran karesinde animate fonksiyonunu tekrar çağırır
        frameId = requestAnimationFrame(animate);
      }
    };

    frameId = requestAnimationFrame(animate); //İlk animasyon karesini tetikler
    return () => cancelAnimationFrame(frameId);
  }, [epicenter]);

  // WEBSOCKET İLETİŞİM MOTORU
  useEffect(() => {               
    let ws;                     //WebSocket bağlantısını tutar
    let reconnectTimer = null; //Bağlantı kesildiğinde devreye girecek gecikme sayacını tutar
    let cancelled = false;     //Kullanıcı sayfadan çıkarsa arka planda gereksiz yere tekrar bağlanmayı önleyen kontrol kilididir

    const scheduleReconnect = () => {       //Bağlantı koparsa 3 saniye sonra initSocket fonksiyonunu 
      if (cancelled) return;                //çağırarak sunucuya tekrar bağlanmayı dener
      reconnectTimer = setTimeout(initSocket, 3000);
    };

    const initSocket = () => {              //Canlı veri akışını kuran ana fonksiyonu tanımlar
      if (cancelled) return;                //Bileşen kapandıysa yeni soket oluşturmayı engeller
      ws = new WebSocket("ws://127.0.0.1:8000/ws"); //React, FastAPI sunucusuyla canlı veri alışverişi yapabileceği bir bağlantı kurar
      wsRef.current = ws;                   //Oluşturulan WebSocket bağlantısını daha sonra kullanabilmek için wsRef içinde saklar
      setConnStatus("connecting");          //Üst durum ışığını "Bağlantı Bekleniyor" durumuna getirir

      ws.onopen = () => {                   //Sunucuyla bağlantı kurulduğunda durumu yeşile (connected) çevirir 
        setConnStatus("connected");         //ve olay geçmişine yazar
        addLog("Sunucuya bağlandı", "system");
      };

      ws.onclose = () => {                  //Sunucu kapanırsa durumu kırmızıya (disconnected) çeker ve 
        setConnStatus("disconnected");      //3 saniyelik yeniden bağlanma sayacını çalıştırır
        scheduleReconnect();
      };

      ws.onerror = () => {                  //Ağ hatası oluştuğunda durumu bağlantı kesildi olarak günceller
        setConnStatus("disconnected");
      };

      // Backend'den gelen olay paketlerinin işlenmesi
      ws.onmessage = (evt) => {   //Sunucudan yeni bir bilgi veya deprem verisi geldiği anda otomatik olarak devreye girip o veriyi yakalayan fonksiyondur
        let msg;                                               //Gelen ham metin paketini JavaScript nesnesine dönüştürür,    
        try { msg = JSON.parse(evt.data); } catch { return; }  //format bozuksa çökmeyi önleyip işlemi sonlandırır 

        //İstasyon Tetiklenme Mesajı
        if (msg.type === "trigger") {          //Bir istasyonun sarsıntı algıladığına dair sinyal geldiğinde çalışır
          if (!eventStartTimeRef.current) {   //Eğer bu olaydaki ilk sarsıntıysa kronometreyi devreye sokar
            eventStartTimeRef.current = performance.now();    //Depremin ilk algılandığı anı yüksek hassasiyetli milisaniye olarak kaydeder
            if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);    //Önceden kalma bir sayaç varsa sıfırlar
            timerIntervalRef.current = setInterval(() => {                          //Her 100 milisaniyede bir geçen süreyi hesaplayıp
              const diff = (performance.now() - eventStartTimeRef.current) / 1000; //ekrandaki saniyeyi canlı günceller
              setDurationSec(diff.toFixed(1));
            }, 100);
          }

          const sid = msg.station_id;                     //Sarsıntıyı algılayan cihazın ID'sini alır
          if (!triggeredStationsRef.current.has(sid)) {   //Aynı cihaz daha önce tetiklenmemişse cihazı “tetiklenen cihazlar” listesine ekler ve ekranda bu cihazın tetiklendiğini gösteren bir log mesajı çıkarır
            triggeredStationsRef.current.add(sid);
            addLog(`${sid} tetiklendi`, "trigger");
          }

          setDeviceStatuses((prev) => ({                       //Cİhazlar listesinde ve haritada bu cihazı "tetiklendi" durumuna çevirir 
            ...prev,
            [sid]: { status: "tetiklendi", phase: msg.phase }
          }));
        } 
        
        else if (msg.type === "alert") {  //Backendin deprem doğrulama seviyesini bildirdiği mesaj geldiğinde çalışır
          setAlertState({                                     //Alarm seviyesini (0, 1, 2, 3, 4), tahmin edilen büyüklüğü ve onaylayan cihaz sayısını arayüze aktarır
            level: msg.level,                               
            magnitude: msg.estimated_magnitude,
            confirmingDevices: msg.confirming_devices || 0,
          });

          // Sistem yeterli sayıda istasyonla depremi doğruladıysa çalışır
          if (msg.level === 4 || msg.level === 3) {
            if (timerIntervalRef.current) {
              clearInterval(timerIntervalRef.current);    //Depremin doğrulanması için geçen süreyi sabitlemek üzere canlı sayacı durdurur
              timerIntervalRef.current = null;
            }
            addLog(`🚨 DEPREM DOĞRULANDI (M${msg.estimated_magnitude || ""})`, "alert");    //Log paneline büyük deprem alarmı mesajı basar
          } 
          //Sarsıntı gürültüden kaynaklıysa ve sistem tarafından reddedildiyse çalışır
          else if (msg.level === 2) {
            if (timerIntervalRef.current) {
              clearInterval(timerIntervalRef.current);
              timerIntervalRef.current = null;
            }
            addLog("⚠️ Yanlış Alarm Engellendi", "rejected");
          } 
          //Seviye sıfıra döndüyse tüm arayüzü başlangıç haline getirir
          else if (msg.level === 0) {
            resetLocalState();
          }
        } 
        // Ağırlıklı merkez hesabı ile bulunan enlem ve boylamı kaydederek haritada dalga animasyonunu tetikler
        else if (msg.type === "epicenter_estimate") {
          setEpicenter({ lat: msg.lat, lon: msg.lon });
        } 
        // Sunucudan gelen genel durum mesajlarını yakalar
        else if (msg.type === "system") {
          addLog(msg.message, "system");
          if (msg.message?.includes("Başlatıldı")) {      //Sunucudan "Simülasyon Başlatıldı" sinyali geldiğinde eski verileri sıfırlar ve kronometreyi başlatır
            resetLocalState();
            eventStartTimeRef.current = performance.now();
            timerIntervalRef.current = setInterval(() => {
              const diff = (performance.now() - eventStartTimeRef.current) / 1000;
              setDurationSec(diff.toFixed(1));
            }, 100);
          }
        }
      };
    };
    initSocket(); 

    //Sayfa kapatıldığında bağlantıyı keser, zamanlayıcıları ve sayaçları bellekten temizler.
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) ws.close();
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, [addLog, resetLocalState]);  //useEffect in bu iki fonksiyona bağlı olduğunu ve bu fonksiyonlar değiştiğinde effectin yeniden çalışması gerektiğini belirtir

  //REST API SENARYO TETİKLEYİCİLERİ
  const runScenario = (url) => {      //resetLocalState() ile mevcut verileri temizler ve ardından belirtilen adrese 
    resetLocalState();                //HTTP POST isteği göndererek sunucuda simülasyonu başlatır
    fetch(url, { method: "POST" });
  };

  // Senaryo 1: Büyük Deprem (Sistem elde ettiği verilere göre uygun bir büyüklük değeri hesaplar)
  const startScenario1 = () => runScenario("http://127.0.0.1:8000/simulate?magnitude=6.4&speed_factor=2.5&duration_s=25");
  // Senaryo 2: Düşük Şiddet (Alarm eşiğini aşmayan mikro deprem testi)
  const startScenario2 = () => runScenario("http://127.0.0.1:8000/simulate?magnitude=2.4&speed_factor=2.5&duration_s=20");
  // Senaryo 3: Ağ Gecikmesi (Verilerin sunucudan cihaza aynı sürede ulaşmaması ve bazı paketlerin normalden daha geç ulaşması durumu)
  const startScenario3 = () => runScenario("http://127.0.0.1:8000/simulate?network_delay_ms=350&speed_factor=2");
  // Senaryo 4: Gürültü Testi (Sensör titreşimlerinin yanlış alarm üretmediğini test eder)
  const startScenario4 = () => runScenario("http://127.0.0.1:8000/simulate_noise?duration_s=12");
  // Senaryo 5: Paket Kaybı (Gönderilen verilerin bir kısmının alıcıya hiç ulaşmaması durumunda sistemin çalışmaya devam edip edemediğinin test edilmesidir)
  const startScenario5 = () => runScenario("http://127.0.0.1:8000/simulate?packet_loss_rate=0.25&speed_factor=2");
  // Simülasyonu anında durdurma
  const handleStop = () => fetch("http://127.0.0.1:8000/stop", { method: "POST" });

  // Kolay mantıksal bayraklar 
  const isLevel4 = alertState.level === 4;  //Kırmızı Alarm - Büyük Deprem Kesinleşti
  const isLevel3 = alertState.level === 3;  //Turuncu Alarm - Deprem Doğrulandı
  const isLevel2 = alertState.level === 2;  //Sarı Alarm - Yanlış Alarm / Gürültü Reddedildi
  const isLevel1 = alertState.level === 1;   //Mavi Alarm - İlk Sarsıntı / Şüpheli Durum

  const triggeredCount = Object.values(deviceStatuses).filter((d) => d.status === "tetiklendi").length;  //Cihaz listesini tarayarak durumu "tetiklendi" olan istasyonları filtreler ve ekranda göstermek üzere toplam adedini hesaplar

  //ARAYÜZ 
  return (
    //Tüm arayüzün içine yerleştiği ana çerçeve
    <div style={{
      width: "100vw",
      height: "100vh",
      background: "#E2E5E8",
      fontFamily: "'Segoe UI', Roboto, sans-serif",
      color: "#222",
      display: "flex",
      flexDirection: "column",
      boxSizing: "border-box",
      padding: "12px 18px",
      overflow: "hidden" // Sayfa genelinde kaydırma çubuğunu önler
    }}>
      {/*ÜST BAŞLIK*/}
      <div style={{ fontSize: "16px", fontWeight: "800", marginBottom: "8px", letterSpacing: "0.5px", flexShrink: 0 }}>
        DEPREM ERKEN UYARI SİSTEMİ
      </div>

      {/*DURUM VE BİLDİRİM BANNERI*/}
      <div style={{
        background: isLevel4 ? "#F8D7DA" : isLevel1 ? "#FEF3C7" : isLevel3 ? "#DBEAFE" : isLevel2 ? "#FEE2E2" : "#FFFFFF",
        border: `1px solid ${isLevel4 ? "#F5C6CB" : isLevel1 ? "#FDE68A" : isLevel3 ? "#BFDBFE" : isLevel2 ? "#FECACA" : "#D0D4D9"}`,
        borderRadius: "4px",
        padding: "8px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",    //Sol durum yazısını en sola, sağdaki süre/büyüklük verilerini en sağa yaslar
        marginBottom: "10px",
        minHeight: "42px",
        flexShrink: 0,
        boxShadow: "0 1px 3px rgba(0,0,0,0.04)"
      }}>
        {/* Sol Durum Işığı ve Metni */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{
            width: "12px",
            height: "12px",
            borderRadius: "50%",
            backgroundColor: isLevel4 ? "#D9534F" : isLevel1 ? "#F59E0B" : isLevel3 ? "#3B82F6" : (connStatus === "connected" ? "#28A745" : "#6C757D"),
            display: "inline-block"
          }} />
          <span style={{
            fontWeight: "800",
            fontSize: "14px",
            color: isLevel4 ? "#721C24" : isLevel1 ? "#92400E" : isLevel3 ? "#1E40AF" : "#2B303A"
          }}>
            {isLevel4 ? "DEPREM DOĞRULANDI" :
             isLevel1 ? `SARSINTI DOĞRULANIYOR (${alertState.confirmingDevices || triggeredCount}/10 Cihaz)` :
             isLevel3 ? "DÜŞÜK BÜYÜKLÜKTE SARSINTI" :
             isLevel2 ? "YANLIŞ ALARM ENGELLENDİ" :
             connStatus === "connected" ? "Sunucuya bağlı" : "Bağlantı Bekleniyor"}
          </span>
        </div>

        {/* Sağ Büyüklük, Onaylayan Cihaz ve Süre Metrikleri */}
        {(isLevel4 || isLevel3) && (
          <div style={{ display: "flex", gap: "24px", alignItems: "center", color: "#721C24" }}>
            <div style={{ fontSize: "13px", fontWeight: "600" }}>
              Büyüklük: <span style={{ fontSize: "16px", fontWeight: "800" }}>M {alertState.magnitude || "-"}</span>
            </div>
            <div style={{ fontSize: "13px", fontWeight: "700" }}>
              {alertState.confirmingDevices} cihaz onayladı
            </div>
            <div style={{ fontSize: "14px", fontWeight: "800" }}>
              Süre: {durationSec} sn
            </div>
          </div>
        )}
      </div>

      {/*ANA GÖVDE (3 SÜTUNLU IZGARA) */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "240px 1fr 280px", //Sol paneli 240px sabit, sağ paneli 280px sabit yapar ortadaki haritaya kalan tüm boş alanı (1fr) verir
        gap: "12px",
        flex: 1,
        minHeight: 0,
        overflow: "hidden"
      }}>
        {/* SOL: Bağlı Cihazlar Listesi */}
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div style={{ fontSize: "11px", fontWeight: "700", marginBottom: "6px", color: "#444" }}>
            BAĞLI CİHAZLAR ({STATIONS.length})
          </div>
          <div style={{
            background: "#D8DCE0",
            borderRadius: "4px",
            padding: "8px",
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "5px"
          }}>
            {STATIONS.map((st) => {     //Her istasyonun anlık sarsıntı durumunu gösteren döngü
              const isTriggered = deviceStatuses[st.id]?.status === "tetiklendi";
              return (
                <div key={st.id} style={{
                  background: "#FFFFFF",
                  padding: "5px 8px",
                  borderRadius: "3px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  fontSize: "11px",
                  boxShadow: "0 1px 2px rgba(0,0,0,0.03)"
                }}>
                  <span style={{ fontWeight: "600" }}>{st.id}</span>
                  <span style={{
                    background: isTriggered ? "#F8D7DA" : "#E9ECEF",
                    color: isTriggered ? "#721C24" : "#495057",
                    fontSize: "10px",
                    fontWeight: isTriggered ? "700" : "500",
                    padding: "2px 6px",
                    borderRadius: "3px"
                  }}>
                    {isTriggered ? "tetiklendi" : "bekleniyor"}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* ORTA: Canlı Harita */}
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div style={{ fontSize: "11px", fontWeight: "700", marginBottom: "6px", color: "#444" }}>
            CANLI HARİTA
          </div>
          <div
            ref={mapContainerRef}
            style={{
              background: "#FFFFFF",
              borderRadius: "4px",
              border: "1px solid #C8CED3",
              flex: 1,
              width: "100%",
              minHeight: 0,
              overflow: "hidden"
            }}
          />
        </div>

        {/* SAĞ: Olay Geçmişi*/}
        <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <div style={{ fontSize: "11px", fontWeight: "700", marginBottom: "6px", color: "#444" }}>
            OLAY GEÇMİŞİ
          </div>
          <div style={{
            background: "#D8DCE0",
            borderRadius: "4px",
            padding: "8px",
            flex: 1,
            minHeight: 0,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",    //tüm elemanların yan yana değil yukarıdan aşağıya doğru sütun şeklinde dizilmesini sağlar
            gap: "5px"
          }}>
            {logs.map((item, idx) => (    //Olay geçmişi listesini ekrana basan ve her olayın türüne göre sol kenarına renkli bir çizgi çeken döngü
              <div key={idx} style={{
                background: "#FFFFFF",
                padding: "6px 8px",
                borderRadius: "3px",
                fontSize: "11px",
                boxShadow: "0 1px 2px rgba(0,0,0,0.03)",
                borderLeft: `4px solid ${
                  item.kind === "alert" ? "#D9534F" :
                  item.kind === "trigger" ? "#28A745" :
                  item.kind === "rejected" ? "#F59E0B" : "#4A5568"
                }`
              }}>
                {item.text}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* SENARYO KONTROL BUTONLARI */}
      <div style={{
        marginTop: "10px",
        display: "grid",
        gridTemplateColumns: "repeat(5, 1fr) 90px",
        gap: "8px",
        flexShrink: 0
      }}>
        <button onClick={startScenario1} style={btnStyle("#059669")}>1. Gerçek Deprem</button>
        <button onClick={startScenario2} style={btnStyle("#2563EB")}>2. Düşük Şiddet</button>
        <button onClick={startScenario3} style={btnStyle("#0D9488")}>3. Ağ Gecikmesi</button>
        <button onClick={startScenario4} style={btnStyle("#475569")}>4. Gürültü Testi</button>
        <button onClick={startScenario5} style={btnStyle("#D97706")}>5. Paket Kaybı</button>
        <button onClick={handleStop} style={btnStyle("#DC2626")}>Durdur</button>
      </div>
    </div>
  );
}

// Butonlar için ortak CSS stil üreteci
const btnStyle = (bg) => ({
  background: bg,
  color: "#FFF",
  padding: "10px 4px",
  fontSize: "11px",
  fontWeight: "700",
  border: "none",
  borderRadius: "4px",
  cursor: "pointer"
});