//Hapkit 2-DOF
//Ross Neuman 2026
//Updated by Connor McKelvey 2026
//Kinematics as defined in Campion, et al. 2006

#define ENCODER_OPTIMIZE_INTERRUPTS

#include <Arduino.h>
#include <Encoder.h>
#include "haplink.h"

#ifndef ENABLE_DEBUG_SERIAL
#define ENABLE_DEBUG_SERIAL 0
#endif

enum hModes{
  ZERO,
  JOYSTICK,
  GRID,
  CIRCLES,
  HARP,
  DAMP,
  WALL,
  JOYSTICK_DAMPED
};

hModes hapticMode = JOYSTICK;

//Motor/encoder 1 pins
const int pwm1 = 9;
const int mot1A = 13;
const int mot1B = 12;
const int enc1A = 4;
const int enc1B = 5;

//Motor/encoder 2 pins
const int pwm2 = 10;
const int mot2A = 11;
const int mot2B = 8;
const int enc2A = 2;
const int enc2B = 3;

//Haplink object for serial communication with the PC
Haplink haplink;

//Set up encoders
Encoder enc1(enc1A,enc1B);
long pos1 = 0;
long lastPos1 = 0;

Encoder enc2(enc2A,enc2B);
long pos2 = 0;
long lastPos2 = 0;

//Convert encoder readings to angular displacement of arms
float countsPerRad = 114.5915; //encoder counts per radian at the arm (48cpr*15gearing*2pi^-1)

//angular displacement of arms
float t1, t5;

//End effector X and Y location (define 0,0 at motor 1 shaft per Campion et al 2005)
float X, Y;

//End effector location normalized to workspace (0,0)
float nX, nY, lastnX, lastnY, vX, vY, lastVx, lastVy;


// Loop timing is measured live each iteration (the old fixed dt=.003 assumption
// did not match the ~1.45ms actual loop time, which meant the velocity filter's
// real cutoff frequency didn't match its design value).
unsigned long lastLoopUs = 0;
float dt = 0.00145; // seed value only; overwritten every loop with a measured dt

// define filter "r" based on cutoff frequency; recomputed every loop from measured dt
float fc = 30;                //cutoff frequency [Hz]
float r = 0.0f;
float vel_scale_factor = 0.0f;

// Precomputed factors for high-speed arithmetic
float invCountsPerRad;
float a2_sq;
float cos_t1, sin_t1, cos_t5, sin_t5;

//Arm lengths
float a1 = 0.1;
float a2 = 0.128;
float a3 = 0.128;
float a4 = 0.1;
float a5 = 0.06;

//Terms used in forward kinematics calculation
float p2x, p2y, p4x, p4y, p2p4, p2ph, p3ph, phx, phy;

//Terms used in Jacobian calculation
float d, h, d1x2, d1y2, d5x4, d5y4;
float d1yh, d5yh, d1xh, d5xh, d1y3, d5y3, d1x3, d5x3;

//forces to render in the workspace (N)
float Ftot, Fx, Fy;

//Torques to command of the motors
float tau1, tau2;

//output of dist() function
float distance;

//PWM control of motors
float duty1, duty2;
int out1, out2;

//Spring constant of joystick mode
float k_joy;

//Intensity of bumps and grid resolution in grid mode
float k_bump, bump_threshold;
float grid_res = 5; // number of bumps/cycles across the workspace in GRID/CIRCLES/HARP modes

float b_damping;

float k_wall;
float b_wall;

//Forward declarations (allow calling functions before their definitions)
void FK(float theta1, float theta5);
void Jac();
void Torque();
void Velocity();
float dist(float x1, float y1, float x2, float y2);

void setup() {
  Serial.begin(115200);
  haplink.begin(Serial);
  haplink.registerParam(0, &hapticMode, HL_INT16);

  TCCR1A = (1 << COM1A1) | (1 << COM1B1); //clears OC1 on compare match when up-counting, sets on match when down-counting
  TCCR1B = (1 << WGM13) | (1 << CS10); //waveform generation mode 8 (phase/freq correct, ICR1 top), prescaler = 1
  ICR1 = 400; //ICR1 defines TOP in WGM8

  //non intrusive debugging pin
  pinMode(7, OUTPUT);
  digitalWrite(7, LOW);

  //Set all the motor control pins to outputs
  pinMode(pwm1, OUTPUT);
  pinMode(pwm2, OUTPUT);
  pinMode(mot2A, OUTPUT);
  pinMode(mot2B, OUTPUT);
  pinMode(mot1A, OUTPUT);
  pinMode(mot1B, OUTPUT);

  //Initialize motor directions and set speeds to 0
  digitalWrite(mot1A, HIGH);
  digitalWrite(mot1B, LOW);

  digitalWrite(mot2A, HIGH);
  digitalWrite(mot2B, LOW);

  //Initialize positions (should place end effector at center of workspace before powering up device)
  lastPos1 = 0;
  lastPos2 = 0;
  lastnX = 0;
  lastnY = 0;

  // Precompute constants that don't depend on dt
  invCountsPerRad = 1.0 / countsPerRad;
  a2_sq = a2 * a2;

  lastLoopUs = micros();
}

// takes ~1.6ms
void loop() {
  digitalWrite(7, HIGH); //debugging pin to measure loop time
  haplink.update(); //process incoming packets
  unsigned long loop_t0_us = micros();

  // Measure actual elapsed time since the previous iteration and rederive the
  // filter constants from it every loop, since loop time varies by hapticMode
  // (trig-heavy modes like GRID/CIRCLES/HARP take longer than JOYSTICK).
  unsigned long nowUs = loop_t0_us;
  unsigned long elapsedUs = nowUs - lastLoopUs;
  lastLoopUs = nowUs;
  if (elapsedUs > 0) {
    dt = elapsedUs * 1.0e-6f;
    r = exp(-2 * M_PI * fc * dt);
    vel_scale_factor = (1.0f - r) / dt;
  }

  //encoder positions
  pos1 = enc1.read();
  pos2 = enc2.read();

  //arm 1 and 5 positions relative to home (rad) - multiplication instead of division
  t1 = 0.7872 - pos1 * invCountsPerRad;
  t5 = 2.3544 - pos2 * invCountsPerRad;

  //get forward kinematics
  //FK takes 750us
  FK(t1,t5);
  Velocity();

  const float grid_coeff1 = 20.0 * grid_res * M_PI;

  switch(hapticMode){
    //Zero/home
    //This just quits generating forces and resets encoders to zero-- put handle in middle of workspace and then go back to another mode
    case ZERO:
      Fx = 0;
      Fy = 0;
      enc1.write(0);
      enc2.write(0);
      // Keep the "last" state in sync with the reset encoders so the next
      // mode transition doesn't see a spurious velocity spike from comparing
      // against stale lastnX/lastnY/lastPos values.
      lastPos1 = 0;
      lastPos2 = 0;
      lastnX = nX;
      lastnY = nY;
      lastVx = 0;
      lastVy = 0;
      break;

    //Joystick mode - snaps back to the center - completely trig-free
    case JOYSTICK:
      k_joy = 1.75;
      {
        float r_sq = nX*nX + nY*nY;
        if (r_sq > 0.005*0.005 && r_sq < 0.06*0.06){
          float r_dist = sqrt(r_sq);
          Fx = -k_joy * (nX / r_dist);
          Fy = -k_joy * (nY / r_dist);
        }
        else{
          Fx = 0;
          Fy = 0;
        }
      }
      break;

    //Grid mode - optimized trig identity to save 2 sin/cos calls
    case GRID:
      k_bump = 2.3;
      Fx = 0;
      Fy = 0;
      {
        float sin_y = sin(grid_coeff1 * nY);
        if (abs(sin_y) > 0.9) {
          float cos_y = cos(grid_coeff1 * nY);
          Fy = -2.0 * k_bump * sin_y * cos_y;
        } else {
          Fy = 0;
        }

        float sin_x = sin(grid_coeff1 * nX);
        if (abs(sin_x) > 0.9) {
          float cos_x = cos(grid_coeff1 * nX);
          Fx = -2.0 * k_bump * sin_x * cos_x;
        } else {
          Fx = 0;
        }
      }
      break;

    //Concentric circles mode - optimized to avoid duplicate sqrt, atan2, and multiple trig calls
    case CIRCLES:
      k_bump = 2;
      bump_threshold = 0.3;
      Fx = 0;
      Fy = 0;
      {
        float r_dist = sqrt(nX*nX + nY*nY);
        if (r_dist > 0.003) {
          float sin_val = sin(grid_coeff1 * r_dist);
          if (abs(sin_val) > bump_threshold) {
            float cos_val = cos(grid_coeff1 * r_dist);
            Ftot = -2.0 * k_bump * sin_val * cos_val;
            Fx = Ftot * (nX / r_dist);
            Fy = Ftot * (nY / r_dist);
          }
        }
      }
      break;

    //Harp mode - optimized trig
    case HARP:
      k_bump = 2;
      Fx = 0;
      Fy = 0;
      if (nX < 0) {
        float sin_y = sin(grid_coeff1 * nY);
        if (abs(sin_y) > 0.9) {
          float cos_y = cos(grid_coeff1 * nY);
          Fy = -2.0 * k_bump * sin_y * cos_y;
        }
      }
      break;

    //Damping
    case DAMP:
      b_damping = 5;
      Fx = -vX*b_damping;
      Fy = -vY*b_damping;
      break;

    //walls in a square with 5cm sides
    case WALL:
      k_wall = 500;
      b_wall = 2;
      Fx = 0;
      Fy = 0;
      if(abs(nX) > 0.025){
        Fx = -k_wall*(nX - 0.03 * (nX>0 ? 1 : -1)) - b_wall*vX;
      }
      if(abs(nY) > 0.025){
        Fy = -k_wall*(nY - 0.03 * (nY>0 ? 1 : -1)) - b_wall*vY;
      }
      break;

    case JOYSTICK_DAMPED:
      k_joy = 3;
      b_damping = 5;
      {
        float r_sq = nX*nX + nY*nY;
        if (r_sq > 0.002*0.002 && r_sq < 0.06*0.06){
          float r_dist = sqrt(r_sq);
          Fx = -k_joy * (nX / r_dist) - b_damping * vX;
          Fy = -k_joy * (nY / r_dist) - b_damping * vY;
        }
        else{
          Fx = -b_damping * vX;
          Fy = -b_damping * vY;
        }
      }
      break;
  }

  //Don't render any forces if you're outside the workspace(ish)
  if(abs(nY) > 0.08 || abs(nX) > 0.08){
    Fx = 0;
    Fy = 0;
  }

  //Convert forces to torques - extremely optimized to avoid 3 sqrt and 4 trig calls
  //490us
  Jac();
  Torque();

  //Tell the motors what direction to turn - direct port writes instead of 4 digitalWrites
  // mot1A (Pin 13) = PB5, mot1B (Pin 12) = PB4
  if (tau1 < 0){
    PORTB &= ~(1 << 5); // LOW
    PORTB |= (1 << 4);  // HIGH
  }
  else{
    PORTB |= (1 << 5);  // HIGH
    PORTB &= ~(1 << 4); // LOW
  }

  // mot2A (Pin 11) = PB3, mot2B (Pin 8) = PB0
  if (tau2 < 0){
    PORTB &= ~(1 << 3); // LOW
    PORTB |= (1 << 0);  // HIGH
  }
  else{
    PORTB |= (1 << 3);  // HIGH
    PORTB &= ~(1 << 0); // LOW
  }

  //Compute duty cycles for tau1, tau2
  duty1 = sqrt(abs(tau1)/.03);
  duty2 = sqrt(abs(tau2)/.03);

  //Limit commanded duty cycle to [0-1]
  if (duty1 > 1){
    duty1 = 1;
  }
  else if (duty1 < 0){
    duty1 = 0;
  }
  out1 = (int)(duty1*400);
  OCR1A = out1;

  if (duty2 > 1){
    duty2 = 1;
  }
  else if (duty2 < 0){
    duty2 = 0;
  }
  out2 = (int)(duty2*400);
  OCR1B = out2;

  //Update values for previous positions
  lastPos1 = pos1;
  lastPos2 = pos2;
  lastnX = nX;
  lastnY = nY;
  lastVx = vX;
  lastVy = vY;

  // Loop execution time in microseconds (not including this print itself)
  static uint16_t printCounter = 0;
  const uint16_t PRINT_EVERY_N_LOOPS = 100;
  if (++printCounter >= PRINT_EVERY_N_LOOPS) {
    printCounter = 0;
  #if ENABLE_DEBUG_SERIAL
    Serial.println(micros() - loop_t0_us);
    Serial.print("x: ");
    Serial.print(nX);
    Serial.print(" y: ");
    Serial.println(nY);
  #endif
  }
  digitalWrite(7, LOW); //debugging pin to measure loop time
}

//Forward kinematics
void FK(float theta1, float theta5){
  cos_t1 = cos(theta1);
  sin_t1 = sin(theta1);
  cos_t5 = cos(theta5);
  sin_t5 = sin(theta5);

  p2x = a1*cos_t1;
  p2y = a1*sin_t1;

  p4x = a4*cos_t5-a5;
  p4y = a4*sin_t5;

  p2p4 = dist(p4x,p4y,p2x,p2y);

  // Since a2 == a3 (0.128m), (a2*a2 - a3*a3) = 0.
  // This simplifies p2ph = p2p4 / 2
  p2ph = 0.5 * p2p4;
  p3ph = sqrt(a2_sq-p2ph*p2ph);

  // Midpoint calculation for phx, phy (since a2 == a3)
  phx = 0.5 * (p2x + p4x);
  phy = 0.5 * (p2y + p4y);

  float p3ph_over_p2p4 = p3ph / p2p4;
  X = phx+p3ph_over_p2p4*(p4y-p2y);
  Y = phy-p3ph_over_p2p4*(p4x-p2x);

  //normalized workspace
  nX = X+.03;
  nY = Y-.15;
}

//Jacobian for the current position - highly optimized using robotic linkage symmetry
void Jac(){
  // b, d, h distances are already known from geometry in FK!
  // b = p2ph (which is 0.5 * d), d = p2p4, h = p3ph.
  d = p2p4;
  h = p3ph;

  // Reuse sines and cosines already calculated in FK()
  d1x2 = -a1*sin_t1;
  d1y2 = a1*cos_t1;
  d5x4 = -a4*sin_t5;
  d5y4 = a4*cos_t5;

  float inv_d = 1.0 / d;
  float h_over_d = h * inv_d;

  float diff_x = p4x - p2x;
  float diff_y = p4y - p2y;

  // Since d1x4, d1y4, d5x2, d5y2 are always 0, those terms drop out below.
  float d1d = (diff_x * (-d1x2) + diff_y * (-d1y2)) * inv_d;
  float d5d = (diff_x * d5x4 + diff_y * d5y4) * inv_d;

  // Since a2 == a3, d1b = 0.5 * d1d, and d5b = 0.5 * d5d.
  // We can precompute the factor (a2^2 + 0.25*d^2) / (h * d^2)
  float factor = (a2_sq + 0.25 * d * d) / (h * d * d);
  float coeff_h_1 = -d1d * factor;
  float coeff_h_5 = -d5d * factor;

  // Midpoint sensitivity:
  d1yh = 0.5 * d1y2;
  d5yh = 0.5 * d5y4;
  d1xh = 0.5 * d1x2;
  d5xh = 0.5 * d5x4;

  d1y3 = d1yh + h_over_d * d1x2 - coeff_h_1 * diff_x;
  d5y3 = d5yh - h_over_d * d5x4 - coeff_h_5 * diff_x;

  d1x3 = d1xh - h_over_d * d1y2 + coeff_h_1 * diff_y;
  d5x3 = d5xh + h_over_d * d5y4 + coeff_h_5 * diff_y;
}

//torque to generate at motor pulley (tau = (J'*F)/gearing)
void Torque(){
  tau1 = (d1x3*Fx + d1y3*Fy)/15;
  tau2 = (d5x3*Fx + d5y3*Fy)/15;
}

void Velocity(){
  vX = r * lastVx + vel_scale_factor * (nX - lastnX);
  vY = r * lastVy + vel_scale_factor * (nY - lastnY);
}

//euclidean distance between two points (x1,y1) and (x2,y2)
float dist(float x1, float y1, float x2, float y2){
  float dx = x1 - x2;
  float dy = y1 - y2;
  distance = sqrt(dx*dx + dy*dy);
  return distance;
}