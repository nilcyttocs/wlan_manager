#!/usr/bin/python

# WLAN Connectivity Manager
#
# Helper to check current connection status, scan for available networks,
# connect to specified network, and disconnect from network.

import os, sys, time, re, subprocess, argparse

version = "0.0.5"

dhcpcd_conf = "/etc/dhcpcd.conf"
dhcpcd_conf_ap = "/etc/dhcpcd.conf.ap"
dhcpcd_conf_sta = "/etc/dhcpcd.conf.sta"

wpa_conf = "/etc/wpa_supplicant/wpa_supplicant.conf"
wpa_conf_orig = "/etc/wpa_supplicant/wpa_supplicant.conf.orig"


class WlanManagerError(Exception):
    pass


class WlanManager(object):
    def __init__(self):
        pass

    # Private function to send bash shell command
    #
    # Returns: tuple containing stdout and stderr
    #
    def __send_command(self, command=None, extra_input=None):
        if command is None:
            raise WlanManagerError("Invalid command")

        if extra_input is not None:
            p = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True,
            )
            stdout, stderr = p.communicate(input=extra_input)
        else:
            p = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                shell=True,
            )
            stdout, stderr = p.communicate()

        if stderr != "":
            raise WlanManagerError(
                "Failed to run command: {}\nError: {}".format(command, stderr)
            )

        return stdout

    # Private function to check if operating in AP mode
    #
    # Returns: boolean indicating if operating in AP mode
    #
    def __is_ap_mode(self):
        stdout = self.__send_command("iw dev")
        for str in stdout.splitlines():
            str = str.strip()
            if "type AP" in str:
                return True

        return False

    # Private function to enable/disable AP mode
    #
    def __enable_ap_mode(self, enable):
        if enable:
            self.__send_command("ln -sf /lib/systemd/system/dnsmasq.service /etc/systemd/system/multi-user.target.wants/dnsmasq.service")
            self.__send_command("ln -sf /lib/systemd/system/hostapd.service /etc/systemd/system/multi-user.target.wants/hostapd.service")
            command = "cp -p {} {}".format(dhcpcd_conf_ap, dhcpcd_conf)
            self.__send_command(command)
            self.__send_command("systemctl daemon-reload")
            self.__send_command("systemctl restart dhcpcd.service")
            self.__send_command("systemctl start dnsmasq.service")
            self.__send_command("systemctl start hostapd.service")
        else:
            self.__send_command("rm -f /etc/systemd/system/multi-user.target.wants/hostapd.service")
            self.__send_command("rm -f /etc/systemd/system/multi-user.target.wants/dnsmasq.service")
            self.__send_command("systemctl stop hostapd.service")
            self.__send_command("systemctl stop dnsmasq.service")
            command = "cp -p {} {}".format(dhcpcd_conf_sta, dhcpcd_conf)
            self.__send_command(command)
            self.__send_command("systemctl daemon-reload")
            self.__send_command("systemctl restart dhcpcd.service")

    # Private function to check WLAN status
    #
    # "rfkill list wifi" output:
    #     0: phy0: Wireless LAN
    #             Soft blocked: yes|no
    #             Hard blocked: yes|no
    #
    def __check_wlan_status(self):
        stdout = self.__send_command("rfkill list wifi")
        for str in stdout.splitlines():
            str = str.strip()
            if re.match("Hard", str):
                if str.split(":")[1].strip() == "yes":
                    raise WlanManagerError("WLAN blocked by hardware")
            elif re.match("Soft", str):
                if str.split(":")[1].strip() == "yes":
                    raise WlanManagerError("WLAN blocked by software")

    # Private function to parse output of "iwlist wlan0 scan" for available networks
    #
    # Returns: list of tuples (SSID: string, secured: boolean) of available networks
    #
    def __find_cells(self, stdout):
        list = []
        name = None
        secured = False

        for str in stdout.splitlines():
            str = str.strip()

            # find new cell
            if re.match("Cell\s([0-9]*)", str):
                # add previous network entry to list
                if name is not None:
                    entry = (name, secured)
                    if entry not in list:
                        list.append(entry)
                    name = None
                    secured = False

            # set SSID of new cell
            if re.search("ESSID", str):
                name = re.findall('[^"]*', str)[2]
                if name == "":
                    name = None

            # set security setting of new cell
            if re.search("WPA", str):
                secured = True

        # add last network entry to list
        if name is not None:
            entry = (name, secured)
            list.append(entry)

        return list

    # Private function to restore WPA supplicant config file
    #
    def __restore_wpa_config(self):
        if not os.path.exists(wpa_conf_orig):
            return

        command = "cp -p {} {}".format(wpa_conf_orig, wpa_conf)
        self.__send_command(command)

    # Public function to enable/disable WLAN
    #
    def enable_wlan(self, enable):
        command = "rfkill unblock wifi" if enable else "rfkill block wifi"
        self.__send_command(command)

    # Public function to show current connection status
    #
    # Returns: tuple (mode: string, SSID: string, secured: boolean) indicating connection status
    #
    def current(self):
        self.__check_wlan_status()

        if self.__is_ap_mode():
            print("Mode: AP")
            return "ap", None, None

        print("Mode: Station")
        name = None
        secured = False

        stdout = self.__send_command("wpa_cli -i wlan0 status")
        for str in stdout.splitlines():
            str = str.strip()
            if re.match("ssid", str):
                name = str.split("=")[1].strip()
            elif re.match("wpa_state=COMPLETED", str):
                secured = True

        if name is None:
            name = ""
            print("No connection")
        else:
            security = "secured" if secured else "public"
            print("SSID: {} ({})".format(name, security))

        return "station", name, secured

    # Public function to enable/disable AP mode
    #
    def ap_mode(self, enable):
        self.__check_wlan_status()

        if enable and self.__is_ap_mode():
            return

        if not enable and not self.__is_ap_mode():
            return

        if enable:
            self.__restore_wpa_config()
            self.__send_command("wpa_cli -i wlan0 reconfigure")

        self.__enable_ap_mode(enable)

    # Public function to list available networks
    #
    # Returns: list of tuples (SSID: string, secured: boolean) of available networks
    #
    def list(self):
        self.__check_wlan_status()

        # scan for available networks
        stdout = self.__send_command("iwlist wlan0 scan")

        # output available networks to console
        list = self.__find_cells(stdout)
        for name, secured in list:
            security = "secured" if secured else "public"
            print("{} ({})".format(name, security))

        return list

    # Public function to connect to specified SSID with supplied password
    #
    def connect(self, ssid=None, password=None, timeout=30):
        self.__check_wlan_status()

        if ssid is None:
            raise WlanManagerError("No SSID specified")

        self.ap_mode(False)

        # update WPA supplicant config file to add specified SSID entry
        command = "wpa_passphrase {:s} {:s} >> {:s}".format(ssid, password, wpa_conf)
        self.__send_command(command)

        # reconfigure WLAN interface
        stdout = self.__send_command("wpa_cli -i wlan0 reconfigure")

        print(
            'Configured WLAN for connection to "{:s}", status: {:s}'.format(
                ssid, stdout
            )
        )

        # verify connection
        elapsed = 0
        connected = False
        while elapsed < timeout and not connected:
            stdout = self.__send_command("ifconfig wlan0")
            for str in stdout.splitlines():
                str = str.strip()
                if re.match("inet\s([0-9]+\.){3}[0-9]+\s", str):
                    connected = True
            if not connected:
                time.sleep(1)
                elapsed += 1
        if connected:
            print('Connection to "{:s}" established'.format(ssid))
        else:
            self.__restore_wpa_config()
            raise WlanManagerError(
                'Failed to establish connection to "{}" within {} seconds'.format(
                    ssid, timeout
                )
            )

    # Public function to disconnect from network
    #
    def disconnect(self):
        self.__restore_wpa_config()
        self.__send_command("wpa_cli -i wlan0 reconfigure")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WLAN Connectivity Manager")

    parser.add_argument(
        "--on", action="store_true", help="turn on WLAN"
    )

    parser.add_argument(
        "--off", action="store_true", help="turn off WLAN"
    )

    parser.add_argument(
        "--ap", action="store_true", help="access point mode"
    )

    parser.add_argument(
        "--sta", action="store_true", help="station mode"
    )

    parser.add_argument(
        "-c", "--current", action="store_true", help="current connection status"
    )

    parser.add_argument(
        "-l", "--list", action="store_true", help="list available networks"
    )

    parser.add_argument(
        "-s",
        "--ssid",
        default=None,
        help="connect to specified service set identifier (SSID)",
    )

    parser.add_argument(
        "-p",
        "--password",
        default=None,
        help="password for SSID to connect to",
    )

    parser.add_argument(
        "-t",
        "--timeout",
        default=30,
        help="timeout in seconds for establishing connection (default = 30s)",
    )

    parser.add_argument(
        "-d", "--disconnect", action="store_true", help="disconnect from network"
    )

    args = parser.parse_args()

    wm = WlanManager()

    if args.on == True:
        try:
            wm.enable_wlan(True)
        except WlanManagerError as err:
            print("Error: {}".format(err))
        finally:
            sys.exit()

    elif args.off == True:
        try:
            wm.enable_wlan(False)
        except WlanManagerError as err:
            print("Error: {}".format(err))
        finally:
            sys.exit()

    try:
        wm.enable_wlan(True)
    except WlanManagerError as err:
        print("Error: {}".format(err))
        sys.exit()

    if args.ap == True:
        try:
            wm.ap_mode(True)
        except WlanManagerError as err:
            print("Error: {}".format(err))

    elif args.sta == True:
        try:
            wm.ap_mode(False)
        except WlanManagerError as err:
            print("Error: {}".format(err))

    elif args.current == True:
        try:
            wm.current()
        except WlanManagerError as err:
            print("Error: {}".format(err))

    elif args.list == True:
        try:
            wm.list()
        except WlanManagerError as err:
            print("Error: {}".format(err))

    elif args.ssid != None:
        try:
            wm.connect(args.ssid, args.password, args.timeout)
        except WlanManagerError as err:
            print("Error: {}".format(err))

    elif args.disconnect == True:
        try:
            wm.disconnect()
        except WlanManagerError as err:
            print("Error: {}".format(err))

    else:
        parser.print_help()
        sys.exit()
