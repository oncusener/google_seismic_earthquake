/**
 * Mock Data Generator - 5 Test Senaryosu
 */
const BASE_CONFIG = {
  epicenter: { latitude: 40.9500, longitude: 28.8000 },
  depth_km: 10,
  noise_level: "low"
};

export const TEST_SCENARIOS = {
  SCENARIO_1: {
    scenario_id: "test_scenario_01",
    name: "1. Gerçek Deprem (Doğrulanmış)",
    ...BASE_CONFIG,
    magnitude: 6.3,
    device_count: 5,
    device_radius_km: 12,
    false_positive_devices: 0
  },
  SCENARIO_2: {
    scenario_id: "test_scenario_02",
    name: "2. Tekil Yanlış Alarm (Gürültü)",
    ...BASE_CONFIG,
    magnitude: 0.0,
    device_count: 0,
    device_radius_km: 0,
    false_positive_devices: 1
  },
  SCENARIO_3: {
    scenario_id: "test_scenario_03",
    name: "3. Dağınık Tetiklenme (Mesafe Dışı)",
    ...BASE_CONFIG,
    magnitude: 5.5,
    device_count: 4,
    device_radius_km: 45,
    false_positive_devices: 0
  },
  SCENARIO_4: {
    scenario_id: "test_scenario_04",
    name: "4. Düşük Büyüklük (Bilgilendirme)",
    ...BASE_CONFIG,
    magnitude: 2.8,
    device_count: 4,
    device_radius_km: 8,
    false_positive_devices: 0
  },
  SCENARIO_5: {
    scenario_id: "test_scenario_05",
    name: "5. Ağ Gecikmesi Stres Testi",
    ...BASE_CONFIG,
    magnitude: 5.8,
    device_count: 5,
    device_radius_km: 12,
    false_positive_devices: 0
  }
};

export function generateMockScenario(scenarioKey) {
  const scenario = TEST_SCENARIOS[scenarioKey];
  if (!scenario) throw new Error("Geçersiz senaryo!");

  const originTime = Date.now();
  const devices = [];

  // Senaryo 2: Tekil gürültü
  if (scenarioKey === 'SCENARIO_2') {
    devices.push({
      device_id: "phone_101",
      location: { latitude: 40.9500, longitude: 28.8000 },
      distance_km: 2.0,
      sta_lta: 4.8,
      triggered: true,
      time_offset_ms: 200
    });
    return { ...scenario, origin_time: originTime, devices };
  }

  // Diğer senaryolar
  const deviceList = ['phone_101', 'phone_102', 'phone_104', 'phone_105', 'phone_103', 'phone_106'];
  const count = Math.min(scenario.device_count, deviceList.length);

  for (let i = 0; i < count; i++) {
    const devId = deviceList[i];
    const distanceKm = (i + 1) * (scenario.device_radius_km / count);
    
    // Ağ gecikmesi senaryosunda gecikmeyi artır
    const timeDelay = scenarioKey === 'SCENARIO_5' 
      ? 300 + (i * 1200) 
      : 200 + (i * 450);

    devices.push({
      device_id: devId,
      location: {
        latitude: parseFloat((scenario.epicenter.latitude + (distanceKm / 111)).toFixed(4)),
        longitude: parseFloat((scenario.epicenter.longitude + (distanceKm / 111)).toFixed(4))
      },
      distance_km: parseFloat(distanceKm.toFixed(1)),
      sta_lta: parseFloat((3.8 + Math.random() * 2.0).toFixed(1)),
      triggered: true,
      time_offset_ms: timeDelay
    });
  }

  return {
    ...scenario,
    origin_time: originTime,
    devices
  };
}