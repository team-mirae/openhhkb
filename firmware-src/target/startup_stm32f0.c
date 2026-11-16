/* Minimal STM32F0 (Cortex-M0) startup: vector table, reset handler, C runtime init.
 * 16 core entries + 32 IRQ slots = 48, matching the vendor image's table. */
#include <stdint.h>

extern uint32_t _sdata, _edata, _sbss, _ebss, _etext, _estack;
extern int main(void);

void Reset_Handler(void);
void Default_Handler(void);

#define WEAK_ALIAS __attribute__((weak, alias("Default_Handler")))
void NMI_Handler(void) WEAK_ALIAS;
void HardFault_Handler(void) WEAK_ALIAS;
void SVC_Handler(void) WEAK_ALIAS;
void PendSV_Handler(void) WEAK_ALIAS;
void SysTick_Handler(void) WEAK_ALIAS;
void USB_IRQHandler(void) WEAK_ALIAS; /* IRQ31 on STM32F0 */

/* 0x08010000: initial SP, reset, then exceptions; IRQ handlers default-weak. */
__attribute__((section(".isr_vector"), used)) void (*const g_vectors[48])(void) = {
    (void (*)(void))(&_estack),
    Reset_Handler,
    NMI_Handler,
    HardFault_Handler,
    0, 0, 0, 0, 0, 0, 0, /* reserved */
    SVC_Handler,
    0, 0,
    PendSV_Handler,
    SysTick_Handler,
    /* 32 external IRQs; only USB (index 31) named, rest default */
    [16 + 31] = USB_IRQHandler,
};

/* Set the vector table offset to the app base so the core uses our table. */
#define SCB_VTOR (*(volatile uint32_t *)0xE000ED08u)

void Reset_Handler(void) {
    SCB_VTOR = 0x08010000u;

    uint32_t *src = &_etext, *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss;) *dst++ = 0;

    main();
    for (;;) {
    }
}

void Default_Handler(void) {
    for (;;) {
    }
}
