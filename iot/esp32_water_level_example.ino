// HydroInsight-compatible ESP32 serial example.
// Keep your existing OLED/UI code and add the JSON line below to its serial loop.
// Wi-Fi is intentionally optional; backend/bridge/serial_bridge.py can forward
// these lines from the USB serial port without changing the hardware build.

#include <ArduinoJson.h>

void emitHydroInsightReading(const char* deviceId, float distanceCm, float temperatureC) {
  StaticJsonDocument<256> doc;
  doc["device_id"] = deviceId;
  doc["timestamp"] = "2026-01-01T00:00:00Z"; // replace with NTP/RTC time in deployment
  doc["distance_cm"] = distanceCm;
  doc["water_level_percent"] = nullptr;
  doc["water_depth_cm"] = nullptr;
  doc["temperature_c"] = temperatureC;
  serializeJson(doc, Serial);
  Serial.println();
}

void setup() {
  Serial.begin(115200);
}

void loop() {
  // Replace with the existing sensor read and OLED update.
  emitHydroInsightReading("ESP32-001", 20.0f, NAN);
  delay(10000);
}

