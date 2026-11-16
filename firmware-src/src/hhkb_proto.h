/* openhhkb clean-room firmware: portable config-protocol core (HHKB Professional Hybrid).
 *
 * Hardware-independent. The same core compiles for the host (unit tests, replaying captured
 * traffic) and for the STM32F0 target (wired to USB HID interface 2, the 0xFF00/0x01 64-byte
 * vendor channel). It owns no I/O: feed it an output report, it fills reply report(s) and
 * mutates device state. Protocol reverse-engineered from captures only; see
 * analysis/hhkb-hybrid-jis/captures/. No vendor code is used.
 *
 * Framing (interface 2, 64-byte reports, report id 0):
 *   request  AA AA <cmd> <chunk> <len> <payload...>
 *   reply    55 55 <cmd> <status> <chunk> <len> <payload...>
 */
#ifndef HHKB_PROTO_H
#define HHKB_PROTO_H

#include <stdint.h>
#include <stddef.h>

#define HHKB_REPORT_LEN 64
#define HHKB_KEYMAP_LEN 128
#define HHKB_MAX_REPLIES 3 /* GetKeymap answers in 3 chunks */

enum {
    HHKB_CMD_NOTIFY_STATE = 0x01,
    HHKB_CMD_GET_INFO = 0x02,
    HHKB_CMD_CONFIRM_KEYMAP = 0x04,
    HHKB_CMD_GET_DIPSW = 0x05,
    HHKB_CMD_GET_MODE = 0x06,
    HHKB_CMD_RESET_DIPSW = 0x07,
    HHKB_CMD_RESET_SLEEP = 0x08,
    HHKB_CMD_GET_SLEEP = 0x09,
    HHKB_CMD_SET_KEYMAP = 0x86,
    HHKB_CMD_GET_KEYMAP = 0x87,
    HHKB_CMD_FW_MODE = 0xE0,
    HHKB_CMD_FW_START = 0xE1,
    HHKB_CMD_FW_BLOCK = 0xE2,
    HHKB_CMD_FW_END = 0xE3,
};

/* A keymap set: standard layer, Fn layer, and (newer firmware) the shortcut/modifier map. */
typedef struct {
    uint8_t standard[HHKB_KEYMAP_LEN];
    uint8_t fn[HHKB_KEYMAP_LEN];
    uint8_t shortcut_standard[HHKB_KEYMAP_LEN];
    uint8_t shortcut_fn[HHKB_KEYMAP_LEN];
} hhkb_keymap_t;

typedef struct {
    char type_number[20]; /* e.g. "PD-KB820BS" */
    char revision[4];     /* "A" */
    char serial[16];
    uint8_t app_version[4];  /* prints "%X%x.%x%x": 0A 02 04 09 -> "A2.49" */
    uint8_t boot_version[4];
    uint8_t keyboard_mode; /* command06 */
    uint8_t dipsw[12];     /* command05 */
    uint8_t sleep_setting; /* command09 */
    hhkb_keymap_t keymap;

    /* keymap write assembly (SetKeymap arrives in 3 chunks) */
    uint8_t write_mode, write_fn;
    uint8_t write_buf[HHKB_KEYMAP_LEN];
    uint16_t write_len;

    /* firmware-update receiver (see analysis/.../captures README) */
    uint8_t fw_active;
    uint32_t fw_size;      /* from FW_START */
    uint32_t fw_received;  /* bytes stored so far */
    /* flash sink: target writes to real flash; host test just counts/captures. */
    void (*fw_sink)(void *ctx, uint32_t off, const uint8_t *data, uint16_t len);
    void (*fw_commit)(void *ctx); /* FW_END: verify + activate */
    void *fw_ctx;
} hhkb_device_t;

/* Initialise with the built-in default identity + keymap (ASDF->HHKB marker). */
void hhkb_device_init(hhkb_device_t *d);

/* Handle one 64-byte output report. Writes up to HHKB_MAX_REPLIES reply reports of
 * HHKB_REPORT_LEN bytes into `replies` (flat buffer, caller provides >= 3*64).
 * Returns the number of reply reports to send (0 if the request is ignored). */
int hhkb_handle_report(hhkb_device_t *d, const uint8_t *req, size_t req_len, uint8_t *replies);

#endif
