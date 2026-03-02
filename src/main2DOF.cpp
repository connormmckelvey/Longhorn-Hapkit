
//Hapkit 2-DOF
//Ross Neuman 2026
//Kinematics as defined in Campion, et al. 2006

#define ENCODER_OPTIMIZE_INTERRUPTS

#include <Encoder.h>
#include "haplink.h"

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

volatile hModes hapticMode = JOYSTICK;

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

//1ms loops -- NOTE: this is not currently true :(
float dt = .001;

// define filter "r" based on cutoff frequency
float fc = 30;                //cutoff frequency [Hz]
float r = exp(-2*M_PI*fc*dt); //filter constant

//Arm lengths
float a1 = 0.1;
float a2 = 0.128;
float a3 = 0.128;
float a4 = 0.1;
float a5 = 0.06;

//Terms used in forward kinematics calculation
float p2x, p2y, p4x, p4y, p2p4, p2ph, p3ph, phx, phy;

//Terms used in Jacobian calculation
float d, b, h, d1x2, d1y2, d5x4, d5y4, d1d, d1b, d1h, d5d, d5b, d5h, d1yh, d5yh, d1xh, d5xh, d1y3, d5y3, d1x3, d5x3;
float d1x4 = 0;
float d1y4 = 0;
float d5x2 = 0;
float d5y2 = 0;

//forces to render in the workspace (N)
float Ftot, Fx, Fy;

//Direction of force application
float dir;

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
float grid_res = 5;

float b_damping;

float k_wall;
float b_wall;

//Pi used for calculating periodic stuff
float pi = 3.14159;

void setup() {
  Serial.begin(115200);
  haplink.begin(Serial);
  haplink.registerParam(0, (void*)&hapticMode, HL_DataType::HL_UINT8);

  TCCR1A = (1 << COM1A1) | (1 << COM1B1); //clears OC1 on compare match when up-counting, sets on match when down-counting
  TCCR1B = (1 << WGM13) | (1 << CS10); //waveform generation mode 8 (phase/freq correct, ICR1 top), prescaler = 1
  ICR1 = 400; //ICR1 defines TOP in WGM8
  
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
  //analogWrite(pwm1,0);
  
  digitalWrite(mot2A, HIGH);
  digitalWrite(mot2B, LOW);
  //analogWrite(pwm2,0);

  //Initialize positions (should place end effector at center of workspace before powering up device)
  lastPos1 = 0;
  lastPos2 = 0;
  lastnX = 0;
  lastnY = 0; 
}

void loop() {
  
  //encoder positions 
  pos1 = enc1.read();
  pos2 = enc2.read();

  //arm 1 and 5 positions relative to home (rad)
  t1 = 0.7872-pos1/countsPerRad;
  t5 = 2.3544-pos2/countsPerRad;

  haplink.update(); //check for incoming serial packets to update parameters from the PC
  
  //get forward kinematics
  FK(t1,t5);
  Velocity();

    switch(hapticMode){
      //Zero/home
      //This just quits generating forces and resets encoders to zero-- put handle in middle of workspace and then go back to another mode
      case ZERO:
        Fx = 0;
        Fy = 0;
        enc1.write(0);
        enc2.write(0);
        break;

      //Joystick mode
      //snaps back to the center - dead zone in the middle and outside of 6cm from center
      case JOYSTICK:
        k_joy = 1.75;
        if (nX*nX+nY*nY > 0.005*0.005 && nX*nX+nY*nY < 0.06*0.06){
          dir = atan2(nY,nX);
          Fx = -k_joy*cos(dir);
          Fy = -k_joy*sin(dir);
        }
        else{
          Fx = 0;
          Fy = 0;
        }
        break;

      //Grid mode
      //Little ridges arranged in a grid pattern
      case GRID:
        k_bump = 2.3;
        grid_res = 5;
        Fx = 0;
        Fy = 0;
        if(abs(sin(20*grid_res*pi*nY))>0.9){
          Fy = k_bump*(-sin(40*grid_res*pi*nY));
        }
        else{
          Fy = 0;
        }
        if(abs(sin(20*grid_res*pi*nX))>0.9){
          Fx = k_bump*(-sin(40*grid_res*pi*nX));
        }
        else{
          Fx = 0;
        }
        break;

      //Concentric circles mode
      //circular ridges from the center
      case CIRCLES:
        k_bump = 2;
        grid_res = 5;
        bump_threshold = 0.3;
        Fx = 0;
        Fy = 0;
        if(abs(sin(20*grid_res*pi*sqrt(nX*nX+nY*nY)))>bump_threshold && sqrt(nX*nX+nY*nY) > 0.003){
          Ftot = k_bump*(-sin(40*grid_res*pi*sqrt(nX*nX+nY*nY)));
          dir = atan2(nY,nX);
          Fx = Ftot*cos(dir);
          Fy = Ftot*sin(dir);
        }
        else{
          Fx = 0;
          Fy = 0;
        }
        break;

      //Harp mode 
      //This was for my MIDI implementation to feel like "strumming"
      //(basically ridges in right half of workspace)
      case HARP:
        k_bump = 2;
        grid_res = 5;
        Fx = 0;
        Fy = 0;
        if(abs(sin(20*grid_res*pi*nY))>0.9 && nX < 0){
          Fy = k_bump*(-sin(40*grid_res*pi*nY));
        }
        else{
          Fy = 0;
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
          Fx = -k_wall*(nX - 0.03 * (nX>0 ? 1 : -1)) + -b_wall*vX;
        }
        if(abs(nY) > 0.025){
          Fy = -k_wall*(nY - 0.03 * (nY>0 ? 1 : -1)) + -b_wall*vY;
        }
        break;
      case JOYSTICK_DAMPED:
        k_joy = 3;
        b_damping = 5;
        if (nX*nX+nY*nY > 0.002*0.002 && nX*nX+nY*nY < 0.06*0.06){
          dir = atan2(nY,nX);
          Fx = -k_joy*cos(dir)-b_damping*vX;
          Fy = -k_joy*sin(dir)-b_damping*vY;
        }
        else{
          Fx = -b_damping*vX;
          Fy = -b_damping*vY;
        }
        break;
    }


  //Don't render any forces if you're outside the workspace(ish)
  if(abs(nY) > 0.06 || abs(nX) > 0.06){
    Fx = 0;
    Fy = 0;
  }

  //Convert forces to torques
  Jac();
  Torque();


  //Tell the motors what direction to turn
  if (tau1 < 0){
    digitalWrite(mot1A, LOW);
    digitalWrite(mot1B, HIGH);
  }
  else{
    digitalWrite(mot1A, HIGH);
    digitalWrite(mot1B, LOW);
  }
  
  if (tau2 < 0){
    digitalWrite(mot2A, LOW);
    digitalWrite(mot2B, HIGH);
  }
  else{
    digitalWrite(mot2A, HIGH);
    digitalWrite(mot2B, LOW);

  }

  //Compute duty cycles for tau1, tau2 (this is not even close to giving actual torques, it's leftover from an old project but I kind of like the scaling)
  duty1 = sqrt(abs(tau1)/.03);
  duty2 = sqrt(abs(tau2)/.03);

  //Limit commanded duty cycle to [0-255]
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
  //out2 = (int)(duty2*255);
  //analogWrite(pwm2,out2);
  out2 = (int)(duty2*400);
  OCR1B = out2;

  //Print stuff for debugging (runs faster without this)
  Serial.print(nX);
  Serial.print(" ");
  Serial.print(nY);
  Serial.println();
  
  //Update values for previous positions
  lastPos1 = pos1;
  lastPos2 = pos2;
  lastnX = nX;
  lastnY = nY;
  lastVx = vX;
  lastVy = vY;

}

//Forward kinematics
void FK(float theta1, float theta5){
  
  p2x = a1*cos(theta1);
  p2y = a1*sin(theta1);
  
  p4x = a4*cos(theta5)-a5;
  p4y = a4*sin(theta5);

  p2p4 = dist(p4x,p4y,p2x,p2y);
  
  p2ph = (a2*a2-a3*a3+p2p4*p2p4)/(2*p2p4);
  p3ph = sqrt(a2*a2-p2ph*p2ph);

  phx = p2x+(p2ph/p2p4)*(p4x-p2x);
  phy = p2y+(p2ph/p2p4)*(p4y-p2y);

  X = phx+(p3ph/p2p4)*(p4y-p2y);
  Y = phy-(p3ph/p2p4)*(p4x-p2x);

  //normalized workspace
  nX = X+.03;
  nY = Y-.15;
}

//Jacobian for the current position
void Jac(){
  d = dist(p2x,p2y,p4x,p4y);
  b = dist(p2x,p2y,phx,phy);
  h = dist(X,Y,phx,phy);
  
  d1x2 = -a1*sin(t1);
  d1y2 = a1*cos(t1);
  d5x4 = -a4*sin(t5);
  d5y4 = a4*cos(t5);
  
  d1d = ((p4x-p2x)*(d1x4-d1x2)+(p4y-p2y)*(d1y4-d1y2))/d;
  d5d = ((p4x-p2x)*(d5x4-d5x2)+(p4y-p2y)*(d5y4-d5y2))/d;
  
  d1b = d1d-(d1d*(a2*a2-a3*a3+d*d))/(2*d*d);
  d5b = d5d-(d5d*(a2*a2-a3*a3+d*d))/(2*d*d);
  
  d1h = -b*d1b/h;
  d5h = -b*d5b/h;
  
  d1yh = d1y2+(d1b*d-d1d*b)/(d*d)*(p4y-p2y)+b/d*(d1y4-d1y2);
  d5yh = d5y2+(d5b*d-d5d*b)/(d*d)*(p4y-p2y)+b/d*(d5y4-d5y2);
  
  d1xh = d1x2 + (d1b*d-d1d*b)/(d*d)*(p4x-p2x)+b/d*(d1x4-d1x2);
  d5xh = d5x2 + (d5b*d-d5d*b)/(d*d)*(p4x-p2x)+b/d*(d5x4-d5x2);
    
  d1y3 = d1yh-h/d*(d1x4-d1x2)-(d1h*d-d1d*h)/(d*d)*(p4x-p2x);
  d5y3 = d5yh-h/d*(d5x4-d5x2)-(d5h*d-d5d*h)/(d*d)*(p4x-p2x);
  
  d1x3 = d1xh+h/d*(d1y4-d1y2)+(d1h*d-d1d*h)/(d*d)*(p4y - p2y);
  d5x3 = d5xh+h/d*(d5y4-d5y2)+(d5h*d-d5d*h)/(d*d)*(p4y - p2y);
}

//torque to generate at motor pulley (tau = (J'*F)/gearing)
void Torque(){
  tau1 = (d1x3*Fx + d1y3*Fy)/15;
  tau2 = (d5x3*Fx + d5y3*Fy)/15;
}

void Velocity(){
  vX = r * lastVx + (1 - r) * (nX - lastnX) / dt;
  vY = r * lastVy + (1 - r) * (nY - lastnY) / dt;
}

//euclidean distance between two points (x1,y1) and (x2,y2)
float dist(float x1, float y1, float x2, float y2){
  distance = sqrt((x1-x2)*(x1-x2) + (y1-y2)*(y1-y2));
  return distance;
}
