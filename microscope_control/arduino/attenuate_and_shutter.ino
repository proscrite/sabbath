// ----- Pin Definitions -----
const int ttlPin = 7;      // Digital pin for TTL output (first snippet)
char lastState = 'L';      // Assume LOW (0V) as default for TTL

const int stepPin = 5;     // Step motor step pin (second snippet)
const int dirPin = 2;      // Step motor direction pin
const int enPin  = 8;      // Step motor enable pin

// Other constants:
int stepsPerRevolution = 1600;  // Not directly used now, but can be your reference
int stepDelay = 500;            // Microseconds delay for each step pulse

// ----- Setup -----
void setup() {
  // Set up TTL pin
  pinMode(ttlPin, OUTPUT);
  digitalWrite(ttlPin, LOW);
  
  // Set up stepper motor pins
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(enPin, OUTPUT);
  digitalWrite(enPin, LOW);    // Enable the motor driver
  
  // Initialize serial communication:
  Serial.begin(9600);
  Serial.println("Arduino ready.");
}

// ----- Main Loop -----
void loop() {
  // Check if data is available on the serial port:
  if (Serial.available() > 0) {
    // Peek at the next byte to decide if it's a letter or a number:
    char nextChar = Serial.peek();
    
    // If it's an alphabetic character, process TTL commands:
    if (isAlpha(nextChar)) {
      char command = Serial.read();  // Read the command character
      
      if (command == 'T') {
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
    // Otherwise, assume the input is numeric (steps for motor movement)
    else {
      // Read an integer value from the serial port.
      int maxSteps = Serial.parseInt();
      
      // If a valid number is received (greater than zero), move the motor:
      if (maxSteps != 0) {
        Serial.print("Moving motor for ");
        Serial.print(maxSteps);
        Serial.println(" steps.");
        moveMotor(maxSteps);
      }
    }
  }
  // A small delay can help avoid busy looping.
  delay(10);
}

// ----- Function Definitions -----

// Function to toggle the TTL output on ttlPin:
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

// Function to move the motor for a given number of steps:
void moveMotor(int steps) {
    String inputString = Serial.readStringUntil('\n');
  inputString.trim(); // Remove any leading/trailing whitespace (like carriage returns)
  
  // Debug: print the raw string received
  Serial.print("Received string: '");
  Serial.print(inputString);
  Serial.println("'");
  
  // Convert the string to an integer (this supports negative numbers)
  int stepsInput = inputString.toInt();
  
  // Debug: print the received value to the Serial Monitor.
  Serial.print("Received steps: ");
  Serial.println(stepsInput);
  
  // Determine the direction from the sign of steps:
  if (steps > 0) {
    digitalWrite(dirPin, HIGH);
    Serial.println("Positive number of steps. Normal spin direction.");

  } else {
    digitalWrite(dirPin, LOW);
    Serial.println("Negative number of steps. Reverse spin direction.");
    steps = -steps;  // Use the absolute value for the number of steps.
  }
  delay(10); // brief delay for stabilization
  
  digitalWrite(enPin, LOW);   // Assumes active-low enable
  delay(10); // brief delay for stabilization
  
  
  for (int i = 0; i < steps; i++) {
    digitalWrite(stepPin, HIGH);
    delayMicroseconds(stepDelay);
    digitalWrite(stepPin, LOW);
    delayMicroseconds(stepDelay);
  }
  // Disable the driver outputs to prevent current circulation:
  digitalWrite(enPin, HIGH);  // Disable motor outputs

  Serial.println("Motor movement complete.");
}
