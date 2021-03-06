import errno
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

import pebble

QEMU_DEFAULT_BT_PORT = 12344
QEMU_DEFAULT_CONSOLE_PORT = 12345
PHONESIM_PORT = 12342
TEMP_DIR = tempfile.gettempdir()
FNULL = open(os.devnull, 'w')


class PebbleEmulator(object):
    def __init__(self, sdk_path, debug, debug_phonesim, persistent_dir, oauth_token, platform=None):
        self.qemu_pid = os.path.join(TEMP_DIR, 'pebble-qemu.pid')
        self.qemu_platform = os.path.join(TEMP_DIR, 'pebble-qemu.platform')
        self.phonesim_pid = os.path.join(TEMP_DIR, 'pebble-phonesim.pid')
        self.port = PHONESIM_PORT
        self.sdk_path = sdk_path
        self.debug = debug
        self.debug_phonesim = debug_phonesim
        self.persistent_dir = persistent_dir
        self.oauth_token = oauth_token
        self.use_running_platform = False if platform is not None else True
        self.platform = platform if platform is not None else "basalt"

    def start(self, use_running_platform=False):
        need_wait = False

        if self.is_qemu_running():
            if self.use_running_platform == True or use_running_platform == True:
                logging.info("Using {} emulator...".format(self.running_platform()))
                return
            elif self.running_platform() != self.platform:
                self.kill_qemu()
                self.kill_phonesim()
                time.sleep(1)

        if not self.is_qemu_running():
            logging.info("Starting Pebble {} emulator...".format(self.platform))
            self.start_qemu()
            need_wait = True

        if not self.is_phonesim_running():
            logging.info("Starting phone simulator...")
            self.start_phonesim()
            need_wait = True

        if need_wait:
            time.sleep(10)

    def is_running(self, pidfile):
        if pidfile == None:
            return False

        pid = self.read_pid(pidfile)

        if pid is not None:
            try:
                os.kill(pid, 0)
            except OSError as err:
                # No Such Process
                if err.errno == errno.ESRCH:
                    return False
            return True
        else:
            return False

    def check_for_spi_images(self):
        qemu_spi_flash = self._get_spi_path()

        if not os.path.exists(qemu_spi_flash):
            logging.debug("Required QEMU file not found: {}".format(qemu_spi_flash))
            logging.debug("Copying {} SPI image to {}".format(self.platform, qemu_spi_flash))
            self.copy_spi_image()

    def copy_spi_image(self):
        sdk_qemu_spi_flash = os.path.join(self.sdk_path, 'Pebble', self.platform, 'qemu', 'qemu_spi_flash.bin')
        qemu_spi_flash = self._get_spi_path()

        if not os.path.exists(sdk_qemu_spi_flash):
            logging.debug("Copy Failed. Required QEMU file not found: {}".format(sdk_qemu_spi_flash))
            raise Exception("Your SDK does not support the Pebble Emulator.")
        else:
            os.makedirs(os.path.dirname(qemu_spi_flash))
            shutil.copy(sdk_qemu_spi_flash, qemu_spi_flash)

    def _get_spi_path(self, platform=None):
        if platform is None:
            platform = self.platform
        return os.path.join(self.persistent_dir, platform, pebble.get_sdk_version(), 'qemu', "qemu_spi_flash.bin")

    def running_platform(self):
        if self.is_qemu_running():
            with open(self.qemu_platform, 'r') as pf:
                return pf.read()
        else:
            return None

    def read_pid(self, pidfile):
        try:
            with open(pidfile, 'r') as pf:
                return int(pf.read())
        except (IOError, ValueError):
            return None

    def is_qemu_running(self):
        return self.is_running(self.qemu_pid)

    def is_phonesim_running(self):
        return self.is_running(self.phonesim_pid)

    def phonesim_address(self):
        return "localhost"

    def phonesim_port(self):
        return PHONESIM_PORT

    def start_qemu(self):
        qemu_bin = os.path.join(self.sdk_path, 'Pebble', 'common', 'qemu', 'qemu-system-arm' + "_" + platform.system() + '_' + platform.machine())
        qemu_micro_flash = os.path.join(self.sdk_path, 'Pebble', self.platform, 'qemu', "qemu_micro_flash.bin")
        qemu_spi_flash = self._get_spi_path()

        self.check_for_spi_images()

        for f in [qemu_bin, qemu_micro_flash]:
            if not os.path.exists(f):
                logging.debug("Required QEMU file not found: {}".format(f))
                raise Exception("Your SDK does not support the Pebble Emulator.")

        cmdline = [qemu_bin]
        cmdline.extend(["-rtc", "base=localtime", "-s", "-serial", "file:/dev/null"])
        cmdline.extend(["-serial", "tcp::{},server,nowait".format(QEMU_DEFAULT_BT_PORT)])
        cmdline.extend(["-serial", "tcp::{},server,nowait".format(QEMU_DEFAULT_CONSOLE_PORT)])
        if self.platform == "basalt":
            cmdline.extend(["-machine", "pebble-snowy-bb", "-cpu", "cortex-m4"])
            cmdline.extend(["-pflash", qemu_micro_flash])
            cmdline.extend(["-pflash", qemu_spi_flash])
        else:
            cmdline.extend(["-machine", "pebble-bb2", "-cpu", "cortex-m3"])
            cmdline.extend(["-pflash", qemu_micro_flash])
            cmdline.extend(["-mtdblock", qemu_spi_flash])

        cmdline.extend(["-pidfile", self.qemu_pid])

        logging.debug("QEMU command: " + " ".join(cmdline))
        if self.debug:
            subprocess.Popen(cmdline)
        else:
            subprocess.Popen(cmdline, stdout=FNULL, stderr=FNULL)

        # Save the platform
        with open(self.qemu_platform, 'w') as pf:
            pf.write(str(self.platform))

    def start_phonesim(self):
        phonesim_bin = os.path.join(self.sdk_path, 'Pebble', 'common', 'phonesim', 'phonesim.py')
        layout_file = os.path.join(self.sdk_path, 'Pebble', self.platform, 'qemu', "layouts.json")

        if not os.path.exists(phonesim_bin):
            logging.debug("phone simulator not found: {}".format(phonesim_bin))
            raise Exception("Your SDK does not support the Pebble Emulator")

        cmdline = [phonesim_bin]
        cmdline.extend(["--qemu", "localhost:{}".format(QEMU_DEFAULT_BT_PORT)])
        cmdline.extend(["--port", str(PHONESIM_PORT)])
        cmdline.extend(["--persist", os.path.join(self.persistent_dir, self.platform, pebble.get_sdk_version())])
        cmdline.extend(["--layout", layout_file])
        if self.debug_phonesim:
            cmdline.extend(['--debug'])

        if self.oauth_token:
            cmdline.extend(["--oauth", self.oauth_token])

        if self.debug:
            process = subprocess.Popen(cmdline)
        else:
            process = subprocess.Popen(cmdline, stdout=FNULL, stderr=FNULL)

        # Save the PID
        with open(self.phonesim_pid, 'w') as pf:
            pf.write(str(process.pid))

    def kill_qemu(self):
        if self.is_qemu_running():
            pid = self.read_pid(self.qemu_pid)
            try:
                os.kill(pid, 9)
                logging.info("Killed the pebble {} emulator".format(self.running_platform()))
            except:
                logging.error("Unexpected error: %s", sys.exc_info()[0])
                raise
        else:
            logging.warning("The pebble emulator isn't running")

    def kill_phonesim(self):
        if self.is_phonesim_running():
            pid = self.read_pid(self.phonesim_pid)
            try:
                os.kill(pid, 9)
                logging.info("Killed the phone simulator")
            except:
                logging.error("Unexpected error: %s", sys.exc_info()[0])
                raise
        else:
            logging.warning("The phone simulator isn't running")

    def wipe_spi(self, platform):
        if platform is None:
            platforms = ['aplite', 'basalt']
        else:
            platforms = [platform]

        for p in platforms:
            qemu_spi_flash = self._get_spi_path(p)
            if os.path.exists(qemu_spi_flash):
                os.unlink(qemu_spi_flash)

