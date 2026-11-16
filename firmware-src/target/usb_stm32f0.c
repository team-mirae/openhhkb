/* STM32F0 USB full-speed device driver for the openhhkb Hybrid firmware.
 *
 * Implements board_usb_init() / board_usb_send() and the standard enumeration + HID class
 * handling, serving the generated descriptors. Interface 2's OUT endpoint (the 0xFF00/0x01
 * vendor channel) feeds app_on_output_report(); board_usb_send() replies on its IN endpoint.
 *
 * !!! NOT YET TESTED ON HARDWARE. There is no STM32F0 USB model in QEMU and no board here, so
 * this compiles and follows RM0091 but has not been enumerated. Do not flash expecting it to
 * work untested. Clock assumes STM32F072 HSI48 + CRS (crystalless). An F070 needs an HSE path.
 */
#include "hhkb_board.h"
#include "usb_descriptors.h"
#include <stdint.h>
#include <stddef.h>

/* ---- register map (RM0091) ---- */
#define RCC_BASE 0x40021000u
#define RCC_CR2 (*(volatile uint32_t *)(RCC_BASE + 0x34))
#define RCC_CFGR3 (*(volatile uint32_t *)(RCC_BASE + 0x30))
#define RCC_APB1ENR (*(volatile uint32_t *)(RCC_BASE + 0x1C))
#define RCC_APB2ENR (*(volatile uint32_t *)(RCC_BASE + 0x18))
#define CRS_BASE 0x40006C00u
#define CRS_CR (*(volatile uint32_t *)(CRS_BASE + 0x00))
#define CRS_CFGR (*(volatile uint32_t *)(CRS_BASE + 0x04))

#define USB_BASE 0x40005C00u
#define USB_EPR(n) (*(volatile uint32_t *)(USB_BASE + (n) * 4))
#define USB_CNTR (*(volatile uint32_t *)(USB_BASE + 0x40))
#define USB_ISTR (*(volatile uint32_t *)(USB_BASE + 0x44))
#define USB_DADDR (*(volatile uint32_t *)(USB_BASE + 0x4C))
#define USB_BTABLE (*(volatile uint32_t *)(USB_BASE + 0x50))
#define USB_BCDR (*(volatile uint32_t *)(USB_BASE + 0x58))
#define USB_PMA ((volatile uint16_t *)0x40006000u)

#define CNTR_FRES (1u << 0)
#define CNTR_PDWN (1u << 1)
#define CNTR_RESETM (1u << 10)
#define CNTR_CTRM (1u << 15)
#define ISTR_CTR (1u << 15)
#define ISTR_RESET (1u << 10)
#define ISTR_EPID 0x0Fu
#define ISTR_DIR (1u << 4)
#define BCDR_DPPU (1u << 15)

/* EPnR bit fields */
#define EP_CTR_RX (1u << 15)
#define EP_SETUP (1u << 11)
#define EP_TYPE_CONTROL (1u << 9)
#define EP_TYPE_INTERRUPT (3u << 9)
#define EP_CTR_TX (1u << 7)
#define EP_STAT_TX (3u << 4)
#define EP_STAT_RX (3u << 12)
#define EP_DTOG_TX (1u << 6)
#define EP_DTOG_RX (1u << 14)
#define STAT_DISABLED 0u
#define STAT_STALL 1u
#define STAT_NAK 2u
#define STAT_VALID 3u
/* rc_w0 bits must be written 1 to stay set; toggle bits written 0 to stay. */
#define EP_W0 (EP_CTR_RX | EP_CTR_TX)
#define EP_NOTOG (EP_W0 | EP_TYPE_INTERRUPT | (1u << 8) | 0x0F)

static inline void ep_set_stat_tx(uint8_t ep, uint32_t stat) {
    uint32_t r = USB_EPR(ep);
    uint32_t w = (r & (EP_NOTOG | EP_STAT_TX)) ^ (stat << 4);
    USB_EPR(ep) = w | EP_W0;
}
static inline void ep_set_stat_rx(uint8_t ep, uint32_t stat) {
    uint32_t r = USB_EPR(ep);
    uint32_t w = (r & (EP_NOTOG | EP_STAT_RX)) ^ (stat << 12);
    USB_EPR(ep) = w | EP_W0;
}
static inline void ep_clear_ctr_rx(uint8_t ep) {
    USB_EPR(ep) = (USB_EPR(ep) & EP_NOTOG & ~EP_CTR_RX) | EP_CTR_TX;
}
static inline void ep_clear_ctr_tx(uint8_t ep) {
    USB_EPR(ep) = (USB_EPR(ep) & EP_NOTOG & ~EP_CTR_TX) | EP_CTR_RX;
}

/* ---- packet memory (BTABLE + per-EP buffers) -------------------------------
 * BTABLE at PMA offset 0; 4 endpoints * 8 bytes. Buffers after it. PMA is 16-bit words. */
#define BTABLE_OFF 0
#define PMA16(byte_off) USB_PMA[(byte_off) / 2]
#define EP_TXADDR(e) PMA16(BTABLE_OFF + (e) * 8 + 0)
#define EP_TXCOUNT(e) PMA16(BTABLE_OFF + (e) * 8 + 2)
#define EP_RXADDR(e) PMA16(BTABLE_OFF + (e) * 8 + 4)
#define EP_RXCOUNT(e) PMA16(BTABLE_OFF + (e) * 8 + 6)

/* fixed buffer offsets in PMA (bytes) */
#define PMA_EP0_TX 0x40
#define PMA_EP0_RX 0x80
#define PMA_EP1_TX 0xC0
#define PMA_EP2_TX 0x100
#define PMA_EP3_TX 0x140
#define PMA_EP3_RX 0x180

static void pma_write(uint16_t off, const uint8_t *src, uint16_t len) {
    for (uint16_t i = 0; i < len; i += 2) {
        uint16_t w = src[i];
        if (i + 1 < len) w |= (uint16_t)src[i + 1] << 8;
        PMA16(off + i) = w;
    }
}
static void pma_read(uint16_t off, uint8_t *dst, uint16_t len) {
    for (uint16_t i = 0; i < len; i += 2) {
        uint16_t w = PMA16(off + i);
        dst[i] = w & 0xFF;
        if (i + 1 < len) dst[i + 1] = w >> 8;
    }
}

/* ---- control transfer state ---- */
static const uint8_t *ep0_in_ptr;
static uint16_t ep0_in_rem;
static uint8_t pending_addr;

static void ep0_send_chunk(void) {
    uint16_t n = ep0_in_rem > 64 ? 64 : ep0_in_rem;
    pma_write(PMA_EP0_TX, ep0_in_ptr, n);
    EP_TXCOUNT(0) = n;
    ep0_in_ptr += n;
    ep0_in_rem -= n;
    ep_set_stat_tx(0, STAT_VALID);
}
static void ep0_send(const uint8_t *data, uint16_t len, uint16_t wLength) {
    ep0_in_ptr = data;
    ep0_in_rem = len < wLength ? len : wLength;
    ep0_send_chunk();
}
static void ep0_send_zlp(void) {
    EP_TXCOUNT(0) = 0;
    ep_set_stat_tx(0, STAT_VALID);
}

static const uint8_t *report_for(uint8_t iface, uint16_t *len) {
    switch (iface) {
    case 0: *len = sizeof(hid_report0); return hid_report0;
    case 1: *len = sizeof(hid_report1); return hid_report1;
    case 2: *len = sizeof(hid_report2); return hid_report2;
    }
    *len = 0;
    return 0;
}

static void handle_setup(void) {
    uint8_t s[8];
    pma_read(PMA_EP0_RX, s, 8);
    uint8_t bmReq = s[0], bReq = s[1];
    uint16_t wValue = s[2] | (s[3] << 8);
    uint16_t wIndex = s[4] | (s[5] << 8);
    uint16_t wLength = s[6] | (s[7] << 8);

    if ((bmReq & 0x60) == 0x00) { /* standard */
        switch (bReq) {
        case 0x05: /* SET_ADDRESS (status stage first, then apply) */
            pending_addr = wValue & 0x7F;
            ep0_send_zlp();
            return;
        case 0x06: { /* GET_DESCRIPTOR */
            uint8_t type = wValue >> 8;
            if (type == 1) ep0_send(usb_device_desc, sizeof(usb_device_desc), wLength);
            else if (type == 2) ep0_send(usb_config_desc, sizeof(usb_config_desc), wLength);
            else if (type == 3) {
                uint8_t idx = wValue & 0xFF;
                const uint8_t *p = idx == 0 ? usb_string0 : idx == 1 ? usb_string1 : usb_string2;
                uint16_t l = p[0];
                ep0_send(p, l, wLength);
            } else if (type == 0x22) { /* HID report descriptor, wIndex = interface */
                uint16_t l;
                const uint8_t *p = report_for(wIndex & 0xFF, &l);
                if (p) ep0_send(p, l, wLength);
                else ep_set_stat_tx(0, STAT_STALL);
            } else ep_set_stat_tx(0, STAT_STALL);
            return;
        }
        case 0x09: /* SET_CONFIGURATION */
            ep0_send_zlp();
            return;
        case 0x00: { /* GET_STATUS */
            static const uint8_t st[2] = {0, 0};
            ep0_send(st, 2, wLength);
            return;
        }
        default:
            ep_set_stat_tx(0, STAT_STALL);
            return;
        }
    } else if ((bmReq & 0x60) == 0x20) { /* class (HID) */
        switch (bReq) {
        case 0x0A: /* SET_IDLE */
        case 0x0B: /* SET_PROTOCOL */
            ep0_send_zlp();
            return;
        case 0x09: /* SET_REPORT: data stage on EP0 OUT; ack */
            ep0_send_zlp();
            return;
        default:
            ep_set_stat_tx(0, STAT_STALL);
            return;
        }
    }
    (void)wIndex;
    ep_set_stat_tx(0, STAT_STALL);
}

/* ---- public API ---- */
void board_usb_send(uint8_t iface, const uint8_t *data, uint16_t len) {
    if (iface != 2) return; /* only the vendor channel sends here */
    if (len > 64) len = 64;
    pma_write(PMA_EP3_TX, data, len);
    EP_TXCOUNT(3) = len;
    ep_set_stat_tx(3, STAT_VALID);
}

static void setup_endpoints(void) {
    USB_BTABLE = BTABLE_OFF;
    /* EP0 control */
    EP_TXADDR(0) = PMA_EP0_TX;
    EP_RXADDR(0) = PMA_EP0_RX;
    EP_RXCOUNT(0) = (1u << 15) | (1u << 10); /* BLSIZE=1, NUM_BLOCK=1 -> 64 bytes */
    USB_EPR(0) = EP_TYPE_CONTROL | 0;
    ep_set_stat_rx(0, STAT_VALID);
    ep_set_stat_tx(0, STAT_NAK);
    /* EP1 IN keyboard, EP2 IN multimedia, EP3 IN+OUT vendor (interrupt) */
    EP_TXADDR(1) = PMA_EP1_TX;
    USB_EPR(1) = EP_TYPE_INTERRUPT | 1;
    ep_set_stat_tx(1, STAT_NAK);
    EP_TXADDR(2) = PMA_EP2_TX;
    USB_EPR(2) = EP_TYPE_INTERRUPT | 2;
    ep_set_stat_tx(2, STAT_NAK);
    EP_TXADDR(3) = PMA_EP3_TX;
    EP_RXADDR(3) = PMA_EP3_RX;
    EP_RXCOUNT(3) = (1u << 15) | (1u << 10);
    USB_EPR(3) = EP_TYPE_INTERRUPT | 3;
    ep_set_stat_rx(3, STAT_VALID);
    ep_set_stat_tx(3, STAT_NAK);
    USB_DADDR = (1u << 7) | 0; /* enable, address 0 */
}

void USB_IRQHandler(void) {
    uint32_t istr = USB_ISTR;
    if (istr & ISTR_RESET) {
        USB_ISTR = ~ISTR_RESET;
        setup_endpoints();
        return;
    }
    while (USB_ISTR & ISTR_CTR) {
        uint32_t s = USB_ISTR;
        uint8_t ep = s & ISTR_EPID;
        uint32_t epr = USB_EPR(ep);
        if (ep == 0) {
            if (epr & EP_CTR_RX) {
                int setup = epr & EP_SETUP;
                ep_clear_ctr_rx(0);
                if (setup) handle_setup();
                else ep_set_stat_rx(0, STAT_VALID); /* OUT data/status */
            }
            if (USB_EPR(0) & EP_CTR_TX) {
                ep_clear_ctr_tx(0);
                if (pending_addr) {
                    USB_DADDR = (1u << 7) | pending_addr;
                    pending_addr = 0;
                }
                if (ep0_in_rem) ep0_send_chunk();
                else ep_set_stat_rx(0, STAT_VALID);
            }
        } else {
            if (epr & EP_CTR_RX) {
                ep_clear_ctr_rx(ep);
                if (ep == 3) {
                    uint16_t cnt = EP_RXCOUNT(3) & 0x3FF;
                    uint8_t buf[64];
                    if (cnt > 64) cnt = 64;
                    pma_read(PMA_EP3_RX, buf, cnt);
                    app_on_output_report(2, buf, cnt);
                    ep_set_stat_rx(3, STAT_VALID);
                }
            }
            if (USB_EPR(ep) & EP_CTR_TX) {
                ep_clear_ctr_tx(ep);
                ep_set_stat_tx(ep, STAT_NAK);
            }
        }
    }
}

void board_usb_init(void) {
    /* 48 MHz USB clock from HSI48 (STM32F072) + CRS auto-trim off USB SOF. */
    RCC_CR2 |= (1u << 16); /* HSI48 ON */
    while (!(RCC_CR2 & (1u << 17))) {
    }
    RCC_CFGR3 &= ~(3u << 7); /* USBSW = HSI48 */
    RCC_APB1ENR |= (1u << 23); /* USB clock */
    RCC_APB1ENR |= (1u << 27); /* CRS clock */
    CRS_CFGR = (CRS_CFGR & ~0xFFFFu) | 0xBB7F; /* RELOAD for 48MHz/1kHz SOF */
    CRS_CR |= (1u << 6) | (1u << 5); /* AUTOTRIMEN | CEN */

    USB_CNTR = CNTR_FRES; /* force reset, power up */
    for (volatile int i = 0; i < 1000; i++) {
    }
    USB_CNTR = 0; /* release reset */
    USB_ISTR = 0;
    USB_CNTR = CNTR_CTRM | CNTR_RESETM;
    USB_BCDR |= BCDR_DPPU; /* attach: enable DP pull-up */

    /* NVIC enable USB IRQ (31) */
    *(volatile uint32_t *)0xE000E100u = (1u << 31);
}
