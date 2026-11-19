/* AquaSense AI ESP32 monitor with stable automatic startup calibration. */
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define DEVICE_ID "ESP32-001"
#define TRIG_PIN 5
#define ECHO_PIN 18
#define OLED_SDA 21
#define OLED_SCL 22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_ADDRESS 0x3C

const float MIN_DISTANCE_CM = 2.0f;
const float MAX_DISTANCE_CM = 400.0f;
const int MEASUREMENT_SAMPLES = 9;
const int CALIBRATION_SAMPLES = 21;
const int SAMPLE_DELAY_MS = 55;
const float SMOOTHING_FACTOR = 0.15f;
const unsigned long OUTPUT_INTERVAL_MS = 1000;

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
float smoothedWaterHeight = -1.0f;
float referenceHeightCm = -1.0f;
unsigned long lastOutput = 0;

void sortValues(float values[], int count) {
  for (int i = 0; i < count - 1; i++) for (int j = 0; j < count - i - 1; j++) if (values[j] > values[j + 1]) {
    float temporary = values[j]; values[j] = values[j + 1]; values[j + 1] = temporary;
  }
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10); digitalWrite(TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) return -1.0f;
  float distance = (duration * 0.0343f) / 2.0f;
  return distance >= MIN_DISTANCE_CM && distance <= MAX_DISTANCE_CM ? distance : -1.0f;
}

float readMedianDistance() {
  float values[MEASUREMENT_SAMPLES]; int validCount = 0;
  for (int i = 0; i < MEASUREMENT_SAMPLES; i++) {
    float distance = readDistanceCm();
    if (distance >= MIN_DISTANCE_CM && distance <= MAX_DISTANCE_CM) values[validCount++] = distance;
    delay(SAMPLE_DELAY_MS);
  }
  if (validCount < 3) return -1.0f;
  sortValues(values, validCount);
  return validCount % 2 == 0 ? (values[validCount / 2 - 1] + values[validCount / 2]) / 2.0f : values[validCount / 2];
}

bool calibrateReferenceHeight() {
  Serial.println("CALIBRATION: keep the real tank at its empty reference level.");
  display.clearDisplay(); display.setTextColor(SSD1306_WHITE); display.setTextSize(1);
  display.setCursor(0, 12); display.println("Calibrating...");
  display.setCursor(0, 30); display.println("Keep reference still"); display.display();
  delay(2000);

  float values[CALIBRATION_SAMPLES]; int validCount = 0;
  for (int i = 0; i < CALIBRATION_SAMPLES; i++) {
    float distance = readDistanceCm();
    if (distance >= MIN_DISTANCE_CM && distance <= MAX_DISTANCE_CM) values[validCount++] = distance;
    delay(80);
  }
  if (validCount < 15) return false;
  sortValues(values, validCount);
  float median = values[validCount / 2];
  float spread = values[validCount - 1] - values[0];
  if (spread > 8.0f) return false;
  referenceHeightCm = median;
  Serial.print("Automatic reference height: "); Serial.print(referenceHeightCm, 2); Serial.println(" cm");
  display.clearDisplay(); display.setCursor(0, 12); display.println("Calibration done");
  display.setCursor(0, 30); display.print("Reference: "); display.print(referenceHeightCm, 1); display.println(" cm"); display.display();
  delay(1200);
  return true;
}

void showReading(float distance, float waterHeight, float percentage) {
  display.clearDisplay(); display.setTextColor(SSD1306_WHITE); display.setTextSize(1);
  display.setCursor(0, 0); display.println("Jal-Drishti");
  display.setCursor(0, 14); display.print("Ref: "); display.print(referenceHeightCm, 1); display.println(" cm");
  display.setCursor(0, 28); display.print("Distance: "); display.print(distance, 1); display.println(" cm");
  display.setCursor(0, 42); display.print("Water: "); display.print(waterHeight, 1); display.print(" cm "); display.print(percentage, 1); display.println("%");
  display.display();
}

void publishReading(float distance, float waterHeight, float percentage) {
  // Send the exact values used by the OLED in one atomic packet. The bridge and
  // web app display these fields without recalculating them.
  Serial.print("{\"device_id\":\""); Serial.print(DEVICE_ID);
  Serial.print("\",\"timestamp\":\"");
  unsigned long now = millis();
  Serial.print(now);
  Serial.print("\",\"distance_cm\":"); Serial.print(distance, 1);
  Serial.print(",\"water_depth_cm\":"); Serial.print(waterHeight, 1);
  Serial.print(",\"water_level_percent\":"); Serial.print(percentage, 1);
  Serial.println(",\"temperature_c\":null}");
}

void setup() {
  Serial.begin(115200); pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT); digitalWrite(TRIG_PIN, LOW);
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) { Serial.println("OLED initialization failed."); while (true) delay(1000); }
  while (!calibrateReferenceHeight()) {
    Serial.println("Calibration failed: aim at the real stable reference and retrying.");
    display.clearDisplay(); display.setCursor(0, 12); display.println("Calibration failed"); display.setCursor(0, 30); display.println("Check sensor aim"); display.display();
    delay(3000);
  }
  display.clearDisplay(); display.display();
  Serial.println("AquaSense ESP32 monitor ready.");
  Serial.print("Automatic reference height: "); Serial.print(referenceHeightCm, 1); Serial.println(" cm");
}

void loop() {
  if (millis() - lastOutput < OUTPUT_INTERVAL_MS) return;
  lastOutput = millis();
  float distance = readMedianDistance();
  if (distance < 0) { Serial.println("Invalid sensor reading."); return; }
  float rawWaterHeight = constrain(referenceHeightCm - distance, 0.0f, referenceHeightCm);
  if (smoothedWaterHeight < 0) smoothedWaterHeight = rawWaterHeight;
  else smoothedWaterHeight = SMOOTHING_FACTOR * rawWaterHeight + (1.0f - SMOOTHING_FACTOR) * smoothedWaterHeight;
  float waterHeight = constrain(smoothedWaterHeight, 0.0f, referenceHeightCm);
  float percentage = (waterHeight / referenceHeightCm) * 100.0f;
  showReading(distance, waterHeight, percentage);
  publishReading(distance, waterHeight, percentage);
}
