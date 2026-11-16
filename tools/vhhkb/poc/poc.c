// Proof of concept: create one virtual HID device that looks like HHKB Studio interface 1
// (VID 04fe, PID 0015, usage page 0xFF60 / usage 0x61, 32-byte in/out) and log every
// output report the host sends to it. Runs only inside a throwaway VM; never touches real hardware.
//
// Build:  clang -framework IOKit -framework CoreFoundation -o poc poc.c
// Sign:   codesign -f -s - --entitlements poc.entitlements poc
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hidsystem/IOHIDUserDevice.h>
#include <IOKit/hid/IOHIDKeys.h>
#include <dispatch/dispatch.h>
#include <stdio.h>
#include <stdlib.h>

static const uint8_t kStudioRawHidDescriptor[] = {
    0x06, 0x60, 0xff, 0x09, 0x61, 0xa1, 0x01, 0x09, 0x62, 0x15, 0x00, 0x26, 0xff, 0x00, 0x95, 0x20,
    0x75, 0x08, 0x81, 0x02, 0x09, 0x63, 0x15, 0x00, 0x26, 0xff, 0x00, 0x95, 0x20, 0x75, 0x08, 0x91,
    0x02, 0xc0};

static void setNum(CFMutableDictionaryRef d, CFStringRef k, int v) {
    CFNumberRef n = CFNumberCreate(NULL, kCFNumberIntType, &v);
    CFDictionarySetValue(d, k, n);
    CFRelease(n);
}

int main(int argc, char **argv) {
    int seconds = argc > 1 ? atoi(argv[1]) : 30;
    CFMutableDictionaryRef p = CFDictionaryCreateMutable(NULL, 0, &kCFTypeDictionaryKeyCallBacks,
                                                         &kCFTypeDictionaryValueCallBacks);
    CFDataRef desc = CFDataCreate(NULL, kStudioRawHidDescriptor, sizeof kStudioRawHidDescriptor);
    CFDictionarySetValue(p, CFSTR(kIOHIDReportDescriptorKey), desc);
    setNum(p, CFSTR(kIOHIDVendorIDKey), 0x04fe);
    setNum(p, CFSTR(kIOHIDProductIDKey), 0x0015);
    setNum(p, CFSTR(kIOHIDVersionNumberKey), 0x0211);
    setNum(p, CFSTR(kIOHIDLocationIDKey), 0x0bad1000);
    CFDictionarySetValue(p, CFSTR(kIOHIDProductKey), CFSTR("HHKB-Studio"));
    CFDictionarySetValue(p, CFSTR(kIOHIDManufacturerKey), CFSTR("PFU Limited"));
    CFDictionarySetValue(p, CFSTR(kIOHIDTransportKey), CFSTR("USB"));

    IOHIDUserDeviceRef dev = IOHIDUserDeviceCreateWithProperties(kCFAllocatorDefault, p, 0);
    if (!dev) {
        fprintf(stderr, "FAIL: IOHIDUserDeviceCreateWithProperties returned NULL "
                        "(missing entitlement or blocked by AMFI?)\n");
        return 1;
    }
    dispatch_queue_t q = dispatch_queue_create("vhhkb", DISPATCH_QUEUE_SERIAL);
    IOHIDUserDeviceSetDispatchQueue(dev, q);
    IOHIDUserDeviceRegisterSetReportBlock(dev, ^IOReturn(IOHIDReportType type, uint32_t reportID,
                                                         const uint8_t *report, CFIndex len) {
        printf("SET type=%d id=%u len=%ld:", type, reportID, (long)len);
        for (CFIndex i = 0; i < len; i++) printf(" %02x", report[i]);
        printf("\n");
        fflush(stdout);
        return kIOReturnSuccess;
    });
    IOHIDUserDeviceActivate(dev);
    printf("OK: virtual HHKB-Studio raw HID device active for %d s\n", seconds);
    fflush(stdout);
    sleep(seconds);
    IOHIDUserDeviceCancel(dev);
    return 0;
}
