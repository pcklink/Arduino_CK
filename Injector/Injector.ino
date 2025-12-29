// Control a stepper motor with DRV8825 stepper motor driver, 
// AccelStepper library and Arduino. Setup for injector.
// c.klink@nin.knaw.nl

// Step Resolution (full 200/revolution)
// J1     J2     J3         S
// Low	  Low	 Low	      Full step
// High	  Low	 Low	      1/2 step
// Low	  High	 Low	      1/4 step
// High	  High	 Low	      1/8 step
// Low	  Low	 High	      1/16 step
// High	  Low	 High	      1/32 step
// Low	  High	 High	      1/32 step
// High	  High	 High	      1/32 step
float StepResolution = 1;
float StepsPerRevolution = 200/StepResolution;
float DistPerRev = 0.8; // mm
float DistPerStep = DistPerRev/StepsPerRevolution;

// Include the AccelStepper library:
#include "AccelStepper.h"

// Define stepper motor connections and motor interface type. 
// Motor interface type must be set to 1 when using a driver
#define dirPin 2
#define stepPin 3
#define enablePin 4
// Microstepping pins
#define m0Pin 5
#define m1Pin 6
#define m2Pin 7

// Create a new instance of the AccelStepper class:
AccelStepper stepper = AccelStepper(AccelStepper::DRIVER, stepPin, dirPin);

// variables to get from a gui
String inputString = "";      // a String to hold incoming data
bool stringComplete = false;  // whether the string is complete

// control variables
float RotSpeed = 400;         // Rotation speed (steps/s)
float JogSpeed = 500;         // Jog speed in steps/s
int Direction = 1;            // Rotation direction 1 or 2
float Distance = 0;           // Distance to move (mm)
int JogDistance;              // Jog distance in steps
float DG = 1;                 // Direction gain to allow changing direction
int msFactor = 1;             // Microstepping
int Acceleration = 400;       // Acceleration step/s/s
int Position = 0;             // Current position
int PosInstr = 0;             // Position instructor
int runvar = 0;               // Variable to allow serial triggering


bool Moving = false;
unsigned long MoveStarted;

bool verbose = false; // verbosity

void setup() {
  // Set the maximum speed in steps per second:
  stepper.setMaxSpeed(1000);
  // Set control pins
  pinMode(stepPin, OUTPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(m0Pin, OUTPUT);
  pinMode(m1Pin, OUTPUT);
  pinMode(m2Pin, OUTPUT);

  if (Direction == 1) {
    digitalWrite(dirPin, HIGH);
  }
  // initialize serial:
  Serial.begin(9600);
}

void setmicrostepping(int msFactor) {
  switch (msFactor) {
    case 1:
      digitalwrite(m0Pin,LOW);
      digitalwrite(m1Pin,LOW);
      digitalwrite(m2Pin,LOW);
      break;
    case 2:
      digitalwrite(m0Pin,HIGH);
      digitalwrite(m1Pin,LOW);
      digitalwrite(m2Pin,LOW);
      break;
    case 4:
      digitalwrite(m0Pin,LOW);
      digitalwrite(m1Pin,HIGH);
      digitalwrite(m2Pin,LOW);
      break;
    case 8:
      digitalwrite(m0Pin,HIGH);
      digitalwrite(m1Pin,HIGH);
      digitalwrite(m2Pin,LOW);
      break;
    case 16:
      digitalwrite(m0Pin,LOW);
      digitalwrite(m1Pin,LOW);
      digitalwrite(m2Pin,HIGH);
      break;
    case 32:
      digitalwrite(m0Pin,HIGH);
      digitalwrite(m1Pin,LOW);
      digitalwrite(m2Pin,HIGH);
      break;
    default:
      digitalwrite(m0Pin,LOW);
      digitalwrite(m1Pin,LOW);
      digitalwrite(m2Pin,LOW);
      break;
  }
}

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
  // Set distance in mm ['D']
  // ====================================
  if (inputString.startsWith("D")) {
    inputString.setCharAt(0, '0');
    float DistanceMM = inputString.toFloat();
    int DistanceSTEPS = 

    if (verbose){
      Serial.print("Distance to move = ");
      Serial.println(DistanceMM);
    }
  }    

  // ====================================
  // Set jog distance in steps ['J']
  // ====================================
  if (inputString.startsWith("J")) {
    inputString.setCharAt(0, '0');
    float JogDistance = inputString.toFloat();

    if (verbose){
      Serial.print("Jog distance = ");
      Serial.println(JogDistance);
    }
  }    

  // ====================================
  // Set direction ['d']
  // ====================================
  if (inputString.startsWith("d")) {
    inputString.setCharAt(0, '0');
    Direction = inputString.toInt();
    if (verbose) {
      Serial.print("Rotation direction = ");
      Serial.println(Direction);
    }
  }  

  // ====================================
  // Set speed mm/s ['S']
  // ====================================
  if (inputString.startsWith("S")) {
    inputString.setCharAt(0, '0');
    Speed = inputString.toInt();
    Speed
    if (verbose){
      Serial.print("Speed = ");
      Serial.println(abs(Speed));
    }
  } 

  // ====================================
  // Set jog speed mm/s ['s']
  // ====================================
  if (inputString.startsWith("s")) {
    inputString.setCharAt(0, '0');
    JogSpeed = inputString.toInt();
    JogSpeed
    if (verbose){
      Serial.print("Jog Speed = ");
      Serial.println(abs(JogSpeed));
    }
  } 

  // ====================================
  // Set acceleration ['A']
  // ====================================
  if (inputString.startsWith("A")) {
    inputString.setCharAt(0, '0');
    Acceleration = inputString.toInt();
    if (verbose){
      Serial.print("Acceleration = ");
      Serial.println(abs(Acceleration));
    }
  }
  
  // ====================================
  // Set current position ['P']
  // ====================================
  if (inputString.startsWith("P")) {
    inputString.setCharAt(0, '0');
    PosInstr = inputString.toInt();
    if (PosInstr == 0) {
      // set current position to zero

      if (verbose){
        Serial.print("Position set to zero ");
        Serial.println(abs(Position));
      }
    }
    else if (Position == 0) {
      // go to current zero

      if (verbose){
        Serial.print("Moved to current zero ");
        Serial.println(abs(Position));
      }
    } 
  } 

  // ====================================
  // Set microstepping ['M']
  // ====================================
  if (inputString.startsWith("M")) {
    inputString.setCharAt(0, '0');
    msFactor = inputString.toInt();
    if (verbose){
      Serial.print("Microstepping = 1/");
      Serial.println(msFactor);
    }
    setmicrostepping(msFactor);
  } 

  // ====================================
  // Set running boolean PLAN ['R']
  // ====================================
  if (inputString.startsWith("R")) {
    inputString.setCharAt(0, '0');
    runvar = inputString.toInt();
    
    if (runvar == 1) {
      Moving = true;
      MoveStarted = millis();

      if (verbose){
        Serial.println("Running");
      }
    }
    else if (runvar == 0) {
      Moving = false;
      if (verbose){
        Serial.println("Stopping");
      }
    }
  } 

  // ====================================
  // Set running boolean JOG ['r']
  // ====================================
  if (inputString.startsWith("r")) {
    inputString.setCharAt(0, '0');
    jogvar = inputString.toInt();

    if (jogvar > 1) {
      Jogging = true;
      // Jog
      if (jogvar==1) {
        //UP

      }
      else if (jogvar==2) {
        // DOWN
        
      }


    }

    if (verbose){
      Serial.println("Jogging");
    }
  } 
}


void loop() {
  
  
  
  
  
  
  
  
  
  
  // Set the speed in steps per second:
  stepper.setSpeed(RotSpeed);

  if (ManOn) {
    StartMan = millis();
    
    while ((millis() - StartMan) < (ManDur)) {
      stepper.runSpeed();
    }    

    ManOn = false;
    delay(ManRefract);
  }

  if (ContOn) {
    stepper.runSpeed();
    if ((millis() - ContStarted) >= (ContDur)) {
      ContOn = false;
    }
  }
}
