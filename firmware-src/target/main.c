/* Hybrid firmware entry: wire the portable protocol core to the board's USB layer. */
#include "hhkb_proto.h"
#include "hhkb_board.h"

static hhkb_device_t g_dev;

static void on_enter_bootloader(void *ctx) {
    (void)ctx;
    board_enter_bootloader(); /* does not return */
}

/* The board layer calls this for each output report from the host. */
void app_on_output_report(uint8_t iface, const uint8_t *data, uint16_t len) {
    if (iface != 2) return; /* vendor config channel */
    uint8_t replies[HHKB_MAX_REPLIES * HHKB_REPORT_LEN];
    int n = hhkb_handle_report(&g_dev, data, len, replies);
    for (int i = 0; i < n; i++)
        board_usb_send(iface, replies + i * HHKB_REPORT_LEN, HHKB_REPORT_LEN);
}

int main(void) {
    hhkb_device_init(&g_dev);
    g_dev.enter_bootloader = on_enter_bootloader;

    board_usb_init();
    for (;;) {
        /* USB runs on interrupt; matrix scan -> board_keyboard_send() goes here (TODO). */
    }
}
