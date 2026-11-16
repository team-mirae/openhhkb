// Test client: finds a HID device exactly the way the official keymap tools do
// (IOHIDManager matching on VendorID, ProductID, DeviceUsagePage, DeviceUsage) and sends one
// 32-byte output report. Only for use against the virtual device inside the VM.
//
// Build: clang -framework IOKit -framework CoreFoundation -o client client.c
#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDManager.h>
#include <stdio.h>

static void put(CFMutableDictionaryRef d, const char *k, int v) {
    CFStringRef key = CFStringCreateWithCString(NULL, k, kCFStringEncodingUTF8);
    CFNumberRef n = CFNumberCreate(NULL, kCFNumberIntType, &v);
    CFDictionarySetValue(d, key, n);
    CFRelease(n);
    CFRelease(key);
}

int main(void) {
    IOHIDManagerRef m = IOHIDManagerCreate(kCFAllocatorDefault, 0);
    CFMutableDictionaryRef match = CFDictionaryCreateMutable(NULL, 0, &kCFTypeDictionaryKeyCallBacks,
                                                             &kCFTypeDictionaryValueCallBacks);
    put(match, "VendorID", 0x04fe);
    put(match, "ProductID", 0x0015);
    put(match, "DeviceUsagePage", 0xff60);
    put(match, "DeviceUsage", 0x61);
    IOHIDManagerSetDeviceMatching(m, match);
    IOHIDManagerOpen(m, 0);
    CFSetRef set = IOHIDManagerCopyDevices(m);
    CFIndex n = set ? CFSetGetCount(set) : 0;
    printf("matched devices: %ld\n", (long)n);
    if (n == 0) return 1;
    IOHIDDeviceRef devs[8];
    CFSetGetValues(set, (const void **)devs);
    IOReturn r = IOHIDDeviceOpen(devs[0], 0);
    printf("open: 0x%x\n", r);
    uint8_t buf[32] = {0x02, 0x10, 0x01, 0x02, 0x00};  // Studio tool's first GetKeyboardInformation prefix
    r = IOHIDDeviceSetReport(devs[0], kIOHIDReportTypeOutput, 0, buf, sizeof buf);
    printf("setReport: 0x%x\n", r);
    return r == kIOReturnSuccess ? 0 : 2;
}
