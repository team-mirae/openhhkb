/* Runs the protocol core on a real Cortex-M0 under QEMU (-machine microbit -semihosting).
 * Proves the portable core behaves identically on-target. Output + exit via ARM semihosting. */
#include "hhkb_proto.h"
#include <stdint.h>

extern uint32_t _sdata, _edata, _sbss, _ebss, _etext, _estack;

/* -nostdlib: supply the mem* the compiler may emit for aggregate init. */
void *memset(void *d, int c, unsigned long n) {
    uint8_t *p = d;
    while (n--) *p++ = (uint8_t)c;
    return d;
}
void *memcpy(void *d, const void *s, unsigned long n) {
    uint8_t *p = d;
    const uint8_t *q = s;
    while (n--) *p++ = *q++;
    return d;
}

/* ---- ARM semihosting ---- */
static int sh_call(int op, void *arg) {
    register int r0 __asm__("r0") = op;
    register void *r1 __asm__("r1") = arg;
    __asm__ volatile("bkpt 0xAB" : "+r"(r0) : "r"(r1) : "memory");
    return r0;
}
static void sh_write0(const char *s) { sh_call(0x04, (void *)s); }
static void sh_exit(int code) {
    uint32_t a[2] = {0x20026, (uint32_t)code}; /* ADP_Stopped_ApplicationExit */
    sh_call(0x18, a);
    for (;;) {
    }
}

static int failures;
static void check(int cond, const char *name) {
    sh_write0(cond ? "  ok  " : " FAIL ");
    sh_write0(name);
    sh_write0("\n");
    if (!cond) failures++;
}

static void getkeymap(hhkb_device_t *d, uint8_t mode, uint8_t fn, uint8_t out[128]) {
    uint8_t req[64] = {0xAA, 0xAA, 0x87, 0x00, 0x02, mode, fn};
    uint8_t rep[HHKB_MAX_REPLIES * HHKB_REPORT_LEN];
    hhkb_handle_report(d, req, 64, rep);
    const uint8_t off[3] = {0, 58, 116}, ln[3] = {58, 58, 12};
    for (int i = 0; i < 3; i++)
        for (int j = 0; j < ln[i]; j++) out[off[i] + j] = rep[i * 64 + 6 + j];
}

int test_main(void) {
    hhkb_device_t dev;
    hhkb_device_init(&dev);
    sh_write0("openhhkb core on Cortex-M0 (QEMU):\n");

    /* GetKeyboardInformation header + type number */
    uint8_t req[64] = {0xAA, 0xAA, 0x02, 0x00, 0x00};
    uint8_t rep[HHKB_MAX_REPLIES * HHKB_REPORT_LEN];
    int n = hhkb_handle_report(&dev, req, 64, rep);
    int ok = (n == 1 && rep[0] == 0x55 && rep[1] == 0x55 && rep[2] == 0x02 && rep[5] == 0x38 &&
              rep[6] == 'P' && rep[7] == 'D');
    check(ok, "GetKeyboardInformation reply");

    /* default marker */
    uint8_t km[128];
    getkeymap(&dev, 0, 0, km);
    check(km[39] == 0x0B && km[38] == 0x0B && km[37] == 0x0E && km[36] == 0x05, "A S D F -> H H K B");
    check(km[26] == 0x1D && km[17] == 0x38 && km[16] == 0x87, "Z / backslash preserved");

    /* round-trip */
    uint8_t want[128];
    for (int i = 0; i < 128; i++) want[i] = (uint8_t)((i * 7 + 3) & 0x7F);
    uint8_t c1[64] = {0xAA, 0xAA, 0x86, 0x41, 0x3B, 0x00, 0x00};
    for (int i = 0; i < 57; i++) c1[7 + i] = want[i];
    uint8_t c2[64] = {0xAA, 0xAA, 0x86, 0x82, 0x3B};
    for (int i = 0; i < 59; i++) c2[5 + i] = want[57 + i];
    uint8_t c3[64] = {0xAA, 0xAA, 0x86, 0xC3, 0x0C};
    for (int i = 0; i < 12; i++) c3[5 + i] = want[116 + i];
    hhkb_handle_report(&dev, c1, 64, rep);
    hhkb_handle_report(&dev, c2, 64, rep);
    hhkb_handle_report(&dev, c3, 64, rep);
    getkeymap(&dev, 0, 0, km);
    int rt = 1;
    for (int i = 0; i < 128; i++)
        if (km[i] != want[i]) rt = 0;
    check(rt, "SetKeymap/GetKeymap round-trip");

    sh_write0(failures ? "RESULT: FAIL\n" : "RESULT: PASS\n");
    return failures;
}

void Reset_Handler(void) {
    uint32_t *src = &_etext, *dst = &_sdata;
    while (dst < &_edata) *dst++ = *src++;
    for (dst = &_sbss; dst < &_ebss;) *dst++ = 0;
    sh_exit(test_main());
}
void Default_Handler(void) {
    for (;;) {
    }
}
__attribute__((section(".isr_vector"), used)) void (*const g_vec[16])(void) = {
    (void (*)(void))(&_estack), Reset_Handler, Default_Handler, Default_Handler,
};
