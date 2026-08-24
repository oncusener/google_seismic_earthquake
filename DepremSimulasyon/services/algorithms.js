/**
 * Deprem Erken Uyarı - Çekirdek Algoritmalar Modülü
 */

// Sabit Parametreler
export const SYSTEM_PARAMS = {
  STA_LTA_THRESHOLD: 3.5, // Tetiklenme eşik değeri
  N_MIN: 3,               // Minimum doğrulama cihaz sayısı
  R_MAX_KM: 15.0,         // Maksimum kümeleme yarıçapı
  TIME_WINDOW_MS: 1500,   // Çoklu istasyon kayar pencere süresi (1.5 sn)
  P_WAVE_VELOCITY: 6.0,   // km/sn
  S_WAVE_VELOCITY: 3.5,   // km/sn
};

/**
 * 1. İki Koordinat Arası Mesafe Hesabı (Haversine Formülü - km)
 */
export function calculateDistanceKm(lat1, lon1, lat2, lon2) {
  const R = 6371; // Dünya yarıçapı (km)
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * 2. STA/LTA ve Sinyal Tetiklenme Denetimi
 */
export function evaluateSTA_LTA(staLtaRatio) {
  return staLtaRatio >= SYSTEM_PARAMS.STA_LTA_THRESHOLD;
}

/**
 * 3. Çoklu İstasyon Doğrulama Algoritması (Multi-Station Validation)
 * @param {Array} triggeredDevices - Tetiklenen cihaz listesi
 * @returns {object} { isValid: boolean, reason: string, validDevices: Array }
 */
export function validateTriggeredCluster(triggeredDevices) {
  if (!triggeredDevices || triggeredDevices.length === 0) {
    return { isValid: false, reason: "Tetiklenen cihaz yok", validDevices: [] };
  }

  // 1. Kural: Cihaz sayısı eşiği (N >= N_min)
  if (triggeredDevices.length < SYSTEM_PARAMS.N_MIN) {
    return {
      isValid: false,
      reason: `Yetersiz cihaz sayısı (N = ${triggeredDevices.length} < ${SYSTEM_PARAMS.N_MIN}) - Yanlış Alarm`,
      validDevices: triggeredDevices,
    };
  }

  // 2. Kural: Mesafe Kümeleme Kontrolü (R <= R_max)
  // İlk tetiklenen cihaz referans alınarak diğer cihazların mesafesi kontrol edilir
  const refDevice = triggeredDevices[0];
  const cluster = triggeredDevices.filter((dev) => {
    const dist = calculateDistanceKm(
      refDevice.location.latitude,
      refDevice.location.longitude,
      dev.location.latitude,
      dev.location.longitude
    );
    return dist <= SYSTEM_PARAMS.R_MAX_KM;
  });

  if (cluster.length >= SYSTEM_PARAMS.N_MIN) {
    return {
      isValid: true,
      reason: `Çoklu doğrulama başarılı (${cluster.length} cihaz, R <= ${SYSTEM_PARAMS.R_MAX_KM} km)`,
      validDevices: cluster,
    };
  } else {
    return {
      isValid: false,
      reason: `Cihazlar arası mesafe sınırı aşıldı (R > ${SYSTEM_PARAMS.R_MAX_KM} km) - Dağınık Tetiklenme`,
      validDevices: cluster,
    };
  }
}

/**
 * 4. Merkez Üssü Tahmini (Weighted Centroid - Ağırlıklı Merkez)
 * STA/LTA oranları ağırlık (w_i) olarak kullanılır
 */
export function estimateEpicenter(validDevices) {
  if (!validDevices || validDevices.length === 0) return null;

  let totalWeight = 0;
  let weightedLatSum = 0;
  let weightedLonSum = 0;

  validDevices.forEach((dev) => {
    const weight = dev.sta_lta || 1.0;
    totalWeight += weight;
    weightedLatSum += dev.location.latitude * weight;
    weightedLonSum += dev.location.longitude * weight;
  });

  return {
    latitude: parseFloat((weightedLatSum / totalWeight).toFixed(4)),
    longitude: parseFloat((weightedLonSum / totalWeight).toFixed(4)),
  };
}

/**
 * 5. Büyüklük (Magnitude) ve S Dalgası Kalan Süre Hesabı
 */
export function calculateLeadTime(distanceKm) {
  const tP = distanceKm / SYSTEM_PARAMS.P_WAVE_VELOCITY;
  const tS = distanceKm / SYSTEM_PARAMS.S_WAVE_VELOCITY;
  const leadTime = tS - tP; // S ve P arasındaki uyarı süresi (sn)
  return Math.max(0, parseFloat(leadTime.toFixed(1)));
}