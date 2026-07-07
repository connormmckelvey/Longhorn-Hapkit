//IF YOU USE THIS CODE, MAKE SURE THE PWMout WIRE IS MOVED TO PIN 9
//Write all serial messages in loop(), do not do serial communication in ISR

//Hapkit basic environments code + CAR STEERING GAME mode
//Base: Ann Majewicz Fey and Ross Neuman 2/13/26
//Car game mode added for steering-game camp project

#include <Encoder.h>
#include <Haplink.h>
#include <math.h>
#define ENCODER_OPTIMIZE_INTERRUPTS

// Pin Declarations
const int MotIn1 = 4;   //motor login pin 1
const int MotIn2 = 5;   //motor logic pin 2
const int PWMout = 9;   //PWM signal to control voltage to motor (pins 9 and 10 are on timer1 (16bit))

const int encPinA = 3;  //encoder output "A"
const int encPinB = 12;  //encoder output "B"

Encoder encoder(encPinB, encPinA);  //the encoder library uses the pulses from the two encoder outputs to get one 48 CPR angular positon
Haplink haplink;

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

// ---- Car game variables ----
float road_pull = 0;       // signed force nudging the handle toward the curve's "correct" angle
int16_t surface_state = 0; // 0 = normal road, 1 = rumble strip, 2 = off-road, 3 = crash
float game_speed = 0;      // normalized 0 (stopped) to 1 (max speed)

// internal state for the car game (not sent over Haplink, just used locally)
int16_t prev_surface_state = 0;
int crash_timer = 0;          // counts down (in ms) while a crash jolt is playing
unsigned long isr_ms = 0;     // free-running millisecond counter, incremented in the ISR


// Edit this function if you want to add variables that can be sent or recived from any provided python script via Haplink
// Parameters are values sent to the Hapkit, Telemetry are values sent from the Hapkit
// "type" mentioned below can be any of the following: HL_UINT8, HL_INT16, HL_INT32, HL_FLOAT, HL_DOUBLE
// simply add a line using register_____(a new ID value, &<variable>, type)
void registerHaplinkVariables(){
  // car game params (sent from the PC each frame)
  haplink.registerParam(1, &road_pull, HL_FLOAT);
  haplink.registerParam(2, &surface_state, HL_INT16);
  haplink.registerParam(3, &game_speed, HL_FLOAT);

  haplink.registerTelemetry(0, &handle_pos, HL_FLOAT);
  haplink.registerTelemetry(1, &handle_vel, HL_FLOAT);
}


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
  haplink.begin(Serial);
  registerHaplinkVariables();
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
// ---- CAR STEERING GAME ----
// x = handle position (cm), v = handle velocity (cm/s)
//   1) a self-centering spring, stiffer at higher game_speed
//   2) road_pull: a tug toward the "correct" wheel angle for the upcoming curve
//   3) surface effects: rumble strip buzz, off-road drag, or a crash jolt
float carGame(float x, float v){
  float k_center = 90.0;            // Increased from 55 for much heavier steering feel
  float b_base = 6.0;               // Base damping
  float b_center_extra = 10.0;      // Extra damping near center (middle of the steer)
  float pull_gain = 18.0;           // scales road_pull (from PC) into an actual force (increased slightly)
  float speed_stiffness_gain = 45.0; // extra stiffness added at higher speed (increased from 35)

  // ---- crash jolt (overrides everything else while it plays) ----
  // detect a NEW crash (rising edge) so we only trigger once per crash event
  if (surface_state == 3 && prev_surface_state != 3) {
    crash_timer = 200; // length of jolt, in ms
  }
  prev_surface_state = surface_state;

  if (crash_timer > 0) {
    // strong, decaying, alternating jolt
    float decay = crash_timer / 200.0;
    float f = 300.0 * decay;
    if ((crash_timer % 20) >= 10) f = -f; // alternate direction for a "rattle" feel
    crash_timer--;
    return f;
  }

  // ---- base self-centering spring ----
  float force = -(k_center + speed_stiffness_gain * game_speed) * x;
  
  // Damping is dynamically boosted close to the middle of the steer
  float b_dynamic = b_base + (b_center_extra / (1.0 + abs(x)));
  force += -b_dynamic * v;

  // ---- road pull toward the curve's correct angle ----
  force += pull_gain * road_pull;

  // ---- surface effects ----
  if (surface_state == 1) {
    // rumble strip: fast buzz, ~40 Hz
    force += 60.0 * sin(2 * M_PI * 40.0 * (isr_ms * dt));
  } else if (surface_state == 2) {
    // off-road: heavy, sluggish wheel
    force += -12.0 * v;
  }

  return force;
}

// The "superloop" below can now just be used for things like serial communication
// runs in 2ms (all of that time is spent in sending telemetry over serial)
// haplink.update() runs in us even if receiving a packet
// haplink.sendAllTelemetry() runs about 1ms per telemetry variable (14 bytes)
void loop() {
  // Update param variables by reading incoming serial packets from PC
  //digitalWrite(13, HIGH); //turn on LED to indicate we are sending telemetry
  haplink.update();
  //digitalWrite(13, LOW); //turn off LED to indicate we are done sending telemetry
  haplink.sendAllTelemetry();
  //digitalWrite(13, LOW); //turn off LED to indicate we are done sending telemetry
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


  duty = carGame(handle_pos, handle_vel);

  // command motor based on duty cycle (-400 to 400)
  setMotor(duty);
  //digitalWrite(13, LOW); //turn off LED to indicate we are done sending telemetry
}