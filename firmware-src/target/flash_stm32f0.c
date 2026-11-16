/* STM32F0 flash primitives + jump to the resident bootloader.
 * Register addresses from the STM32F0 reference manual (FLASH @ 0x40022000). */
#include "hhkb_board.h"
#include <stdint.h>

#define FLASH_BASE 0x40022000u
#define FLASH_KEYR (*(volatile uint32_t *)(FLASH_BASE + 0x04))
#define FLASH_SR (*(volatile uint32_t *)(FLASH_BASE + 0x0C))
#define FLASH_CR (*(volatile uint32_t *)(FLASH_BASE + 0x10))
#define FLASH_AR (*(volatile uint32_t *)(FLASH_BASE + 0x14))
#define FLASH_KEY1 0x45670123u
#define FLASH_KEY2 0xCDEF89ABu
#define CR_PG (1u << 0)
#define CR_PER (1u << 1)
#define CR_STRT (1u << 6)
#define CR_LOCK (1u << 7)
#define SR_BSY (1u << 0)
#define SR_EOP (1u << 5)
#define BOOTLOADER_BASE 0x08000000u

static void flash_wait(void) {
    while (FLASH_SR & SR_BSY) {
    }
    if (FLASH_SR & SR_EOP) FLASH_SR = SR_EOP;
}

int board_flash_unlock(void) {
    if (FLASH_CR & CR_LOCK) {
        FLASH_KEYR = FLASH_KEY1;
        FLASH_KEYR = FLASH_KEY2;
    }
    return (FLASH_CR & CR_LOCK) ? -1 : 0;
}

void board_flash_lock(void) { FLASH_CR |= CR_LOCK; }

int board_flash_erase_page(uint32_t addr) {
    flash_wait();
    FLASH_CR |= CR_PER;
    FLASH_AR = addr;
    FLASH_CR |= CR_STRT;
    flash_wait();
    FLASH_CR &= ~CR_PER;
    return 0;
}

int board_flash_write(uint32_t addr, const uint8_t *data, uint32_t len) {
    flash_wait();
    FLASH_CR |= CR_PG;
    for (uint32_t i = 0; i + 1 < len; i += 2) { /* STM32F0 programs half-words */
        uint16_t hw = (uint16_t)(data[i] | (data[i + 1] << 8));
        *(volatile uint16_t *)(addr + i) = hw;
        flash_wait();
    }
    FLASH_CR &= ~CR_PG;
    return 0;
}

/* Hand control to the vendor bootloader (which owns the firmware-update protocol). */
void board_enter_bootloader(void) {
    __asm volatile("cpsid i");
    uint32_t sp = *(volatile uint32_t *)(BOOTLOADER_BASE);
    uint32_t pc = *(volatile uint32_t *)(BOOTLOADER_BASE + 4);
    *(volatile uint32_t *)0xE000ED08u = BOOTLOADER_BASE; /* VTOR */
    __asm volatile("msr msp, %0" ::"r"(sp));
    ((void (*)(void))pc)();
    for (;;) {
    }
}
