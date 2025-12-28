// Control a stepper motor with A4988 stepper motor driver, 
// AccelStepper library and Arduino. Setup for peristaltic pump
// c.klink@nin.knaw.nl

// Step Resolution (full 200/revolution)
// J1     J2     J3 
// Low	  Low	   Low	      Full step
// High	  Low	   Low	      1/2 step
// Low	  High	 Low	      1/4 step
// High	  High	 Low	      1/8 step
// Low	  Low	   High	      1/16 step
// High	  Low	   High	      1/32 step
// Low	  High	 High	      1/32 step
// High	  High	 High	      1/32 step

// Include the AccelStepper library:
#include "AccelStepper.h"

// Define stepper motor connections and motor interface type. 
// Motor interface type must be set to 1 when using a driver
#define dirPin 2      // allows for direction comntrol (handled by driver)
#define stepPin 3     // sends the stepping commands
#define enablePin 12  // allows switching motor off
// Create a new instance of the AccelStepper class:
AccelStepper stepper = AccelStepper(AccelStepper::DRIVER, stepPin, dirPin);

// triggers and buttons
#define ttlPin 5              // BNC or on/off switch based stepping
#define manPin 7              // Manual button based stepping

// variables to get from a gui
String inputString = "";      // a String to hold incoming data
bool stringComplete = false;  // whether the string is complete

// control variables
int ManDur = 500;             // Manual run duration (ms)
int ManRefract = 500;         // Refractory period after manual drive
bool ManOn = false;           // Manual run for limited time
unsigned long StartMan;       // Keep track of starting moment

float RotSpeed = 600;         // Rotation speed (steps/s)
int Direction = 1;            // Rotation direction 1 or 2
float DG = 1;                 // Direction gain to allow changing direction

int ContDur = 5000;           // Continuous running duration (if triggered over serial)
bool ContOn = false;          // Continuous run for limited time
unsigned long  ContStarted;   // Continuous starting moment
int runvar = 0;               // Variable to allow serial triggering

bool verbose = false;         // verbosity

// == SETUP ==========
void serialEventRun(void) {
  if (Serial.available()) serialEvent();
}

void setup() {
  // Set the maximum speed in steps per second:
  stepper.setMaxSpeed(1000);
  // Set control pins
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(ttlPin, INPUT_PULLUP);
  pinMode(manPin, INPUT_PULLUP);

  digitalWrite(enablePin, LOW); // Enable motor 

  // initialize serial:
  Serial.begin(9600);

  float DirSpeed = DG*RotSpeed;
  stepper.setSpeed(DirSpeed);
  if (verbose) {
    Serial.print("Speed = ");
    Serial.println(DirSpeed);
  }
}

// == COMMUNICATION ==========
// Catch incoming commands
void serialEvent() {
  while (Serial.available()) {
    // get the new byte:
    char inChar = (char)Serial.read();
    // add it to the inputString:
    inputString += inChar;
    // if the incoming character is a carriage return
    // set a flag so the main loop can use it:
    if (inChar == '\r') {
      stringComplete = true;
      interpretCommand(); // Handle the requested command
      inputString = "";
    }
  }
}

// Interpret the received commands
void interpretCommand() {
  // Serial.println(inputString); // debugging
  
  // ====================================
  // Set manual duration ['m']
  // ====================================
  if (inputString.startsWith("m")) {
    inputString.setCharAt(0, '0');
    ManDur = inputString.toInt();
    if (verbose){
      Serial.print("Manual duration = ");
      Serial.println(abs(ManDur));
    }
  }     

  // ====================================
  // Set continuous duration ['c']
  // ====================================
  if (inputString.startsWith("c")) {
    inputString.setCharAt(0, '0');
    ContDur = inputString.toInt();
    if (verbose){
      Serial.print("Continuous duration = ");
      Serial.println(abs(ContDur));
    }
  }  

  // ====================================
  // Set running continuous ['r']
  // ====================================
  if (inputString.startsWith("r")) {
    inputString.setCharAt(0, '0');
    runvar = inputString.toInt();
    
    if (runvar == 1) {
      ContOn = true;
      ContStarted = millis();
    }
    
    if (runvar == 0) {
      ContOn = false;
    }
  } 

  // ====================================
  // Set speed ['s']
  // ====================================
  if (inputString.startsWith("s")) {
    inputString.setCharAt(0, '0');
    RotSpeed = inputString.toFloat();
    float DirSpeed = DG*RotSpeed;
    stepper.setSpeed(DirSpeed);
    if (verbose) {
      Serial.print("Speed = ");
      Serial.println(DirSpeed);
    }
  }     

  // ====================================
  // Set direction ['d']
  // ====================================
  if (inputString.startsWith("d")) {
    inputString.setCharAt(0, '0');
    Direction = inputString.toInt();
        
    if (Direction == 1) {
      DG = 1;
    }
    if (Direction == 2) {
      DG = -1;
    }

    float DirSpeed = DG*RotSpeed;
    stepper.setSpeed(DirSpeed);
    if (verbose) {
      Serial.print("Speed = ");
      Serial.println(DirSpeed);
    }
  }    
}

// == RUN LOOP ==========
void loop() {
  // check ttlPin
  bool ttlPinStatus = digitalRead(ttlPin);
  if (ttlPinStatus==LOW) {
    digitalWrite(enablePin, LOW); // enable motor 
    stepper.runSpeed();
  }
  else {
    digitalWrite(enablePin, HIGH); // disable motor 
  }

  // check manPin
  bool manPinStatus = digitalRead(manPin);
  if (manPinStatus==LOW) {
    ManOn = true;
  }
  else {
    ManOn = false;
  }

  if (ManOn) {
    digitalWrite(enablePin, LOW); // enable motor 
    StartMan = millis();
    while ((millis() - StartMan) < (ManDur)) {
      stepper.runSpeed();
    }    

    ManOn = false;
    digitalWrite(enablePin, HIGH); // disable motor 
    delay(ManRefract);
  }

  if (ContOn) {
    digitalWrite(enablePin, LOW); // enable motor 
    stepper.runSpeed();
    if ((millis() - ContStarted) >= (ContDur)) {
      ContOn = false;
      digitalWrite(enablePin, HIGH); // disable motor 
    }
  }
}