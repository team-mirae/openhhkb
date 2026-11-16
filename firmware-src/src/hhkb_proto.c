/* openhhkb clean-room firmware: portable config-protocol core. See hhkb_proto.h. */
#include "hhkb_proto.h"
#include "default_keymap.h"
#include <string.h>

/* ---- helpers ------------------------------------------------------------ */

static uint8_t *reply_slot(uint8_t *replies, int i) {
    uint8_t *r = replies + i * HHKB_REPORT_LEN;
    memset(r, 0, HHKB_REPORT_LEN);
    return r;
}

/* Build "55 55 <cmd> <status> <chunk> <len>" header; returns payload pointer. */
static uint8_t *reply_hdr(uint8_t *r, uint8_t cmd, uint8_t chunk, uint8_t len) {
    r[0] = 0x55;
    r[1] = 0x55;
    r[2] = cmd;
    r[3] = 0x00; /* status OK */
    r[4] = chunk;
    r[5] = len;
    return r + 6;
}

static const uint8_t *layer_for(const hhkb_device_t *d, uint8_t mode, uint8_t fn) {
    if (mode == 0x10)
        return fn ? d->keymap.shortcut_fn : d->keymap.shortcut_standard;
    return fn ? d->keymap.fn : d->keymap.standard;
}

static uint8_t *layer_ptr(hhkb_device_t *d, uint8_t mode, uint8_t fn) {
    if (mode == 0x10)
        return fn ? d->keymap.shortcut_fn : d->keymap.shortcut_standard;
    return fn ? d->keymap.fn : d->keymap.standard;
}

/* ---- init --------------------------------------------------------------- */

void hhkb_device_init(hhkb_device_t *d) {
    memset(d, 0, sizeof(*d));
    /* Identity matches the PD-KB820BS (JIS) we captured, so the JIS keymap tool accepts us. */
    strncpy(d->type_number, "PD-KB820BS", sizeof(d->type_number) - 1);
    strncpy(d->revision, "A", sizeof(d->revision) - 1);
    strncpy(d->serial, "OPENHHKB0000001", sizeof(d->serial) - 1);
    /* Report an old app version (A2.00) so a current keymap tool offers an update. */
    d->app_version[0] = 0x0A; /* 'A' */
    d->app_version[1] = 0x02;
    d->app_version[2] = 0x00;
    d->app_version[3] = 0x00;
    d->boot_version[0] = 0x0A;
    d->boot_version[1] = 0x01;
    d->keyboard_mode = 0x00;
    d->sleep_setting = 0x00;
    memcpy(d->keymap.standard, hhkb_default_standard, HHKB_KEYMAP_LEN);
    memcpy(d->keymap.fn, hhkb_default_fn, HHKB_KEYMAP_LEN);
    /* shortcut maps default to all-zero (no modifier assignments) */
}

/* ---- report handler ----------------------------------------------------- */

int hhkb_handle_report(hhkb_device_t *d, const uint8_t *req, size_t req_len, uint8_t *replies) {
    if (req_len < 5 || req[0] != 0xAA || req[1] != 0xAA)
        return 0;
    uint8_t cmd = req[2];
    uint8_t chunk = req[3];
    uint8_t len = req[4];
    const uint8_t *payload = req + 5;

    switch (cmd) {
    case HHKB_CMD_NOTIFY_STATE:
    case HHKB_CMD_CONFIRM_KEYMAP:
    case HHKB_CMD_RESET_SLEEP: {
        uint8_t *r = reply_slot(replies, 0);
        reply_hdr(r, cmd, 0x00, 0x00);
        if (cmd == HHKB_CMD_RESET_SLEEP && len >= 1)
            d->sleep_setting = payload[0];
        return 1;
    }
    case HHKB_CMD_RESET_DIPSW: {
        if (len >= 1)
            d->keyboard_mode = payload[0];
        reply_hdr(reply_slot(replies, 0), cmd, 0x00, 0x00);
        return 1;
    }
    case HHKB_CMD_GET_INFO: {
        uint8_t *r = reply_slot(replies, 0);
        reply_hdr(r, cmd, 0x00, 0x38);
        memcpy(r + 6, d->type_number, 20);
        memcpy(r + 26, d->revision, 4);
        memcpy(r + 30, d->serial, 16);
        memcpy(r + 46, d->app_version, 4);
        memcpy(r + 54, d->boot_version, 4);
        r[62] = 0x00; /* running firmware state: application */
        return 1;
    }
    case HHKB_CMD_GET_DIPSW: {
        uint8_t *r = reply_slot(replies, 0);
        uint8_t *p = reply_hdr(r, cmd, 0x00, 12);
        memcpy(p, d->dipsw, 12);
        return 1;
    }
    case HHKB_CMD_GET_MODE: {
        uint8_t *r = reply_slot(replies, 0);
        reply_hdr(r, cmd, 0x00, 1)[0] = d->keyboard_mode;
        return 1;
    }
    case HHKB_CMD_GET_SLEEP: {
        uint8_t *r = reply_slot(replies, 0);
        reply_hdr(r, cmd, 0x00, 1)[0] = d->sleep_setting;
        return 1;
    }
    case HHKB_CMD_GET_KEYMAP: {
        /* req: AA AA 87 00 02 <mode> <fn> */
        uint8_t mode = payload[0];
        uint8_t fn = payload[1];
        const uint8_t *km = layer_for(d, mode, fn);
        static const struct {
            uint8_t marker, off, len;
        } parts[3] = {{0x41, 0, 58}, {0x82, 58, 58}, {0xC3, 116, 12}};
        for (int i = 0; i < 3; i++) {
            uint8_t *r = reply_slot(replies, i);
            uint8_t *p = reply_hdr(r, cmd, parts[i].marker, parts[i].len);
            memcpy(p, km + parts[i].off, parts[i].len);
        }
        return 3;
    }
    case HHKB_CMD_SET_KEYMAP: {
        /* chunk 0x41: mode,fn + pos0..56 ; 0x82: pos57..115 ; 0xC3: pos116..127 */
        if (chunk == 0x41) {
            d->write_mode = payload[0];
            d->write_fn = payload[1];
            d->write_len = 0;
            if (len >= 2) {
                uint16_t n = (uint16_t)(len - 2);
                if (n > HHKB_KEYMAP_LEN) n = HHKB_KEYMAP_LEN;
                memcpy(d->write_buf, payload + 2, n);
                d->write_len = n;
            }
        } else {
            uint16_t n = len;
            if (d->write_len + n > HHKB_KEYMAP_LEN) n = HHKB_KEYMAP_LEN - d->write_len;
            memcpy(d->write_buf + d->write_len, payload, n);
            d->write_len += n;
            if (chunk == 0xC3 && d->write_len == HHKB_KEYMAP_LEN)
                memcpy(layer_ptr(d, d->write_mode, d->write_fn), d->write_buf, HHKB_KEYMAP_LEN);
        }
        reply_hdr(reply_slot(replies, 0), cmd, 0x00, 0x00);
        return 1;
    }
    case HHKB_CMD_FW_MODE: {
        reply_hdr(reply_slot(replies, 0), cmd, 0x00, 0x00);
        return 1;
    }
    case HHKB_CMD_FW_START: {
        /* payload: size LE32 + 2 header bytes (the .hfb's first 2 bytes) */
        d->fw_size = (uint32_t)payload[0] | (payload[1] << 8) | (payload[2] << 16) |
                     ((uint32_t)payload[3] << 24);
        d->fw_received = 0;
        d->fw_active = 1;
        /* payload = size(4) + the .hfb's first 2 bytes; those 2 bytes are file[0:2]. */
        if (d->fw_sink && len >= 6)
            d->fw_sink(d->fw_ctx, 0, payload + 4, 2);
        d->fw_received = (len >= 6) ? 2 : 0;
        reply_hdr(reply_slot(replies, 0), cmd, 0x00, 0x00);
        return 1;
    }
    case HHKB_CMD_FW_BLOCK: {
        /* payload: block number LE16 + data(len-2). Data is the next slice of the .hfb. */
        if (d->fw_active && len >= 2) {
            uint16_t dlen = (uint16_t)(len - 2);
            if (d->fw_sink)
                d->fw_sink(d->fw_ctx, d->fw_received, payload + 2, dlen);
            d->fw_received += dlen;
        }
        uint8_t *r = reply_slot(replies, 0);
        uint8_t *p = reply_hdr(r, cmd, 0x00, 0x02);
        p[0] = payload[0]; /* echo block number (tool accepted any value) */
        p[1] = payload[1];
        return 1;
    }
    case HHKB_CMD_FW_END: {
        if (d->fw_active && d->fw_commit)
            d->fw_commit(d->fw_ctx);
        d->fw_active = 0;
        reply_hdr(reply_slot(replies, 0), cmd, 0x00, 0x00);
        return 1;
    }
    default:
        return 0;
    }
}
