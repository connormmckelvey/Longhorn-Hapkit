
//--------------------------------------------------------------------------
// Ann Majewicz Fey, University of Texas at Austin
// Last Modified: 08.27.21
// Code to test basic functionaility of the Longhorn Hapkit (w/ encoder)
//--------------------------------------------------------------------------

// INCLUDES
#define ENCODER_OPTIMIZE_INTERRUPTS
#include <TimerOne.h>  // This library manages the timing of the haptic loop 
#include <Encoder.h>   // This library manages the encoder read.
#include "haplink.h" // This library manages the serial communication between the Arduino and the PC.

// Parameters that define what environment to render
enum environment {VIRTUAL_WALL = 0, VIRTUAL_SPRING = 1, CONST_DAMPENER = 2, SIN_DAMPENER = 3, FISHROD_CAST = 4 };
volatile environment currentEnvironment = VIRTUAL_SPRING; // default environment

// Pin Declarations
const int PWMoutp = 4;
const int PWMoutn = 5;
const int PWMspeed = 9;

const int encoder0PinA = 2;
const int encoder0PinB = 3;

Encoder encoder(encoder0PinA,encoder0PinB);
Haplink haplink;

double encoderResolution = 48;
double pos = 0; 
double lastPos = 0; 
double lastVel = 0; 

// Kinematics variables
double xh = 0;           // position of the handle [m]
double vh = 0;           // velocity of the handle [m/s]
double lastXh = 0;       // prior handel position [m]
double lastVh = 0;       // prior velocity of the handel 
double lastLastVh = 0;   // second last velocity of the handel 
double theta_s = 0;      // Angle of the sector pulley in deg
double xh_prev;          // Distance of the handle at previous time step
double xh_prev2;
double dxh;              // Velocity of the handle
double dxh_prev;
double dxh_prev2;
double dxh_filt;         // Filtered velocity of the handle
double dxh_filt_prev;
double dxh_filt_prev2;

//Constants for velocity filtering
double ao = 2500;    //wn^2 (where wn=50)
double a1 = 100;     //2*zeta*wn (where zeta=1)
double T = 0.0006; //sample period [sec]
double A = 1/((2*ao*T*T)+2*a1*T+4);
double B = 4-2*a1*T+ao*T*T;
double C = 8-2*ao*T*T;
double D = ao*T*T;

// *******************************************
// UNCOMMENT THESE AND INCLUDE CORRECT NUMBERS
// *******************************************
double rh = 0.085;   // length of your handle[m] 
double rp = 0.005;  // radius of motor pulley[m] 
double rs = 0.075;  // radius of sector[m] 
// *******************************************

// Force output variables
double force = 0;           // force at the handle
double Tp = 0;              // torque of the motor pulley
double duty = 0;            // duty cylce (between 0 and 255)
unsigned int output = 0;    // output command to the motor

// Timing Variables: Initalize Timer and Set Haptic Loop
boolean hapticLoopFlagOut = false; 
boolean timeoutOccured = false; 
const unsigned long HAPTIC_PERIOD_US = 1000;

// *************** Parameter for haptic rendering *******************
// Parameters for virtual wall
double x_wall = 0.05;                   // Position of the virtual wall
volatile double k_wall = 800;                     // Maximum stiffness of the virtual wall

// Parameters for virtual spring
volatile double K_spring = 60;  // Spring stiffness [N/m]
// Parameters for linear damping
volatile double b_linear = 75;                   // Linear damping in N/m
// Parameters for fishing rod casting
#define READY -1
#define PULLING_BACK 0
#define THROWING_BAIT 1
double min_xh_for_casting = -0.9;      // minimum handle position for pulling back
double max_xh_for_casting = 0.0;        // maximum handle position for pulling back
double dxh_threshold_for_back = -0.002; // backward velocity threshold
double dxh_threshold_for_forward = 0.01; // forward velocity threshold to throw
double fishing_pullback_force = 30;     // N, resistance during pull back
double fishing_throwing_bait_force = -50; // N, assist force during forward throw
int8_t casting_status = READY;          // initial state



// --------------------------
// Haptic Loop
// --------------------------
  void hapticLoop()
  {

      // See if flag is out (couldn't finish before another call) 
      if(hapticLoopFlagOut)
      {
        timeoutOccured = true;
      }
      //*************************************************************
      //*** Section 1. Compute position and velocity using encoder (DO NOT CHANGE!!) ***  
      //*************************************************************
      pos = encoder.read();
     // double vel = (.80)*lastVel + (.20)*(pos - lastPos)/(.01);


        //*************************************************************
        //*** Section 2. Compute handle position in meters ************
        //*************************************************************

          // SOLUTION:
          // Define kinematic parameters you may need
           
          // Step 2.1: print updatedPos via serial monitor
          //*************************************************************
           //Serial.println(updatedPos);
           
          // Step 2.2: Compute the angle of the sector pulley (ts) in degrees based on updatedPos
         //*************************************************************
            double ts = (pos/encoderResolution)*360; // Find angle based on encoder position and encoder resolution 
       
         // Step 2.3: Compute the position of the handle based on ts
          //*************************************************************
            xh = rh*(ts*3.14159/180);       // arc length formula ( handle_pos = length_of_handle * (angle_of_sector_pulley->radians)
        
          // Step 2.4: print xh via serial monitor
          //*************************************************************
          // Serial.println(xh,5);
           
          // Step 2.5: compute handle velocity
          //*************************************************************
            
            // Calculate the velocity of the handle
            dxh = (double)(xh - xh_prev) / (HAPTIC_PERIOD_US * 1e-6);

             // Calculate the filtered velocity of the handle using an infinite impulse response filter
            //dxh_filt = .9*dxh + 0.1*dxh_prev; 
            
            // Calculate the filtered velocity of the handle using a second-order low pass filter (derived from anolog H(s)=ao/(s^2+a1s+ao))
            dxh_filt = A*(-B*dxh_filt_prev2 + C*dxh_filt_prev + D*(dxh + 2*dxh_prev + dxh_prev2));
              
            // Record the position
            xh_prev2 = xh_prev;
            xh_prev = xh;

            // Record the velocity
            dxh_prev2 = dxh_prev;
            dxh_prev = dxh;
            
            dxh_filt_prev2 = dxh_filt_prev;
            dxh_filt_prev = dxh_filt;
  
  
             vh = -(.95*.95)*lastLastVh + 2*.95*lastVh + (1-.95)*(1-.95)*(xh-lastXh)/.0001;  // filtered velocity (2nd-order filter)
             lastXh = xh;
             lastLastVh = lastVh;
            lastVh = vh;

        //*************************************************************
        //*** Section 3. Assign a motor output force in Newtons *******  
        //*************************************************************
 
            // Init force 
           // int force = 0;

            // ORIGINAL EXAMPLE
              //            double K = 12;   // spring stiffness 
              //    
              //           if(pos < 0)
              //          {
              //           // force = -K*pos; 
              //            force = 0;
              //          } else 
              //          {
              //            force = 0; 
              //          }
              
              // This is just a simple example of a haptic wall that only uses encoder position.
              // You will need to add the rest of the following cases. You will want to enable some way to select each case. 
              // Options for this are #DEFINE statements, swtich case statements (i.e., like a key press in serial monitor), or 
              // some other method. 
          
          // Virtual Wall 
        //*************************************************************
          // Forces algorithms
          //Serial.println(xh); 
          switch (currentEnvironment)
          {
          case VIRTUAL_WALL:
              if (xh > x_wall)
              {
                  force = -k_wall * (xh - x_wall) ; //+ -b_linear*(dxh_filt);
              }
              else
              {
                  force = 0;
              }
          break;

          //virtual spring
         //****************************************************************
          case VIRTUAL_SPRING:
            force = -K_spring*xh; 
          break;
          
          //const dampener
          //***************************************************************
          case CONST_DAMPENER:
            force = -b_linear*dxh;
          break;

          //const dampener
          //***************************************************************
          case SIN_DAMPENER:
            
          break;
          
          // fishing casting
          //***************************************************************
          case FISHROD_CAST:
            
          //were moving back in the cast
            if (xh > min_xh_for_casting and xh < max_xh_for_casting and dxh < dxh_threshold_for_back)
            {
              force = fishing_pullback_force;
              casting_status = PULLING_BACK;
            }
            else if (casting_status == PULLING_BACK and dxh > dxh_threshold_for_forward)
            {
              force = fishing_throwing_bait_force;
              casting_status = THROWING_BAIT;
            }
            else
            {
              casting_status = -1;
            }
            
          break;
          }
          

      //*************************************************************
      //*** Section 5. Force output (do not change) *****************
      //*************************************************************

        // Determine correct direction 
        //*************************************************************
        if(force < 0)
        {
        digitalWrite(PWMoutp, HIGH);
        digitalWrite(PWMoutn, LOW);
        } 
        if(force >0)
        {
         digitalWrite(PWMoutp, LOW);
        digitalWrite(PWMoutn, HIGH);
        } 

       //  if(force < 0)
       // {
       // digitalWrite(PWMoutp, HIGH);
       // digitalWrite(PWMoutn, LOW);
       // } else 
       // {
       //  digitalWrite(PWMoutp, LOW);
       // digitalWrite(PWMoutn, HIGH);
   //     } 
    
        // Limit torque to motor and write
        //*************************************************************
        if(force > 255)
        {
          force = 255; 
        }
        if(force < -255)
        {
          force = -255;
        }
          //Serial.println(force); // Could print this to troublshoot but don't leave it due to bogging down speed

        // Write out the motor speed.
        //*************************************************************    
        analogWrite(PWMspeed, abs(force)); //abs(force)
 
  // Update variables 
  //lastVel = vel;
  lastPos = pos; 

}


//--------------------------------------------------------------------------
// Initialize
//--------------------------------------------------------------------------
void setup()
{

 Serial.begin(115200); // Initialize serial communication for debugging (optional, but helpful for troubleshooting)
 haplink.begin(Serial); // Initialize serial communication with the PC through the Haplink library
 haplink.registerParam(0, (void*)&currentEnvironment, HL_DataType::HL_UINT8); // Register the current environment variable to be set from the PC. You can register other parameters here as well (e.g., stiffness of the wall, stiffness of the spring, damping coefficient, etc.)
 haplink.registerParam(1, (void*)&k_wall, HL_DataType::HL_DOUBLE);
 haplink.registerParam(2, (void*)&K_spring, HL_DataType::HL_DOUBLE);
 haplink.registerTelemetry(0, (void*)&xh, HL_DataType::HL_DOUBLE);
 haplink.registerTelemetry(1, (void*)&dxh_filt, HL_DataType::HL_DOUBLE);
  
 // Output Pins
 pinMode(PWMoutp, OUTPUT);
 pinMode(PWMoutn, OUTPUT);
 pinMode(PWMspeed, OUTPUT);

 // Haptic Loop Timer Initalization
   Timer1.initialize(); 
  const unsigned long period = HAPTIC_PERIOD_US; // [us]  10000 [us] - 1000 Hz 
  Timer1.attachInterrupt(hapticLoop, period); 

  // Init Position and Velocity
  lastPos = encoder.read();
  lastVel = 0;
  force = 0;

  // Initalize motor direction and set to 0 (no spin)
  digitalWrite(PWMoutp, HIGH);
  digitalWrite(PWMoutn, LOW);
  analogWrite(PWMspeed, 0);
  
}

//--------------------------------------------------------------------------
// Main Loop
//--------------------------------------------------------------------------

void loop()
{
  haplink.update(); // Update the Haplink library to process incoming serial data and send telemetry. You can call this as often as you want, but it should be called at least once every loop() to ensure proper communication with the PC.}
  haplink.sendTelemetry(0);
  haplink.sendTelemetry(1); 
}