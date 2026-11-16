/* Thin host CLI over the protocol core, for the Python test harness.
 * stdin lines:
 *   <hex>     one 64-byte output report -> prints "<n>" then n reply reports as hex
 *   DUMPFW    prints the hex of the firmware image reassembled by the update receiver
 *   RESET     re-init device and clear the firmware buffer
 */
#include "hhkb_proto.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint8_t fw_buf[400000];
static uint32_t fw_max;

static void fw_sink(void *ctx, uint32_t off, const uint8_t *data, uint16_t len) {
    (void)ctx;
    if ((uint64_t)off + len <= sizeof(fw_buf)) {
        memcpy(fw_buf + off, data, len);
        if (off + len > fw_max) fw_max = off + len;
    }
}

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(void) {
    hhkb_device_t dev;
    hhkb_device_init(&dev);
    dev.fw_sink = fw_sink;
    dev.fw_ctx = NULL;

    char line[4096];
    while (fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = 0;
        if (!line[0]) continue;
        if (!strcmp(line, "RESET")) {
            hhkb_device_init(&dev);
            dev.fw_sink = fw_sink;
            fw_max = 0;
            memset(fw_buf, 0, sizeof(fw_buf));
            printf("ok\n");
            fflush(stdout);
            continue;
        }
        if (!strcmp(line, "DUMPFW")) {
            for (uint32_t i = 0; i < fw_max; i++) printf("%02x", fw_buf[i]);
            printf("\n");
            fflush(stdout);
            continue;
        }
        uint8_t req[128];
        size_t n = 0;
        for (char *p = line; p[0] && p[1] && n < sizeof(req); p += 2) {
            int hi = hexval(p[0]), lo = hexval(p[1]);
            if (hi < 0 || lo < 0) break;
            req[n++] = (uint8_t)((hi << 4) | lo);
        }
        uint8_t replies[HHKB_MAX_REPLIES * HHKB_REPORT_LEN];
        int cnt = hhkb_handle_report(&dev, req, n, replies);
        printf("%d\n", cnt);
        for (int i = 0; i < cnt; i++) {
            for (int j = 0; j < HHKB_REPORT_LEN; j++) printf("%02x", replies[i * HHKB_REPORT_LEN + j]);
            printf("\n");
        }
        fflush(stdout);
    }
    return 0;
}
