# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from platform import system
from os import makedirs
from os.path import isdir, isfile, join

from SCons.Script import (COMMAND_LINE_TARGETS, AlwaysBuild, Builder, Default,
                          DefaultEnvironment)

env = DefaultEnvironment()
platform = env.PioPlatform()

env.Replace(
    ARFLAGS=["rc"],

    ASFLAGS=["-x", "assembler-with-cpp"],

    CCFLAGS=[
        "-Os",  # optimize for size
        "-Wall",  # show warnings
        "-ffunction-sections",  # place each function in its own section
        "-fdata-sections"
    ],

    CXXFLAGS=[
        "-fno-exceptions",
        "-felide-constructors"
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU"),
        "LAYOUT_US_ENGLISH"
    ],

    LINKFLAGS=[
        "-Os",
        "-Wl,--gc-sections,--relax"
    ],

    LIBS=["m"],

    PROGSUFFIX=".elf"
)

# Allow user to override via pre:script
if env.get("PROGNAME", "program") == "program":
    env.Replace(PROGNAME="firmware")

if "BOARD" in env and env.BoardConfig().get("build.core") == "teensy":
    env.Replace(
        AR="avr-ar",
        AS="avr-as",
        CC="avr-gcc",
        CXX="avr-g++",
        GDB="avr-gdb",
        OBJCOPY="avr-objcopy",
        RANLIB="avr-ranlib",
        SIZETOOL="avr-size",
        SIZEPRINTCMD='$SIZETOOL --mcu=$BOARD_MCU -C -d $SOURCES'
    )
    env.Append(
        CCFLAGS=[
            "-mmcu=$BOARD_MCU"
        ],

        CXXFLAGS=[
            "-std=gnu++11"
        ],

        LINKFLAGS=[
            "-mmcu=$BOARD_MCU"
        ],

        BUILDERS=dict(
            ElfToEep=Builder(
                action=env.VerboseAction(" ".join([
                    "$OBJCOPY",
                    "-O",
                    "ihex",
                    "-j",
                    ".eeprom",
                    '--set-section-flags=.eeprom="alloc,load"',
                    "--no-change-warnings",
                    "--change-section-lma",
                    ".eeprom=0",
                    "$SOURCES",
                    "$TARGET"
                ]), "Building $TARGET"),
                suffix=".eep"
            ),

            ElfToHex=Builder(
                action=env.VerboseAction(" ".join([
                    "$OBJCOPY",
                    "-O",
                    "ihex",
                    "-R",
                    ".eeprom",
                    "$SOURCES",
                    "$TARGET"
                ]), "Building $TARGET"),
                suffix=".hex"
            )
        )
    )
elif "BOARD" in env and env.BoardConfig().get("build.core") == "teensy3":
    env.Replace(
        AR="arm-none-eabi-ar",
        AS="arm-none-eabi-as",
        CC="arm-none-eabi-gcc",
        CXX="arm-none-eabi-g++",
        GDB="arm-none-eabi-gdb",
        OBJCOPY="arm-none-eabi-objcopy",
        RANLIB="arm-none-eabi-gcc-ranlib",
        SIZETOOL="arm-none-eabi-size",
        SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES'
    )
    if "arduino" in env.get("PIOFRAMEWORK", []):
        env.Replace(
            AR="arm-none-eabi-gcc-ar",
            RANLIB="$AR"
        )
    env.Append(
        CCFLAGS=[
            "-mthumb",
            "-mcpu=%s" % env.BoardConfig().get("build.cpu"),
            "-nostdlib",
            "-fsingle-precision-constant"
        ],

        CXXFLAGS=[
            "-fno-rtti",
            "-std=gnu++14"
        ],

        RANLIBFLAGS=["-s"],

        LIBS=["stdc++"],

        LINKFLAGS=[
            "-mthumb",
            "-mcpu=%s" % env.BoardConfig().get("build.cpu"),
            "-Wl,--defsym=__rtc_localtime=$UNIX_TIME",
            "-fsingle-precision-constant"
        ],

        BUILDERS=dict(
            ElfToBin=Builder(
                action=env.VerboseAction(" ".join([
                    "$OBJCOPY",
                    "-O",
                    "binary",
                    "$SOURCES",
                    "$TARGET"
                ]), "Building $TARGET"),
                suffix=".bin"
            ),

            ElfToHex=Builder(
                action=env.VerboseAction(" ".join([
                    "$OBJCOPY",
                    "-O",
                    "ihex",
                    "-R",
                    ".eeprom",
                    "$SOURCES",
                    "$TARGET"
                ]), "Building $TARGET"),
                suffix=".hex"
            )
        )
    )
    if env.BoardConfig().id_ in ("teensy35", "teensy36"):
        env.Append(
            CCFLAGS=[
                "-mfloat-abi=hard",
                "-mfpu=fpv4-sp-d16"
            ],

            LINKFLAGS=[
                "-mfloat-abi=hard",
                "-mfpu=fpv4-sp-d16"
            ]
        )

env.Append(
    ASFLAGS=env.get("CCFLAGS", [])[:]
)

#
# Target: Build executable and linkable firmware
#

target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_firm = join("$BUILD_DIR", "${PROGNAME}.hex")
else:
    target_elf = env.BuildProgram()
    target_firm = env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf)

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

#
# Target: Print binary size
#

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

#
# Target: Upload by default firmware file
#

# Force Teensy CLI when Teensy App is not available (Linux ARM)
if env.subst("$UPLOAD_PROTOCOL") == "teensy-gui" and not isfile(
        join(
            platform.get_package_dir("tool-teensy") or "",
            "teensy_post_compile.exe"
            if system() == "Windows" else "teensy_post_compile")):
    env.Replace(UPLOAD_PROTOCOL="teensy-cli")

upload_protocol = env.subst("$UPLOAD_PROTOCOL")
upload_actions = []

if upload_protocol.startswith("jlink"):

    def _jlink_cmd_script(env, source):
        build_dir = env.subst("$BUILD_DIR")
        if not isdir(build_dir):
            makedirs(build_dir)
        script_path = join(build_dir, "upload.jlink")
        commands = ["h", "loadfile %s" % source, "r", "q"]
        with open(script_path, "w") as fp:
            fp.write("\n".join(commands))
        return script_path

    env.Replace(
        __jlink_cmd_script=_jlink_cmd_script,
        UPLOADER="JLink.exe" if system() == "Windows" else "JLinkExe",
        UPLOADERFLAGS=[
            "-device", env.BoardConfig().get("debug", {}).get("jlink_device"),
            "-speed", "4000",
            "-if", ("jtag" if upload_protocol == "jlink-jtag" else "swd"),
            "-autoconnect", "1"
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS -CommanderScript ${__jlink_cmd_script(__env__, SOURCE)}"
    )
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

elif upload_protocol == "teensy-cli":
    env.Replace(
        REBOOTER="teensy_reboot",
        UPLOADER="teensy_loader_cli",
        UPLOADERFLAGS=[
            "-mmcu=$BOARD_MCU",
            "-w",  # wait for device to appear
            "-s",  # soft reboot if device not online
            "-v"  # verbose output
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS $SOURCES"
    )
    upload_actions = [
        env.VerboseAction("$REBOOTER -s", "Rebooting..."),
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")
    ]

elif upload_protocol == "teensy-gui":
    env.Replace(
        REBOOTER="teensy_reboot",
        UPLOADER="teensy_post_compile",
        UPLOADERFLAGS=[
            "-file=${PROGNAME}", '-path="$BUILD_DIR"',
            '-tools=%s' % (platform.get_package_dir("tool-teensy") or "")
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS"
    )
    upload_actions = [
        env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE"),
        env.VerboseAction("$REBOOTER", "Rebooting...")
    ]

# custom upload tool
elif "UPLOADCMD" in env:
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

else:
    sys.stderr.write("Warning! Unknown upload protocol %s\n" % upload_protocol)

AlwaysBuild(env.Alias("upload", target_firm, upload_actions))

#
# Default targets
#

Default([target_buildprog, target_size])
