#include <BH1750.h>
#include <Wire.h>
#include <WiFiNINA.h>
#include <PubSubClient.h>
#include <Arduino.h>

#define TC_TIMER       TC3
#define TC_TIMER_IRQn  TC3_IRQn
#define TC_HANDLER     TC3_Handler

// WiFi credentials
const char* ssid = "Quang Huy";
const char* password = "Danang040903";

// MQTT Broker
const int ID = 1;
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
char topic[50];
char topic1[50];
char topic2[50];
char topic3[50];
char topic4[50];
char topic_sensor_status[50];
char topic_motion_sensor_status[50];

const int motionPin = 2;
const int ledPin = 3;
float latestLightValue = 0.0;
int currentBrightness = 0;

volatile bool motionDetected = false;
volatile bool ledState = false;
unsigned long lastMotionTime = 0; // To track the last motion time
const unsigned long countdownDuration = 60000 * 20; // 20 minutes in milliseconds
volatile uint8_t timerCounter = 0; //count

// New variables for motion sensor error detection
unsigned long lastMotionDetectedTime = 0;  // Last time motion was detected
bool motionSensorErrorReported = false;
const unsigned long motionSensorTimeout = 60000 *60 *12; // 12 hours timeout to suspect sensor error


WiFiClient espClient;
PubSubClient client(espClient);

BH1750 lightMeter;

void setupTimer() {
  // Enable clock for TC3
  REG_GCLK_CLKCTRL = GCLK_CLKCTRL_CLKEN |         // Enable GCLK
                     GCLK_CLKCTRL_GEN_GCLK0 |     // Select GCLK0 (48MHz)
                     GCLK_CLKCTRL_ID_TCC2_TC3;    // Feed GCLK to TC3
  while (GCLK->STATUS.bit.SYNCBUSY);              // Wait for synchronization
  
  // Reset TC3
  TC_TIMER->COUNT16.CTRLA.bit.SWRST = 1;
  while (TC_TIMER->COUNT16.CTRLA.bit.SWRST);
  
  // Set TC3 in 16-bit mode
  TC_TIMER->COUNT16.CTRLA.reg = TC_CTRLA_MODE_COUNT16 |   // 16-bit counter mode
                               TC_CTRLA_WAVEGEN_MFRQ |    // Match frequency mode
                               TC_CTRLA_PRESCALER_DIV1024; // Prescaler: 1024
  
  // Set the period (5 second toggle)
  // 48MHz/1024 = 46875 Hz, so for 1 second we need 46875 ticks
  TC_TIMER->COUNT16.CC[0].reg = 46875;
  while (TC_TIMER->COUNT16.STATUS.bit.SYNCBUSY);
  
  // Configure interrupt
  NVIC_SetPriority(TC_TIMER_IRQn, 0);    // Set highest priority
  NVIC_EnableIRQ(TC_TIMER_IRQn);         // Enable the interrupt
  
  // Enable the TC3 interrupt
  TC_TIMER->COUNT16.INTENSET.reg = TC_INTENSET_MC0;
  
  // Enable TC3
  TC_TIMER->COUNT16.CTRLA.bit.ENABLE = 1;
  while (TC_TIMER->COUNT16.STATUS.bit.SYNCBUSY);
}

void TC_HANDLER() {
  // Check for match counter 0 (MC0) interrupt
  if (TC_TIMER->COUNT16.INTFLAG.bit.MC0) {
    // Clear the interrupt flag
    TC_TIMER->COUNT16.INTFLAG.bit.MC0 = 1;
    
    // Increase counter value 
    timerCounter++;
    
    // After 3 secs, update latestLightValue
    if (timerCounter >= 3) {
      latestLightValue = readLightValue();
      if (latestLightValue < 0) {
        sendData(latestLightValue, ledState, currentBrightness);
        timerCounter = 0;
        return;
      } else {
        int pwmValue;
        if (latestLightValue < 100) {
          pwmValue = 255; // Maximum brightness
        } else if (latestLightValue > 300) {
          pwmValue = 0;
          currentBrightness = 0;
          analogWrite(ledPin,0);
        } else {
          pwmValue = map(latestLightValue, 100, 300, 255, 0); // Map lux from 100 to 300
        }
        pwmValue = constrain(pwmValue, 0, 255);  // Ensure it's within PWM range
        if (ledState & pwmValue != 0) {
          currentBrightness = map(pwmValue, 0, 255, 0, 100);
          setIntensity(pwmValue);
        }
      }
      sendData(latestLightValue, ledState, currentBrightness);
      timerCounter = 0;
    }
  }
}

void setup() {
  sprintf(topic, "task11.1/sensorData/%d", ID);
  sprintf(topic1, "task11.1/ledStateData/%d", ID);
  sprintf(topic2, "task11.1/ledStateChangeCommand/%d", ID);
  sprintf(topic3, "task11.1/ledValueCommand/%d", ID);
  sprintf(topic4, "task11.1/ledBrightnessData/%d", ID);
  sprintf(topic_sensor_status, "task11.1/sensorStatus/%d", ID);
  sprintf(topic_motion_sensor_status, "task11.1/motionSensorStatus/%d", ID);

  Serial.begin(115200);
  connectToWiFi();
  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  reconnectMQTT();
  pinMode(motionPin, INPUT_PULLDOWN); 
  Wire.begin();
  setupTimer();
  attachInterrupt(digitalPinToInterrupt(motionPin), motionHandler, RISING);
  
  if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x23)) {
    Serial.println(F("BH1750 Advanced begin"));
  } else {
    Serial.println(F("Error initialising BH1750"));
  }

  lastMotionDetectedTime = millis();  // Initialize last motion detected time
}

float readLightValue() {
  if (lightMeter.measurementReady()) {
    float lux = lightMeter.readLightLevel();
    if (lux < 0 || lux > 100000) {
      Serial.println("Invalid sensor reading detected!");
      sendSensorStatus(false);  // Send sensor error status
      return -1.0;
    }
    sendSensorStatus(true);  // Send sensor OK status
    return lux;
  }
  Serial.println("Measurement not ready");
  sendSensorStatus(false);  // Send sensor error status
  return -1.0;
}


void setSafeLED() {
  Serial.println("Setting LED to safe mode due to sensor error.");
  setIntensity(0);  // Turn off LED
  ledState = false;
  motionDetected = false;
  currentBrightness = 0;
}

void connectToWiFi() {
  Serial.print("Connecting to WiFi...");
  WiFi.begin(ssid, password);

  // Attempting to connect
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nConnected to WiFi!");
}

void turnOffCommand() {
  setIntensity(0);
  currentBrightness = 0;
}

void turnOnCommand() {
  float lux = readLightValue();
  if (lux < 0) {
    // Error value, turn on light
    setIntensity(255);
    currentBrightness = 100;
    return;
  }
  int pwmValue;
  if (lux < 100) {
    pwmValue = 255; // Maximum brightness
  } else if (lux > 300) {
    pwmValue = 0; // Turn off the LED
  } else {
    pwmValue = map(lux, 100, 300, 255, 0); // Map lux from 100 to 300
  }
  pwmValue = constrain(pwmValue, 0, 255);  // Ensure it's within PWM range
  currentBrightness = map(pwmValue, 0, 255, 0, 100);
  if (pwmValue != 0) {
    ledState = true;
    setIntensity(pwmValue);
    lastMotionTime = millis(); // Reset the timer on motion detection
    motionDetected = true; // Indicate motion detected
  } else {
    ledState = false;
  }
}
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");
  String message = "";
  for (int i = 0; i < length; i++) {
    message += (char)payload[i]; // Append each character to the message
  }
  Serial.println(message); // Print the complete message
  if (strcmp(topic, topic2) == 0) {
    message.trim(); // Remove any leading or trailing whitespace
    message.toLowerCase(); // Convert to lowercase for case-insensitive comparison
    if (message == "1") {
      Serial.println("This is turn on");
      ledState = true;
      turnOnCommand();
    } else if (message == "0") {
      Serial.println("This is turn off");
      ledState = false;
      turnOffCommand();
    }
    Serial.println(ledState);
  }
  if (strcmp(topic, topic3) == 0) {
    message.trim(); // Remove any leading or trailing whitespace
    message.toLowerCase(); // Convert to lowercase for case-insensitive comparison
    int value = message.toInt();
    currentBrightness = value;
    Serial.println(value);
    value = map(value, 0, 100, 0, 255);
    setIntensity(value);
  }
  if (strcmp(topic, topic4) == 0) {
    message.trim(); // Remove any leading or trailing whitespace
    message.toLowerCase(); // Convert to lowercase for case-insensitive comparison
    int value = message.toInt();
    Serial.println(value);
    motionDetected = true;
  }
}

void setIntensity(int percentage) {
  if (percentage != 0){
    analogWrite(ledPin,percentage); // Set the LED brightness
    ledState = true;
  } else {
    analogWrite(ledPin,percentage);
    ledState = false;
    motionDetected = false;
  }
}

void sendSensorStatus(bool status) {
  // status = true: sensor OK, false: sensor error
  String statusMsg = status ? "OK" : "ERROR";
  if (client.publish(topic_sensor_status, statusMsg.c_str())) {
    Serial.println("Sensor status sent: " + statusMsg);
  } else {
    Serial.println("Failed to send sensor status");
  }
}

void sendMotionSensorStatus(bool status) {
  String statusMsg = status ? "OK" : "ERROR";
  if (client.publish(topic_motion_sensor_status, statusMsg.c_str())) {
    Serial.println("Motion sensor status sent: " + statusMsg);
  } else {
    Serial.println("Failed to send motion sensor status");
  }
}

void sendData(float lux, bool ledState, int currentBrightness) {
  // Convert lux to a string and publish to the sensorData topic
  String luxMessage = String(lux);
  if (client.publish(topic, luxMessage.c_str())) {
    Serial.println("Sensor data sent: " + luxMessage);
  } else {
    Serial.println("Sensor data failed to send");
  }

  // Convert ledState to a string ("1" for true, "0" for false) and publish to the ledStateData topic
  String ledMessage = String(ledState ? 1 : 0);
  if (client.publish(topic1, ledMessage.c_str())) {
    Serial.println("LED state sent: " + String(ledState ? "True" : "False"));
  } else {
    Serial.println("LED state failed to send");
  }

  String brightnessMessage = String(currentBrightness);
  if (client.publish(topic4, brightnessMessage.c_str())) {
    Serial.println("Brightness sent: " + brightnessMessage + "%");
  } else {
    Serial.println("Brightness data failed to send");
  }
}

void motionHandler() {
  lastMotionDetectedTime = millis(); // Update last motion detected time
  motionSensorErrorReported = false; // Reset error report if motion detected

  if (!motionDetected) {
    float lux = readLightValue();
    if (lux < 0) {
      // Error value, set LED to safe mode
      return;
    }
    int pwmValue;
    if (!(!(WiFi.status() != WL_CONNECTED) && client.connected())) {
      pwmValue = 255;
    } else {
      if (lux < 100) {
        pwmValue = 255; // Maximum brightness
      } else if (lux > 300) {
        pwmValue = 0; // Turn off the LED
      } else {
        pwmValue = map(lux, 100, 300, 255, 0); // Map lux from 100 to 300
      }
      pwmValue = constrain(pwmValue, 0, 255);  // Ensure it's within PWM range
    }
    currentBrightness = map(pwmValue, 0, 255, 0, 100);
    if (pwmValue != 0) {
      ledState = true;
      setIntensity(pwmValue);
      lastMotionTime = millis(); // Reset the timer on motion detection
      motionDetected = true; // Indicate motion detected
    } else {
      ledState = false;
    }
    Serial.println("Motion detected");
    Serial.print("Light: ");
    Serial.print(lux);
    Serial.println(" lx");
    setIntensity(pwmValue);
  } else {
    lastMotionTime = millis(); // Reset the timer on motion detection
    Serial.println("Motion detected, reset timer!!!");
  }
}

void timeCheck() {
  // Check for timeout in the background
  if (motionDetected && (millis() - lastMotionTime >= countdownDuration)) {
    analogWrite(ledPin, 0); // Turn off LED
    ledState = false; // Toggle state
    motionDetected = false; // Reset motion flag
    currentBrightness = 0;
    Serial.println("LED turned off due to inactivity.");
  }
}

void checkMotionSensor() {
  unsigned long currentTime = millis();
  if ((currentTime - lastMotionDetectedTime) > motionSensorTimeout && !motionSensorErrorReported) {
    Serial.println("Warning: No motion detected for a long time. Motion sensor may be malfunctioning.");
    sendMotionSensorStatus(false); // Send error status
    motionSensorErrorReported = true; // Avoid repeated reports
  } else if ((currentTime - lastMotionDetectedTime) <= motionSensorTimeout) {
    // Sensor working again, send OK status
    sendMotionSensorStatus(true);
    motionSensorErrorReported = false;
  }
}

void reconnectMQTT() {
  while (!client.connected()) {
    Serial.println("Attempting MQTT connection...");
    if (client.connect("Nano33Client")) {
      Serial.println("Connected to MQTT");
      client.subscribe(topic2); // Subscribe topic2
      client.subscribe(topic3); // Subscribe topic3
    } else {
      Serial.print("Failed to connect to MQTT, rc=");
      Serial.print(client.state());
      delay(2000); // Check every 2 secs
    }
  }
}

void loop() {
  // Check wifi connection
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected. Attempting to reconnect...");
    connectToWiFi(); // Reconnect wifi function
  }

  // Check MQTT connection
  if (!client.connected()) {
    reconnectMQTT(); // Reconnect MQTT
  }

  client.loop(); // Maintain connection with MQTT
  timeCheck();   // Count down for inactivity
  checkMotionSensor(); // Check motion sensor status regularly
  delay(5000);  // Check every 5 secs
}
