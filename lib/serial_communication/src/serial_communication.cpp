#include "serial_communication.h"

// ============================================================
// Internal State (Private to this file)
// ============================================================

// ---- Configuration ----
static float g_sendRateHz = 100.0f;
static unsigned long g_sendIntervalMicros = 10000; // default 100 Hz
static bool g_debugEnabled = false;
static char g_delimiter = ' ';
static bool g_streamEnabled = false;

// ---- Command Parsing ----
static const uint8_t BUFFER_SIZE = 32;
static char g_inputBuffer[BUFFER_SIZE];
static uint8_t g_bufferIndex = 0;

static bool g_commandReady = false;
static char g_commandType = 0;
static float g_commandValue = 0.0f;

// ---- Timing ----
static unsigned long g_lastSendTime = 0;


// ============================================================
// Initialization
// ============================================================

void commInit(
    unsigned long baudRate,
    float sendRateHz,
    bool enableDebug,
    char delimiter,
    bool streamEnabled = false
) {
    Serial.begin(baudRate);

    g_sendRateHz = sendRateHz;
    g_sendIntervalMicros = (unsigned long)(1000000.0f / g_sendRateHz);

    g_debugEnabled = enableDebug;
    g_delimiter = delimiter;

    g_bufferIndex = 0;
    g_commandReady = false;
    g_lastSendTime = micros();
    g_streamEnabled = streamEnabled;
}


// ============================================================
// Main Update (Call Every Loop)
// ============================================================

void commUpdate() {

    while (Serial.available()) {

        char c = Serial.read();

        // End of line detected
        if (c == '\n' || c == '\r') {

            if (g_bufferIndex == 0)
                continue;

            g_inputBuffer[g_bufferIndex] = '\0';  // Null terminate

            // -------------------------------------------------
            // 1. HANDSHAKE CHECK
            // -------------------------------------------------

            if (strcmp(g_inputBuffer, "HELLO") == 0) {
                Serial.println("READY");
            }
            else {

                // -------------------------------------------------
                // 2. NORMAL COMMAND PARSING
                // Expected format: "F 0.25"
                // -------------------------------------------------

                char* delimiterPtr = strchr(g_inputBuffer, g_delimiter);

                if (delimiterPtr != nullptr) {

                    g_commandType = g_inputBuffer[0];
                    g_commandValue = atof(delimiterPtr + 1);
                    g_commandReady = true;
                }
            }

            // Reset buffer
            g_bufferIndex = 0;
        }
        else {
            // Add character to buffer safely
            if (g_bufferIndex < BUFFER_SIZE - 1) {
                g_inputBuffer[g_bufferIndex++] = c;
            }
            else {
                // Overflow protection: reset buffer
                g_bufferIndex = 0;
            }
        }
    }
}


// ============================================================
// Command Handling
// ============================================================

bool commCommandAvailable() {

    if (g_commandReady) {
        g_commandReady = false;
        return true;
    }

    return false;
}

char commGetCommandType() {
    return g_commandType;
}

float commGetCommandValue() {
    return g_commandValue;
}


// ============================================================
// State Transmission (Rate Controlled)
// ============================================================

void commSendState(float position, float velocity) {

    if (!g_streamEnabled)
    {
        return;
    }
    unsigned long now = micros();

    if (now - g_lastSendTime >= g_sendIntervalMicros) {

        g_lastSendTime = now;

        Serial.print(position);
        Serial.print(",");
        Serial.println(velocity);
    }
}


// ============================================================
// Debug Messaging
// ============================================================

void commSendDebug(const char* message) {

    if (!g_debugEnabled)
        return;

    Serial.print("DBG:");
    Serial.println(message);
}


// ============================================================
// Utility
// ============================================================

bool commDebugEnabled() {
    return g_debugEnabled;
}

float commGetSendRate() {
    return g_sendRateHz;
}

void commSetStreamEnabled(bool enabled) {
    g_streamEnabled = enabled;
}