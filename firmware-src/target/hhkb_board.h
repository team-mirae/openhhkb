/* Hardware abstraction the Hybrid firmware needs from the board layer.
 * Implemented per-target. A stub (board_stub.c) lets the image link while the real
 * USB FS device stack and the Topre matrix scanner are still TODO. */
#ifndef HHKB_BOARD_H
#define HHKB_BOARD_H

#include <stdint.h>
#include <stddef.h>

/* USB: the vendor config channel is interface 2 (0xFF00/0x01, 64-byte reports). */
void board_usb_init(void);
void board_usb_send(uint8_t iface, const uint8_t *data, uint16_t len);
/* Called by the board layer when an output report arrives from the host. */
void app_on_output_report(uint8_t iface, const uint8_t *data, uint16_t len);

/* HID keyboard report (interface 0) once matrix scanning exists. TODO: blocked on
 * the Topre capacitive sense details (GPIO matrix) — needs the physical board. */
void board_keyboard_send(const uint8_t *report8);

/* Jump to the resident vendor bootloader at 0x08000000 (handles the firmware update). */
void board_enter_bootloader(void);

/* Self-flash primitives (STM32F0), used only if we ever flash without the bootloader. */
int board_flash_unlock(void);
int board_flash_erase_page(uint32_t addr);
int board_flash_write(uint32_t addr, const uint8_t *data, uint32_t len);
void board_flash_lock(void);

#endif
