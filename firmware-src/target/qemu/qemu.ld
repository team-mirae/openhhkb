/* Linker for the QEMU Cortex-M0 smoke test (-machine microbit, nRF51: flash @ 0, RAM @ 0x20000000). */
MEMORY
{
    FLASH (rx)  : ORIGIN = 0x00000000, LENGTH = 256K
    RAM   (rwx) : ORIGIN = 0x20000000, LENGTH = 16K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS
{
    .isr_vector : { KEEP(*(.isr_vector)) } > FLASH
    .text : { *(.text*) *(.rodata*) . = ALIGN(4); _etext = .; } > FLASH
    .data : AT(_etext) { . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM
    .bss : { . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
}
