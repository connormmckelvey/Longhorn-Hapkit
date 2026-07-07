//IF YOU USE THIS CODE, MAKE SURE THE PWMout WIRE IS MOVED TO PIN 9
//Write all serial messages in loop(), do not do serial communication in ISR
//Hapkit basic environments code
//Base: Ann Majewicz Fey and Ross Neuman 2/13/26

#include <Encoder.h>
#include <math.h>
#define ENCODER_OPTIMIZE_INTERRUPTS

// Pin Declarations
const int MotIn1 = 4;   //motor login pin 1
const int MotIn2 = 5;   //motor logic pin 2
const int PWMout = 9;   //PWM signal to control voltage to motor (pins 9 and 10 are on timer1 (16bit))

const int encPinA = 3;  //encoder output "A"
const int encPinB = 12;  //encoder output "B"

Encoder encoder(encPinB, encPinA);  //the encoder library uses the pulses from the two encoder outputs to get one 48 CPR angular positon

float encoderResolution = 48;  //encoder has 48 counts per revolution (CPR)
float pos = 0; //encoder position in ticks (initialized at zero)


// Change handle_length to reflect the handle you printed!
float handle_length = 0.085;  // length of your handle[m]
float pulley_radius = 0.005;  // radius of motor pulley[m]
float sector_radius = 0.075;  // radius of sector[m]

// Kinematics variables
float handle_pos = 0;      // position of the handle [we will calculate it in cm in code below]
float handle_pos_prev = 0; // previous handle position

float pulley_angle;     // motor pulley angle (radians)
float sector_angle;          // sector angle (radians)

// velocity using 1st-order low-pass filter
float handle_vel = 0;         // handle velocity
float handle_vel_prev = 0;    // previous velocity

float dt = 0.001;  // time steps of 1ms (1kHz control loop)

// define "r" based on cutoff frequency
float cutoff_frequency = 40;                //cutoff frequency [Hz]
float r = exp(-2*M_PI*cutoff_frequency*dt); //filter constant

float duty; //duty cycle for PWM (-400 to 400)

// enumerate the different possible haptic modes
enum hModes{
  ZERO,
  SPRING,
  DAMPER,
  SPRING_DAMPER,
  WALL,
  BUMP_VALLEY,
  TEXTURE
};

// pick which mode is there from the start
hModes hapticMode = SPRING;
//volatile lets the compiler know this value may change due to outside factors (e.g. keyboard press or PC command)

unsigned long isr_ms = 0;     // free-running millisecond counter, incremented in the ISR


void setup() {

  //****DO NOT CHANGE*****
  //set up PWM on Timer1 so it's faster and we don't hear the annoying hum anymore
  //this stuff is more in the weeds, please consult the ATmega328/P datasheet for more detailed info (p. ~170)
  //set phase and frequency correct pwm at 20kHz:
  TCCR1A = (1 << COM1A1); //clear OC1 on compare match when up-counting, sets on match when down-counting
  TCCR1B = (1 << WGM13) | (1 << CS10); //waveform generation mode 8 (phase/freq correct, ICR1 top), prescaler = 1
  ICR1 = 400; //ICR1 defines TOP in WGM8
  // the results of the above code is:
  // freq_PWM = freq_CPU / (2 * prescaler * TOP)
  // freq_PWM = 16,000,000 / (2 * 1 * 400) = 20,000 or 20 kHz

  // Set motor controlling pins to OUTPUT mode
  pinMode(13, OUTPUT); //pin 13 is the onboard LED, we will use it to indicate when we are sending telemetry
  pinMode(MotIn1, OUTPUT);
  pinMode(MotIn2, OUTPUT);
  pinMode(PWMout, OUTPUT);

  // Initalize motor direction and set to 0 (no spin)
  digitalWrite(MotIn1, HIGH);
  digitalWrite(MotIn2, LOW);
  OCR1A = 0;  //write to this register for PWM later instead of "analogwrite"

  // Configure control interrupt with Timer2 to make 1kHz control loop
  cli();  //disable interrupts

  TCCR2A = 0;
  TCCR2B = 0;

  // waveform generation mode 2 -- clear timer on compare match (CTC) mode
  TCCR2A |= (1 << WGM21);

  // Prescaler = 64
  TCCR2B |= (1 << CS22);

  OCR2A = 249;
  // freq = freq_cpu / (prescaler * (1 + OCR2A))
  // freq = 16,000,000 / (64 * (1 + 249)) = 1000 Hz or 1 kHz
  // no multiplication by factor of 2 in denominator as Timer2 is single-slope (Timer1 is dual-slope)

  // enable interrupt
  TIMSK2 |= (1 << OCIE2A);

  sei();   // enable interrupts

  Serial.begin(115200);  //begin serial communication
}

void setMotor(int motCommand) {
  //motCommand range: -400 to 400
  //Limit values to this range
  if (motCommand > 400) {
    motCommand = 400;
  }
  if (motCommand < -400) {
    motCommand = -400;
  }

  //command motor speed and direction based on motCommand
  if(motCommand > 0) {
    digitalWrite(MotIn1, LOW);
    digitalWrite(MotIn2, HIGH);
    OCR1A = motCommand;
  }
  if(motCommand < 0) {
    digitalWrite(MotIn1, HIGH);
    digitalWrite(MotIn2, LOW);
    OCR1A = -motCommand;
  }
}
// write each haptic environment as a function that returns the desired duty cycle for PWM
// writing as functions can help make the code easier to parse (plus you can collapse them in the IDE)

// simple spring
float spring(float x){
  float k = 60;
  return -k * x;
}

// simple damper
float damper(float v){
  float b = 8;
  return -b * v;
}

// spring plus damping
float springDamper(float x, float v){
  float k = 80;
  float b = 7;
  return -k * x - b * v;
}

// wall with damping
float wall(float x, float v) {
  float x_wall = 2;   // wall location (cm)
  float k_wall = 200; // wall stiffness
  float b_wall = 8;  // wall damping (try increasing this to feel some instability vibrations)
  if (x > x_wall)
  {
    return -k_wall * (x - x_wall)  + -b_wall*(v);
  }
  else
  {
    return 0;
  }
}

// Bump and Valley
float bumpValley(float x){
  float bump_location = 2;
  float bump_length = 3;
  float bump_height = 2;
  float bump_k = 200;
  float valley_location = -2;
  float valley_length = 3;
  float valley_height = 2;
  float valley_k = 200;

  if ((x <= (bump_location + bump_length / 2)) && (x >= (bump_location - bump_length / 2))) {
    // The handle is on the bump
    return bump_k * bump_height * cos(M_PI / bump_length * (x - bump_location)) * sin(M_PI / bump_length * (x - bump_location));
  } else if ((x <= (valley_location + valley_length / 2)) && (x >= (valley_location - valley_length / 2))) {
    // The handle is in the valley
    return -valley_k * valley_height * cos(M_PI / valley_length * (x - valley_location)) * sin(M_PI / valley_length * (x - valley_location));
  } else {
    // the handle is on flat ground
    return 0;
  }

}

//Texture with sinusoid
float texture(float x, float v){
  float w = 0.5; //width of damping area (cm)
  float b = 7;  //damping constant
  if (sin((M_PI * x) / w)> 0) {
    return -b * v;
  }
  else{
    return 0;
  }
}

// The "superloop" below can now just be used for things like serial communication
// runs in 2ms (all of that time is spent in sending telemetry over serial)
// haplink.update() runs in us even if receiving a packet
// haplink.sendAllTelemetry() runs about 1ms per telemetry variable (14 bytes)
void loop() {
  // Update param variables by reading incoming serial packets from PC
  // allow serial monitor to read for a new mode and switch accordingly
  if(Serial.available()){
    char s = Serial.read();
    if (s == '0') hapticMode = ZERO;
    if (s == '1') hapticMode = SPRING;
    if (s == '2') hapticMode = DAMPER;
    if (s == '3') hapticMode = SPRING_DAMPER;
    if (s == '4') hapticMode = WALL;
    if (s == '5') hapticMode = BUMP_VALLEY;
    if (s == '6') hapticMode = TEXTURE;
  }
}

//Haptic loop running at 1kHz using an interrupt service routine (ISR) for reliable calling
//runs in ~100us
ISR(TIMER2_COMPA_vect) {
  //digitalWrite(13, HIGH); //turn on LED to indicate we are sending telemetry
  isr_ms++; // free-running ms counter, used for buzz timing in carGame()

  // read encoder
  pos = encoder.read();

  pulley_angle = (pos / encoderResolution) * 2 * M_PI; //angular position of motor pulley in radians

  sector_angle = (pulley_angle * pulley_radius) / sector_radius; //angular position of sector pulley in radians

  //determine handle position in cm
  handle_pos = 100*(handle_length * pulley_radius * pulley_angle) / sector_radius;

  // handle velocity (cm/s) using a 1st-order low pass filter with constant r defined in setup()
  handle_vel = r * handle_vel_prev + (1 - r) * (handle_pos - handle_pos_prev) / dt;

  // update "previous" terms for next loop
  handle_pos_prev = handle_pos;
  handle_vel_prev = handle_vel;

  // switch statement to determine which haptic mode we will use
  switch(hapticMode){
    case ZERO:
      duty = 0;
      encoder.write(0);
      pos = 0;
      break;
    case SPRING:
      duty = spring(handle_pos);
      break;
    case DAMPER:
      duty = damper(handle_vel);
      break;
    case SPRING_DAMPER:
      duty = springDamper(handle_pos, handle_vel);
      break;
    case WALL:
      duty = wall(handle_pos, handle_vel);
      break;
    case BUMP_VALLEY:
      duty = bumpValley(handle_pos);
      break;
    case TEXTURE:
      duty = texture(handle_pos,handle_vel);
      break;
    }

  // command motor based on duty cycle (-400 to 400)
  setMotor(duty);
  //digitalWrite(13, LOW); //turn off LED to indicate we are done sending telemetry
}