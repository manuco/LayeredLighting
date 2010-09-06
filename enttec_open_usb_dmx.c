
/**
  * The main purpose of this code is to separate USB / FTDI code
  * from DMX code.
  *
  * This app reads 513 bytes of DMX data (begining by 0) and
  * writes it to the Open USB DMX Enttec Widget.
  *
  * Frames beginning by other things than 0 are reserved for
  * future usages
  *
  * Reset is done via SIGUSR1, stop by SIGQUIT or SIGINT.
  * All others signals keep their default meanings.
  *
  * Command line arg :
  *    (None)     : app is displaying found devices
  *    "any"      : use the first available device
  *    a serial   : app will use this device
  */

#include <stdio.h>
#include <string.h>
#include <stdbool.h>

#include <signal.h>
#include <pthread.h>
#include <errno.h>

#include <ftdi.h>

#define ENTTEC_USB_WIDGET_VID 0x0403
#define ENTTEC_USB_WIDGET_PID 0x6001

struct ftdi_context ftdi_handle;
bool running = true;
char * serial = NULL;




/** Device management */

void listDevices(void) {
    struct ftdi_device_list * devices = NULL;
    struct ftdi_device_list * devices_pointer = NULL;

    ftdi_init(&ftdi_handle);

    int nbDevices = ftdi_usb_find_all(
        &ftdi_handle,
        &devices,
        ENTTEC_USB_WIDGET_VID,
        ENTTEC_USB_WIDGET_PID
    );
    devices_pointer = devices;

    if (nbDevices < 0) {
        fprintf(stderr, "ftdi_usb_find_all: %s", ftdi_get_error_string(&ftdi_handle));
        // introducing C exceptions :-)
        goto deinit;
    }

    fprintf(stderr, "%d devices found.\n", nbDevices);

    while (devices != NULL) {
        struct usb_device * dev = devices->dev;
        char serial[256];
        char name[256];
        char vendor[256];

        ftdi_usb_get_strings(
            &ftdi_handle, dev,
            vendor, sizeof(vendor),
            name, sizeof(name),
            serial, sizeof(serial)
        );

        fprintf(stdout, "Vendor : '%s'\nName : '%s'\nSerial : '%s'\n", vendor, name, serial);
        devices = devices->next;

    }
    ftdi_list_free(&devices_pointer);

    deinit:
    ftdi_deinit(&ftdi_handle);
}


int initOutput() {
    ftdi_init(&ftdi_handle);

    if (ftdi_usb_open_desc(&ftdi_handle, ENTTEC_USB_WIDGET_VID, ENTTEC_USB_WIDGET_PID, NULL, serial)) {
        fprintf(stderr, "Error opening device: %s\n", ftdi_get_error_string(&ftdi_handle));
        return 1;
    }

    if (ftdi_usb_reset(&ftdi_handle) < 0) {
        fprintf(stderr, "Unable to reset device: %s\n", ftdi_get_error_string(&ftdi_handle));
        return 1;
    }

    if (ftdi_set_line_property(&ftdi_handle, BITS_8, STOP_BIT_2, NONE) < 0) {
        fprintf(stderr, "Unable to configure device line: %s\n", ftdi_get_error_string(&ftdi_handle));
        return 1;
    }

    if (ftdi_set_baudrate(&ftdi_handle, 250000) < 0) {
        fprintf(stderr, "Unable to set device speed: %s\n", ftdi_get_error_string(&ftdi_handle));
        return 1;
    }

    if (ftdi_setrts(&ftdi_handle, 0) < 0) {
        fprintf(stderr, "Unable to set device RTS: %s\n", ftdi_get_error_string(&ftdi_handle));
        return 1;
    }
    ftdi_usb_purge_buffers(&ftdi_handle);
    return 0;
}

void closeOutput(void) {
    if (ftdi_usb_close(&ftdi_handle) < 0) {
        fprintf(stderr, "Unable close device: %s\n", ftdi_get_error_string(&ftdi_handle));
    }

    ftdi_deinit(&ftdi_handle);
}


/** Thread management */

bool thread_running = false;
pthread_t thread;
unsigned char internalBuffer[513];
unsigned char sharedBuffer[513];
bool neededSync;
pthread_mutex_t mutex = PTHREAD_MUTEX_INITIALIZER;

void * run(void * arg) {
    int device_opened;

    while (thread_running) {
        device_opened = false;
        while (thread_running && !device_opened) {
            if (initOutput()) {
                device_opened = false;
                sleep(1);
            } else {
                device_opened = true;
            }
        }

        while(thread_running && device_opened) {
            if (neededSync) {
                int error = pthread_mutex_trylock(&mutex);
                if (error && error != EBUSY) {
                    fprintf(stderr, "Unable to lock mutex.\n");
                    abort();
                } else if (error == 0) {
                    memcpy(internalBuffer, sharedBuffer, 513);
                    neededSync = false;
                    pthread_mutex_unlock(&mutex);
                }
            }

            if (ftdi_set_line_property2(&ftdi_handle, BITS_8, STOP_BIT_2, NONE, BREAK_ON) < 0) {
                fprintf(stderr, "Unable to toggle BREAK_ON: %s\n", ftdi_get_error_string(&ftdi_handle));
                break;
            }

            usleep(88);

            if (ftdi_set_line_property2(&ftdi_handle, BITS_8, STOP_BIT_2, NONE, BREAK_OFF) < 0) {
                fprintf(stderr, "Unable to toggle BREAK_OFF: %s\n", ftdi_get_error_string(&ftdi_handle));
                break;
            }

            usleep(8);

            if (ftdi_write_data(&ftdi_handle, internalBuffer, 513) < 0) {
                fprintf(stderr, "Unable to write DMX data: %s\n", ftdi_get_error_string(&ftdi_handle));
                break;
            }

            usleep(22754);
        }

        if (device_opened) {
            closeOutput();
        }
    }

    return NULL;
}


void startThread() {
    if (thread_running) {
        fprintf(stderr, "Thread already started !\n");
        return;
    }
    thread_running = true;
    pthread_create(&thread, NULL, run, NULL);
}

void updateBuffer(unsigned char * buffer) {
    if (pthread_mutex_lock(&mutex)) {
        perror("mutex lock");
        abort();
    }
    memcpy(sharedBuffer, buffer, 513);
    neededSync = true;

    if (pthread_mutex_unlock(&mutex)) {
        perror("mutex unlock");
        abort();
    }
}

void stopThread(void) {
    if (!thread_running) {
        return;
    }
    thread_running = false;
    pthread_join(thread, NULL);
}




/** Signals handling */


void onInt(int signal_num) {
    running = false;
    stopThread();
}

void onReset(int signal_num) {
    stopThread();
    startThread();
}

void initSignalHandlers(void) {
    struct sigaction act;
    sigset_t mask;

    sigemptyset(&mask);

    act.sa_handler = onInt;
    act.sa_mask = mask;
    act.sa_flags = 0;

    sigaction(SIGINT, &act, NULL);
    sigaction(SIGQUIT, &act, NULL);
    sigaction(SIGTERM, &act, NULL);

    act.sa_handler = onReset;
    sigaction(SIGUSR1, &act, NULL);
}

/** IO */



void readDMXFrame(void) {
    int i = 0;
    int ret;
    unsigned char readBuffer[513];

    while (i < 513) {
        ret = read(0, readBuffer, 513 - i);
        if (ret < 0 && errno == EINTR) {
            return;
        } else if (ret < 0) {
            perror("Stdin read");
            abort();
        } else if (ret == 0) {
            stopThread();
            running = false;
            return;
        }

        i += ret;
    }

    updateBuffer(readBuffer);
    if (!thread_running) {
        startThread();
    }
}

/** Main */

int main(int argc, char ** argv) {

    if (argc < 2) {
       listDevices();
       return 0;
    }

    char * user_serial = argv[1];

    if (strcmp(user_serial, "any") != 0) {
        serial = user_serial;
    }

    initSignalHandlers();

    while(running) {
        readDMXFrame();
    }
    return 0;
}
