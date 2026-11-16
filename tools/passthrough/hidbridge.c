/* hidbridge: relay HID reports to/from a real keyboard's vendor interface (hidapi).
 * Runs on the HOST, opens the physical device, and bridges it to the VM's virtual device so a
 * vendor tool in the VM talks to the real keyboard while every report is logged by the responder.
 *
 * Line protocol (stdin/stdout), hex payloads:
 *   stdin:  W <hex>   write this output report to the device
 *           Q         quit
 *   stdout: READY <productName>
 *           R <hex>   an input report arrived from the device
 *           ERR <msg>
 *
 * Usage: hidbridge <vid_hex> <pid_hex> <interface_number>
 * SAFETY: this only moves bytes. The responder decides what is allowed to reach the device.
 */
#include <hidapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <poll.h>

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: hidbridge <vid_hex> <pid_hex> <iface>\n");
        return 2;
    }
    unsigned short vid = (unsigned short)strtol(argv[1], NULL, 16);
    unsigned short pid = (unsigned short)strtol(argv[2], NULL, 16);
    int iface = atoi(argv[3]);

    setbuf(stdout, NULL);
    fprintf(stderr, "dbg: starting, opening %04x:%04x iface %d\n", vid, pid, iface);
    if (hid_init()) {
        printf("ERR hid_init\n");
        return 1;
    }
    struct hid_device_info *devs = hid_enumerate(vid, pid), *d;
    char path[512] = {0};
    const wchar_t *pname = L"";
    for (d = devs; d; d = d->next)
        if (d->interface_number == iface) {
            strncpy(path, d->path, sizeof(path) - 1);
            pname = d->product_string ? d->product_string : L"";
            break;
        }
    if (!path[0]) {
        printf("ERR device %04x:%04x iface %d not found\n", vid, pid, iface);
        return 1;
    }
    hid_device *dev = hid_open_path(path);
    hid_free_enumeration(devs);
    if (!dev) {
        printf("ERR open failed\n");
        return 1;
    }
    hid_set_nonblocking(dev, 1);
    printf("READY %ls\n", pname);
    fflush(stdout);

    char line[4096];
    struct pollfd pfd = {.fd = 0, .events = POLLIN};
    unsigned char in[65];
    for (;;) {
        int pr = poll(&pfd, 1, 5);
        if (pr > 0 && (pfd.revents & POLLIN)) {
            if (!fgets(line, sizeof(line), stdin)) break;
            if (line[0] == 'Q') break;
            if (line[0] == 'W') {
                unsigned char out[65];
                memset(out, 0, sizeof(out));
                out[0] = 0x00; /* report id */
                int n = 1;
                char *p = line + 2;
                while (p[0] && p[1] && n < 65) {
                    int hi = hexval(p[0]), lo = hexval(p[1]);
                    if (hi < 0 || lo < 0) break;
                    out[n++] = (unsigned char)((hi << 4) | lo);
                    p += 2;
                }
                int w = hid_write(dev, out, 65);
                if (w < 0) {
                    printf("ERR write %ls\n", hid_error(dev));
                    fflush(stdout);
                }
            }
        }
        int r = hid_read_timeout(dev, in, sizeof(in), 0);
        if (r > 0) {
            printf("R ");
            for (int i = 0; i < r; i++) printf("%02x", in[i]);
            printf("\n");
            fflush(stdout);
        } else if (r < 0) {
            printf("ERR read %ls\n", hid_error(dev));
            fflush(stdout);
            break;
        }
    }
    hid_close(dev);
    return 0;
}
