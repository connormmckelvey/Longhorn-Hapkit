#ifndef COMMUNICATION_H
#define COMMUNICATION_H

#include <Arduino.h>

/*
    ============================================================
    Communication Module for Haptic / Simulation Applications
    ============================================================

    Responsibilities:
    - Non-blocking serial command parsing
    - Structured command handling (Type + Value)
    - Rate-controlled state transmission to PC
    - Optional debug messaging

    Designed for real-time control loops.
    commUpdate() must be called every loop iteration.
*/


// ============================================================
// Initialization
// ============================================================

/*
    Initializes serial communication.

    Parameters:
        baudRate      : Serial baud rate (e.g. 115200)
        sendRateHz    : Rate at which state data is transmitted to PC
                        (e.g. 50 Hz, 100 Hz)
        enableDebug   : Enables or disables debug messages
        delimiter     : Character separating command type and value
                        Default expected format: "F 0.25"
*/
void commInit(
    unsigned long baudRate,
    float sendRateHz,
    bool enableDebug = false,
    char delimiter = ' ',
    bool streamEnabled = false
);


// ============================================================
// Main Update (Call Every Loop)
// ============================================================

/*
    Handles:
    - Reading incoming serial bytes
    - Building command buffer
    - Parsing completed commands
    - Managing timed state transmission

    MUST be called every loop iteration.
    This function is non-blocking.
*/
void commUpdate();


// ============================================================
// Command Handling
// ============================================================

/*
    Returns true if a complete command has been received
    and parsed since last check.

    Calling this function resets the internal "new command" flag.
*/
bool commCommandAvailable();

/*
    Returns the command type character.

    Example:
        Input  : "F 0.25"
        Output : 'F'
*/
char commGetCommandType();

/*
    Returns the numeric value associated with the command.

    Example:
        Input  : "F 0.25"
        Output : 0.25
*/
float commGetCommandValue();


// ============================================================
// State Transmission
// ============================================================

/*
    Sends system state to PC at configured sendRateHz.

    Format:
        position,velocity

    Example:
        0.523,0.041

    This function does NOT immediately transmit unless
    enough time has passed based on sendRateHz.

    Safe to call every loop iteration.
*/
void commSendState(float position, float velocity);


/*
    Sends a debug message if debugging is enabled.

    Format:
        DBG:message

    Example:
        DBG:Force Saturated
*/
void commSendDebug(const char* message);


// ============================================================
// Utility / Status
// ============================================================

/*
    Returns true if debug mode is enabled.
*/
bool commDebugEnabled();

/*
    Returns the configured state transmission rate in Hz.
*/
float commGetSendRate();

/*
    Enables or disables state streaming to PC.
    When disabled, commSendState() will not transmit data.
*/
void commSetStreamEnabled(bool enabled);
#endif
