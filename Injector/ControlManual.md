# Controlling the motor with AccelStepper library

Define stepper motor connections and motor interface type. 
- **Direction**: D-2
- **Step**: D-3
- **EnablePin**: D-4

Microstepping pins
- **M0**: D-5
- **M1**: D-6
- **M2**: D-7

Variables to get from a gui or serial monitor that need to be initialized:
- **RotSpeed** = 400;
  - Rotation speed (steps/s)
- **JogSpeed** = 500;
  - Jog speed in steps/s
- **Direction** = 1;
  - Rotation direction 1 or 2
- **Distance** = 0;
  - Distance to move (mm)
- **JogDistance**; 
  - Jog distance in steps
- **DG** = 1;
  - Direction gain to allow changing direction
- **msFactor** = 1;
  - Microstepping
- **Acceleration** = 400;
  - Acceleration step/s/s
- **Position** = 0;
  - Current position
- **PosInstr** = 0;
  - Position instructor
- **runvar** = 0;
  - Variable to allow serial triggering
- **verbose** = false;
  - verbosity

## Command strings

**Dxx** : distance in mm
Sets `DistanceMM` which should be converted to `DistanceSTEPS`
  
**Jxx** : jog distance in steps
Sets `JogDistance`

**dxx** : direction
Sets `Direction` 1/2

**Sxx** : speed mm/s 
Sets `Speed`

**sxx** : jog speed mm/s 
Sets `JogSpeed`

**Axx** : acceleration
Sets `Acceleration`

**Pxx** : current position
Sets `PosInstr`

**Mxx** : microstepping
Sets `msFactor`

**Rx** : running boolean PLAN
Sets `runvar`

**rx** : running boolean JOG
Sets `jogvar`

## Calculations needed
