const int ttlPin = 7;  // Choose a digital pin for TTL output

void setup() {
    pinMode(ttlPin, OUTPUT);
    Serial.begin(9600);  // Start serial communication
}

void loop() {
    if (Serial.available() > 0) {
        char command = Serial.read();  // Read incoming command
        if (command == 'H') {
            digitalWrite(ttlPin, HIGH);  // Send 5V TTL
            Serial.println("TTL HIGH");
        } else if (command == 'L') {
            digitalWrite(ttlPin, LOW);   // Send 0V TTL
            Serial.println("TTL LOW");
        }
    }
}