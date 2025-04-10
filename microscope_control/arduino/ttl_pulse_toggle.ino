const int ttlPin = 7;  // Digital pin used for TTL output
char lastState = 'L';  // Assume LOW (0V) as default

void setup() {
  pinMode(ttlPin, OUTPUT);
  Serial.begin(9600);
  digitalWrite(ttlPin, LOW); // Initialize pin to LOW
}

void loop() {
  if (Serial.available() > 0) {
    char command = Serial.read();
    if (command == 'T') { // 'T' command toggles the state
      toggleTTL();
    } else if (command == 'H') {
      digitalWrite(ttlPin, HIGH);
      lastState = 'H';
      Serial.println("TTL HIGH");
    } else if (command == 'L') {
      digitalWrite(ttlPin, LOW);
      lastState = 'L';
      Serial.println("TTL LOW");
    }
  }
}

void toggleTTL() {
  if (lastState == 'H') {
    digitalWrite(ttlPin, LOW);
    lastState = 'L';
    Serial.println("Toggled to TTL LOW");
  } else {
    digitalWrite(ttlPin, HIGH);
    lastState = 'H';
    Serial.println("Toggled to TTL HIGH");
  }
}
