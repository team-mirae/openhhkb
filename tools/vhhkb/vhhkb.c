// vhhkb: virtual HID devices driven over stdin/stdout. Runs inside the throwaway VM only.
//
// All configuration and logic live in the host-side responder (tools/responder); this program only
// creates devices and relays reports. Line protocol, tab-separated, one message per line:
//
//   host -> vhhkb
//     DEV <idx> <vid> <pid> <version> <location> <product> <manufacturer> <descriptor-hex>
//     GO                      activate all declared devices
//     IN  <idx> <hex>         send an input report from device <idx> to the host OS
//     QUIT
//   vhhkb -> host
//     READY <idx>             device <idx> created and active
//     OUT <idx> <type> <id> <hex>   output/feature report the OS sent to device <idx> (SetReport)
//     GET <idx> <type> <id>   the OS asked for a report (GetReport); answered with zeros
//     ERR <text>
//
// Numbers are decimal or 0x-prefixed hex. Build and sign: see README.md.
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDKeys.h>
#include <IOKit/hidsystem/IOHIDUserDevice.h>
#include <dispatch/dispatch.h>
#include <mach/mach_time.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_DEV 8

static IOHIDUserDeviceRef devs[MAX_DEV];
static dispatch_queue_t outq;  // serialises writes to stdout

static void emit(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void emit(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    char *s = NULL;
    vasprintf(&s, fmt, ap);
    va_end(ap);
    dispatch_sync(outq, ^{
      fputs(s, stdout);
      fputc('\n', stdout);
      fflush(stdout);
    });
    free(s);
}

static char *hex(const uint8_t *p, CFIndex n) {
    char *s = malloc(n * 2 + 1);
    for (CFIndex i = 0; i < n; i++) sprintf(s + i * 2, "%02x", p[i]);
    s[n * 2] = 0;
    return s;
}

static CFIndex unhex(const char *s, uint8_t *out, CFIndex max) {
    CFIndex n = 0;
    while (s[0] && s[1] && n < max) {
        unsigned v;
        if (sscanf(s, "%2x", &v) != 1) break;
        out[n++] = (uint8_t)v;
        s += 2;
    }
    return n;
}

static void setNum(CFMutableDictionaryRef d, CFStringRef k, long v) {
    CFNumberRef n = CFNumberCreate(NULL, kCFNumberLongType, &v);
    CFDictionarySetValue(d, k, n);
    CFRelease(n);
}

static void setStr(CFMutableDictionaryRef d, CFStringRef k, const char *v) {
    CFStringRef s = CFStringCreateWithCString(NULL, v, kCFStringEncodingUTF8);
    CFDictionarySetValue(d, k, s);
    CFRelease(s);
}

static CFMutableDictionaryRef props[MAX_DEV];

static void declare(char **f, int nf) {
    if (nf != 9) { emit("ERR DEV needs 8 fields"); return; }
    int idx = atoi(f[1]);
    if (idx < 0 || idx >= MAX_DEV || props[idx]) { emit("ERR bad or duplicate idx %d", idx); return; }
    CFMutableDictionaryRef p = CFDictionaryCreateMutable(NULL, 0, &kCFTypeDictionaryKeyCallBacks,
                                                         &kCFTypeDictionaryValueCallBacks);
    setNum(p, CFSTR(kIOHIDVendorIDKey), strtol(f[2], NULL, 0));
    setNum(p, CFSTR(kIOHIDProductIDKey), strtol(f[3], NULL, 0));
    setNum(p, CFSTR(kIOHIDVersionNumberKey), strtol(f[4], NULL, 0));
    setNum(p, CFSTR(kIOHIDLocationIDKey), strtol(f[5], NULL, 0));
    setStr(p, CFSTR(kIOHIDProductKey), f[6]);
    setStr(p, CFSTR(kIOHIDManufacturerKey), f[7]);
    setStr(p, CFSTR(kIOHIDTransportKey), "USB");
    /* So hidapi (and anything matching on USB interface number) sees this as HID interface <idx>. */
    setNum(p, CFSTR("bInterfaceClass"), 3);   /* HID class */
    setNum(p, CFSTR("bInterfaceNumber"), idx);
    uint8_t buf[1024];
    CFIndex n = unhex(f[8], buf, sizeof buf);
    CFDataRef d = CFDataCreate(NULL, buf, n);
    CFDictionarySetValue(p, CFSTR(kIOHIDReportDescriptorKey), d);
    CFRelease(d);
    props[idx] = p;
}

static void activate(void) {
    for (int i = 0; i < MAX_DEV; i++) {
        if (!props[i]) continue;
        IOHIDUserDeviceRef dev = IOHIDUserDeviceCreateWithProperties(kCFAllocatorDefault, props[i], 0);
        if (!dev) { emit("ERR create failed for %d (entitlement/AMFI?)", i); continue; }
        int idx = i;
        IOHIDUserDeviceSetDispatchQueue(dev, dispatch_queue_create("vhhkb.dev", DISPATCH_QUEUE_SERIAL));
        IOHIDUserDeviceRegisterSetReportBlock(dev, ^IOReturn(IOHIDReportType type, uint32_t id,
                                                             const uint8_t *r, CFIndex len) {
          char *h = hex(r, len);
          emit("OUT\t%d\t%d\t%u\t%s", idx, type, id, h);
          free(h);
          return kIOReturnSuccess;
        });
        IOHIDUserDeviceRegisterGetReportBlock(dev, ^IOReturn(IOHIDReportType type, uint32_t id,
                                                             uint8_t *r, CFIndex *len) {
          emit("GET\t%d\t%d\t%u", idx, type, id);
          memset(r, 0, *len);
          return kIOReturnSuccess;
        });
        IOHIDUserDeviceActivate(dev);
        devs[i] = dev;
        emit("READY\t%d", i);
    }
}

static void input(char **f, int nf) {
    if (nf != 3) { emit("ERR IN needs 2 fields"); return; }
    int idx = atoi(f[1]);
    if (idx < 0 || idx >= MAX_DEV || !devs[idx]) { emit("ERR no device %d", idx); return; }
    uint8_t buf[1024];
    CFIndex n = unhex(f[2], buf, sizeof buf);
    IOReturn r = IOHIDUserDeviceHandleReportWithTimeStamp(devs[idx], mach_absolute_time(), buf, n);
    if (r != kIOReturnSuccess) emit("ERR HandleReport %d: 0x%x", idx, r);
}

int main(void) {
    outq = dispatch_queue_create("vhhkb.out", DISPATCH_QUEUE_SERIAL);
    char *line = NULL;
    size_t cap = 0;
    while (getline(&line, &cap, stdin) > 0) {
        line[strcspn(line, "\r\n")] = 0;
        char *f[16];
        int nf = 0;
        for (char *t = strtok(line, "\t"); t && nf < 16; t = strtok(NULL, "\t")) f[nf++] = t;
        if (nf == 0) continue;
        if (!strcmp(f[0], "DEV")) declare(f, nf);
        else if (!strcmp(f[0], "GO")) activate();
        else if (!strcmp(f[0], "IN")) input(f, nf);
        else if (!strcmp(f[0], "QUIT")) break;
        else emit("ERR unknown command %s", f[0]);
    }
    for (int i = 0; i < MAX_DEV; i++)
        if (devs[i]) IOHIDUserDeviceCancel(devs[i]);
    return 0;
}
