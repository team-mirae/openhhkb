/* Placeholder board layer so the firmware image links and is structurally valid.
 * TODO: replace with the real STM32F0 USB FS device stack (3 HID interfaces from our
 * captured descriptors) and the Topre matrix scanner. These stubs do nothing. */
#include "hhkb_board.h"

__attribute__((weak)) void board_usb_init(void) {}
__attribute__((weak)) void board_usb_send(uint8_t iface, const uint8_t *data, uint16_t len) {
    (void)iface;
    (void)data;
    (void)len;
}
__attribute__((weak)) void board_keyboard_send(const uint8_t *report8) { (void)report8; }
