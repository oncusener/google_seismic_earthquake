import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TouchableOpacity, ScrollView, SafeAreaView } from 'react-native';
import { generateMockScenario, TEST_SCENARIOS } from './services/mockDataGenerator';
import {
  evaluateSTA_LTA,
  validateTriggeredCluster,
  estimateEpicenter,
  calculateLeadTime,
} from './services/algorithms';

const FIXED_DEVICES = [
  { id: 'phone_101', top: '22%', left: '50%' },
  { id: 'phone_102', top: '48%', left: '38%' },
  { id: 'phone_103', top: '70%', left: '36%' },
  { id: 'phone_104', top: '10%', left: '58%' },
  { id: 'phone_105', top: '35%', left: '44%' },
  { id: 'phone_106', top: '55%', left: '60%' },
];

export default function App() {
  const [selectedScenario, setSelectedScenario] = useState('SCENARIO_1');
  const [isAlertActive, setIsAlertActive] = useState(false);
  const [alertType, setAlertType] = useState('danger'); // danger | info
  const [alertDetails, setAlertDetails] = useState({ mag: '6.3', count: '4 cihaz', time: '7.2 sn' });
  const [deviceStates, setDeviceStates] = useState({});
  const [eventLogs, setEventLogs] = useState([
    { text: 'Sistem başlatıldı', color: '#1E293B' },
    { text: '6 cihaz bağlandı', color: '#1E293B' }
  ]);
  const [bottomStatus, setBottomStatus] = useState('Herhangi bir sarsıntı algılanmadı.');
  const [waveRadius, setWaveRadius] = useState(0);

  const timeoutsRef = useRef([]);

  const clearAllTimeouts = () => {
    timeoutsRef.current.forEach(t => clearTimeout(t));
    timeoutsRef.current = [];
  };

  useEffect(() => {
    return () => clearAllTimeouts();
  }, []);

  // Dalga Animasyonu
  useEffect(() => {
    let animFrame;
    if (isAlertActive) {
      const animate = () => {
        setWaveRadius((prev) => (prev >= 260 ? 0 : prev + 2.5));
        animFrame = requestAnimationFrame(animate);
      };
      animFrame = requestAnimationFrame(animate);
    } else {
      setWaveRadius(0);
    }
    return () => cancelAnimationFrame(animFrame);
  }, [isAlertActive]);

  // Simülasyon Çalıştırma
  const runSimulation = (scenarioKey = selectedScenario) => {
    clearAllTimeouts();
    setIsAlertActive(false);
    setWaveRadius(0);
    setDeviceStates({});

    const scenarioData = generateMockScenario(scenarioKey);

    setEventLogs([
      { text: 'Sistem başlatıldı', color: '#1E293B' },
      { text: '6 cihaz bağlandı', color: '#1E293B' },
      { text: `[${scenarioData.name}] çalıştırıldı`, color: '#3B82F6' }
    ]);
    setBottomStatus('Sensör verileri dinleniyor...');

    const incomingDevices = [];

    scenarioData.devices.forEach((dev) => {
      const t = setTimeout(() => {
        const isTriggered = evaluateSTA_LTA(dev.sta_lta);

        if (isTriggered) {
          incomingDevices.push(dev);

          // Cihaz durumunu 'tetiklendi' yap
          setDeviceStates((prev) => ({ ...prev, [dev.device_id]: 'tetiklendi' }));
          setEventLogs((prev) => [
            ...prev,
            { text: `${dev.device_id} tetiklendi (STA/LTA: ${dev.sta_lta})`, color: '#84CC16' }
          ]);
          setBottomStatus(`${incomingDevices.length} cihaz tetiklendi`);

          // Doğrulama Kontrolü
          const validation = validateTriggeredCluster(incomingDevices);

          if (validation.isValid) {
            const epicenter = estimateEpicenter(validation.validDevices);
            const leadTime = calculateLeadTime(dev.distance_km || 12);

            // Büyüklük Kontrolü (Düşük Büyüklük Bilgilendirmesi mi?)
            const isLowMag = scenarioData.magnitude < 3.0;
            setAlertType(isLowMag ? 'info' : 'danger');

            setIsAlertActive(true);
            setAlertDetails({
              mag: `${scenarioData.magnitude}`,
              count: `${validation.validDevices.length} cihaz`,
              time: `${leadTime || 7.2} sn`
            });

            // Onaylanan cihazları güncelle
            setDeviceStates((prev) => {
              const updated = { ...prev };
              validation.validDevices.forEach((d) => {
                updated[d.device_id] = isLowMag ? 'bilgi' : 'onaylandi';
              });
              return updated;
            });

            setEventLogs((prev) => [
              ...prev,
              { text: isLowMag ? 'Hissedilebilir Düşük Sarsıntı (Bilgilendirme)' : 'Deprem doğrulandı', color: isLowMag ? '#3B82F6' : '#EF4444' },
              { text: `Tahmini Merkez: ${epicenter.latitude}°N, ${epicenter.longitude}°E`, color: '#64748B' },
              { text: 'Uyarı tüm bağlı cihazlara yayınlandı.', color: isLowMag ? '#3B82F6' : '#EF4444' }
            ]);
            setBottomStatus(isLowMag ? 'Düşük büyüklükte sarsıntı tespit edildi (Bilgilendirme).' : 'Uyarı tüm bağlı cihazlara yayınlandı.');
          } else {
            // Doğrulanamadıysa ve son cihaz geldiyse iptal kararı ver
            if (incomingDevices.length === scenarioData.devices.length) {
              const cancelTimer = setTimeout(() => {
                setDeviceStates((prev) => {
                  const cancelled = { ...prev };
                  incomingDevices.forEach((d) => {
                    cancelled[d.device_id] = 'iptal';
                  });
                  return cancelled;
                });
                setEventLogs((prev) => [
                  ...prev,
                  { text: `İptal Edildi: ${validation.reason}`, color: '#8B5CF6' }
                ]);
                setBottomStatus(validation.reason);
              }, 800);
              timeoutsRef.current.push(cancelTimer);
            }
          }
        }
      }, dev.time_offset_ms);

      timeoutsRef.current.push(t);
    });
  };

  const selectAndRunScenario = (key) => {
    setSelectedScenario(key);
    runSimulation(key);
  };

  const resetAll = () => {
    clearAllTimeouts();
    setIsAlertActive(false);
    setDeviceStates({});
    setWaveRadius(0);
    setEventLogs([
      { text: 'Sistem başlatıldı', color: '#1E293B' },
      { text: '6 cihaz bağlandı', color: '#1E293B' }
    ]);
    setBottomStatus('Herhangi bir sarsıntı algılanmadı.');
  };

  return (
    <SafeAreaView style={styles.page}>
      <View style={styles.container}>
        {/* HEADER */}
        <View style={styles.headerBox}>
          <Text style={styles.headerTitle}>DEPREM ERKEN UYARI SİSTEMİ</Text>
        </View>

        {/* BANNER */}
        {isAlertActive ? (
          <View style={[styles.alertBanner, alertType === 'info' && styles.alertBannerInfo]}>
            <Text style={[styles.alertBannerTitle, alertType === 'info' && { color: '#1D4ED8' }]}>
              {alertType === 'info' ? 'ℹ️ DÜŞÜK BÜYÜKLÜKTE SARSINTI' : '🔴 DEPREM DOĞRULANDI'}
            </Text>
            <View style={styles.alertMetaGroup}>
              <View style={styles.metaItem}>
                <Text style={[styles.metaLabel, alertType === 'info' && { color: '#1E40AF' }]}>Büyüklük</Text>
                <Text style={[styles.metaVal, alertType === 'info' && { color: '#1D4ED8' }]}>{alertDetails.mag}</Text>
              </View>
              <View style={styles.metaItem}>
                <Text style={[styles.metaLabel, alertType === 'info' && { color: '#1E40AF' }]}>Doğrulama</Text>
                <Text style={[styles.metaVal, alertType === 'info' && { color: '#1D4ED8' }]}>{alertDetails.count}</Text>
              </View>
              <View style={styles.metaItem}>
                <Text style={[styles.metaLabel, alertType === 'info' && { color: '#1E40AF' }]}>Kalan Süre</Text>
                <Text style={[styles.metaVal, alertType === 'info' && { color: '#1D4ED8' }]}>{alertDetails.time}</Text>
              </View>
            </View>
          </View>
        ) : (
          <View style={styles.serverStatusBox}>
            <View style={styles.greenDot} />
            <Text style={styles.serverStatusText}>Sunucuya bağlı</Text>
          </View>
        )}

        {/* 3 SÜTUN */}
        <View style={styles.threeColumnGrid}>
          {/* SOL: BAĞLI CİHAZLAR */}
          <View style={styles.leftColumn}>
            <Text style={styles.columnHeader}>BAĞLI CİHAZLAR (6)</Text>
            {FIXED_DEVICES.map((dev) => {
              const st = deviceStates[dev.id] || 'bekleniyor';
              return (
                <View key={dev.id} style={styles.deviceRow}>
                  <Text style={styles.deviceName}>{dev.id}</Text>
                  <View style={[
                    styles.statusPill,
                    st === 'bekleniyor' && styles.pillGrey,
                    st === 'tetiklendi' && styles.pillYellow,
                    st === 'onaylandi' && styles.pillRed,
                    st === 'bilgi' && styles.pillBlue,
                    st === 'iptal' && styles.pillPurple,
                  ]}>
                    <Text style={[
                      styles.statusPillText,
                      (st === 'onaylandi' || st === 'iptal' || st === 'bilgi') && { color: '#FFF' }
                    ]}>
                      {st}
                    </Text>
                  </View>
                </View>
              );
            })}
          </View>

          {/* ORTA: CANLI HARİTA */}
          <View style={styles.centerColumn}>
            <Text style={styles.columnHeader}>CANLI HARİTA</Text>
            <View style={styles.mapGridContainer}>
              <View style={styles.gridLinesRow} />
              <View style={[styles.gridLinesRow, { top: '25%' }]} />
              <View style={[styles.gridLinesRow, { top: '50%' }]} />
              <View style={[styles.gridLinesRow, { top: '75%' }]} />
              <View style={styles.gridLinesCol} />
              <View style={[styles.gridLinesCol, { left: '25%' }]} />
              <View style={[styles.gridLinesCol, { left: '50%' }]} />
              <View style={[styles.gridLinesCol, { left: '75%' }]} />

              {/* Dalgalar ve Merkez */}
              {isAlertActive && (
                <>
                  <View style={[styles.epicenterDot, { top: '40%', left: '46%' }]} />
                  <View style={[styles.waveCircle, styles.pWave, {
                    width: waveRadius * 2,
                    height: waveRadius * 2,
                    borderRadius: waveRadius,
                    top: '40%',
                    left: '46%',
                    transform: [{ translateX: -waveRadius }, { translateY: -waveRadius }]
                  }]} />
                  <View style={[styles.waveCircle, styles.sWave, {
                    width: waveRadius * 1.3,
                    height: waveRadius * 1.3,
                    borderRadius: waveRadius * 0.65,
                    top: '40%',
                    left: '46%',
                    transform: [{ translateX: -waveRadius * 0.65 }, { translateY: -waveRadius * 0.65 }]
                  }]} />
                </>
              )}

              {/* 6 Cihaz */}
              {FIXED_DEVICES.map((dev) => {
                const st = deviceStates[dev.id] || 'bekleniyor';
                return (
                  <View
                    key={dev.id}
                    style={[
                      styles.mapDot,
                      { top: dev.top, left: dev.left },
                      st === 'tetiklendi' && styles.mapDotYellow,
                      st === 'onaylandi' && styles.mapDotRed,
                      st === 'bilgi' && styles.mapDotBlue,
                      st === 'iptal' && styles.mapDotPurple,
                    ]}
                  >
                    <View style={styles.mapDotInner} />
                  </View>
                );
              })}
            </View>
          </View>

          {/* SAĞ: OLAY GEÇMİŞİ */}
          <View style={styles.rightColumn}>
            <Text style={styles.columnHeader}>OLAY GEÇMİŞİ</Text>
            <ScrollView style={styles.logsScroll} showsVerticalScrollIndicator={false}>
              {eventLogs.map((log, i) => (
                <View key={i} style={styles.logCard}>
                  <View style={[styles.logAccentBar, { backgroundColor: log.color }]} />
                  <Text style={styles.logCardText}>{log.text}</Text>
                </View>
              ))}
            </ScrollView>
          </View>
        </View>

        {/* ALT DURUM BARI */}
        <View style={styles.bottomStatusBanner}>
          <Text style={styles.bottomStatusText}>{bottomStatus}</Text>
        </View>

        {/* KONTROL PANELİ */}
        <View style={styles.controlDeck}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0, marginBottom: 8 }}>
            {Object.keys(TEST_SCENARIOS).map((key) => (
              <TouchableOpacity
                key={key}
                style={[styles.scenarioChip, selectedScenario === key && styles.scenarioChipActive]}
                onPress={() => selectAndRunScenario(key)}
              >
                <Text style={[styles.scenarioChipText, selectedScenario === key && { color: '#FFF' }]}>
                  {TEST_SCENARIOS[key].name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          <View style={styles.actionButtonsRow}>
            <TouchableOpacity style={styles.btnStart} onPress={() => runSimulation(selectedScenario)}>
              <Text style={styles.btnTextWhite}>▶ Simülasyonu Yeniden Başlat</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.btnReset} onPress={resetAll}>
              <Text style={styles.btnTextWhite}>🔄 Sıfırla</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: '#D1D5DB' },
  container: { flex: 1, padding: 16, maxWidth: 1200, width: '100%', alignSelf: 'center' },
  headerBox: { backgroundColor: '#E5E7EB', paddingVertical: 14, paddingHorizontal: 16, marginBottom: 8 },
  headerTitle: { fontSize: 20, fontWeight: '900', color: '#111827', letterSpacing: 0.5 },
  serverStatusBox: { backgroundColor: '#E5E7EB', paddingVertical: 10, paddingHorizontal: 16, flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  greenDot: { width: 14, height: 14, borderRadius: 7, backgroundColor: '#10B981', marginRight: 8 },
  serverStatusText: { fontSize: 13, color: '#374151', fontWeight: '500' },
  alertBanner: { backgroundColor: '#FECDD3', borderColor: '#FDA4AF', borderWidth: 1, paddingVertical: 10, paddingHorizontal: 16, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  alertBannerInfo: { backgroundColor: '#DBEAFE', borderColor: '#BFDBFE' },
  alertBannerTitle: { fontSize: 16, fontWeight: '900', color: '#BE123C' },
  alertMetaGroup: { flexDirection: 'row', gap: 20 },
  metaItem: { alignItems: 'center' },
  metaLabel: { fontSize: 10, color: '#881337' },
  metaVal: { fontSize: 14, fontWeight: 'bold', color: '#BE123C' },
  threeColumnGrid: { flexDirection: 'row', flex: 1, gap: 14, minHeight: 380 },
  columnHeader: { fontSize: 13, fontWeight: '800', color: '#1F2937', marginBottom: 10 },
  leftColumn: { flex: 1.2, backgroundColor: '#E5E7EB', padding: 12, borderRadius: 2 },
  deviceRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#FFFFFF', paddingVertical: 9, paddingHorizontal: 12, marginBottom: 8, borderRadius: 2 },
  deviceName: { fontSize: 13, fontWeight: '600', color: '#1F2937' },
  statusPill: { paddingHorizontal: 12, paddingVertical: 4, borderRadius: 3 },
  statusPillText: { fontSize: 11, fontWeight: '600', color: '#4B5563' },
  pillGrey: { backgroundColor: '#E5E7EB' },
  pillYellow: { backgroundColor: '#FEF08A' },
  pillRed: { backgroundColor: '#F43F5E' },
  pillBlue: { backgroundColor: '#3B82F6' },
  pillPurple: { backgroundColor: '#A855F7' },
  centerColumn: { flex: 2, backgroundColor: '#E5E7EB', padding: 12, borderRadius: 2 },
  mapGridContainer: { flex: 1, backgroundColor: '#FFFFFF', position: 'relative', overflow: 'hidden', borderWidth: 1, borderColor: '#D1D5DB' },
  gridLinesRow: { position: 'absolute', width: '100%', height: 1, backgroundColor: '#E5E7EB', top: 0 },
  gridLinesCol: { position: 'absolute', height: '100%', width: 1, backgroundColor: '#E5E7EB', left: 0 },
  mapDot: { position: 'absolute', width: 18, height: 18, borderRadius: 9, backgroundColor: '#1F2937', justifyContent: 'center', alignItems: 'center', borderWidth: 2, borderColor: '#FFFFFF', zIndex: 10 },
  mapDotInner: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#FFFFFF' },
  mapDotYellow: { backgroundColor: '#EAB308' },
  mapDotRed: { backgroundColor: '#EF4444' },
  mapDotBlue: { backgroundColor: '#3B82F6' },
  mapDotPurple: { backgroundColor: '#8B5CF6' },
  epicenterDot: { position: 'absolute', width: 22, height: 22, borderRadius: 11, backgroundColor: '#B91C1C', zIndex: 12, borderWidth: 3, borderColor: '#FECDD3' },
  waveCircle: { position: 'absolute', borderColor: '#4B5563', borderWidth: 2, zIndex: 5 },
  pWave: { borderColor: '#6B7280', borderStyle: 'solid' },
  sWave: { borderColor: '#DC2626', borderWidth: 3 },
  rightColumn: { flex: 1.5, backgroundColor: '#E5E7EB', padding: 12, borderRadius: 2 },
  logsScroll: { flex: 1 },
  logCard: { flexDirection: 'row', backgroundColor: '#FFFFFF', paddingVertical: 10, paddingHorizontal: 10, marginBottom: 8, alignItems: 'center', borderRadius: 2 },
  logAccentBar: { width: 4, height: 18, borderRadius: 2, marginRight: 10 },
  logCardText: { fontSize: 12, color: '#1F2937', fontWeight: '500' },
  bottomStatusBanner: { backgroundColor: '#E5E7EB', paddingVertical: 10, paddingHorizontal: 16, alignItems: 'center', marginVertical: 8 },
  bottomStatusText: { fontStyle: 'italic', fontSize: 13, color: '#374151' },
  controlDeck: { backgroundColor: '#E5E7EB', padding: 10, borderRadius: 2 },
  scenarioChip: { backgroundColor: '#D1D5DB', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 4, marginRight: 8 },
  scenarioChipActive: { backgroundColor: '#1E293B' },
  scenarioChipText: { fontSize: 11, color: '#374151', fontWeight: '600' },
  actionButtonsRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
  btnStart: { flex: 1, backgroundColor: '#059669', paddingVertical: 8, alignItems: 'center', borderRadius: 4 },
  btnReset: { flex: 1, backgroundColor: '#4B5563', paddingVertical: 8, alignItems: 'center', borderRadius: 4 },
  btnTextWhite: { color: '#FFFFFF', fontWeight: 'bold', fontSize: 12 }
});