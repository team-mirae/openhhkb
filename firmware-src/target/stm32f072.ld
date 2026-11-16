/* openhhkb application linker script for STM32F072CB (best-guess part).
 * Flash 128 KB: 0x08000000 bootloader (64 KB), application at 0x08010000 (64 KB).
 * RAM 16 KB at 0x20000000. Confirm against the physical board before flashing. */

MEMORY
{
    FLASH (rx)  : ORIGIN = 0x08010000, LENGTH = 64K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 16K
}

_estack = ORIGIN(RAM) + LENGTH(RAM);

SECTIONS
{
    .isr_vector : {
        KEEP(*(.isr_vector))
    } > FLASH

    .text : {
        *(.text*)
        *(.rodata*)
        . = ALIGN(4);
        _etext = .;
    } > FLASH

    .data : AT(_etext) {
        . = ALIGN(4);
        _sdata = .;
        *(.data*)
        . = ALIGN(4);
        _edata = .;
    } > RAM

    .bss : {
        . = ALIGN(4);
        _sbss = .;
        *(.bss*)
        *(COMMON)
        . = ALIGN(4);
        _ebss = .;
    } > RAM

    /* min heap/stack guard */
    ._user_heap_stack : {
        . = ALIGN(8);
        . = . + 0x400; /* heap */
        . = . + 0x800; /* stack */
    } > RAM
}
