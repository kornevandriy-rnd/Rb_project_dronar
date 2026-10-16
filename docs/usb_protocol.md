# USB UART control protocol

This document can be sent to the manufacturer as the command reference for controlling the device over USB.

## Transport

- Physical path: host USB -> USB-UART converter -> ESP UART firmware.
- UART speed: `921600` baud.
- Data format: `8N1`.
- Command format: one JSON object per line.
- Line ending: `\n` or `\r\n`.
- Maximum line length: 512 characters.
- Non-JSON lines are ignored.

Replace the serial port name in the examples with the actual port on the test computer:

- Linux: `/dev/ttyUSB0` or `/dev/ttyACM0`
- Windows: `COM3`
- macOS: `/dev/tty.usbserial-0001` or `/dev/cu.usbserial-0001`

## Commands

| Command | Value / description | Linux example | Windows PowerShell example | macOS example |
|---|---|---|---|---|
| `brightness` | Image brightness. Range: `0..100`. Default: `50`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"brightness":60}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"brightness":60}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"brightness":60}\n' > /dev/tty.usbserial-0001` |
| `contrast` | Image contrast. Range: `0..100`. Default: `50`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"contrast":40}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"contrast":40}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"contrast":40}\n' > /dev/tty.usbserial-0001` |
| `palette` | Color palette. Range: `0..11`. Default: `0`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"palette":2}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"palette":2}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"palette":2}\n' > /dev/tty.usbserial-0001` |
| `scene` | Scene mode. Range: `0..9`. Default: `3`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"scene":3}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"scene":3}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"scene":3}\n' > /dev/tty.usbserial-0001` |
| `dde` | Digital detail enhancement. Range: `0..100`. Default: `65`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"dde":65}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"dde":65}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"dde":65}\n' > /dev/tty.usbserial-0001` |
| `anr` | Spatial noise reduction. Range: `0..100`. Default: `50`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"anr":50}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"anr":50}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"anr":50}\n' > /dev/tty.usbserial-0001` |
| `shutter_period` | Automatic shutter interval in minutes. Range: `1..30`. Default: `1`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"shutter_period":5}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"shutter_period":5}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"shutter_period":5}\n' > /dev/tty.usbserial-0001` |
| `shutter_auto` | Automatic shutter calibration. Boolean. Default: `true`. Set to `false` to disable automatic shutter activations; PWM and serial manual calibration remain available. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"shutter_auto":false}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"shutter_auto":false}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"shutter_auto":false}\n' > /dev/tty.usbserial-0001` |
| `shutter:close` | Close the shutter manually. Disable automatic shutter mode separately when persistent manual control is required. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"shutter":"close"}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"shutter":"close"}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"shutter":"close"}\n' > /dev/tty.usbserial-0001` |
| `shutter:open` | Open the shutter manually. Disable automatic shutter mode separately when persistent manual control is required. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"shutter":"open"}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"shutter":"open"}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"shutter":"open"}\n' > /dev/tty.usbserial-0001` |
| `tnr` | Temporal noise reduction. Range: `0..100`. Default: `50`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"tnr":50}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"tnr":50}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"tnr":50}\n' > /dev/tty.usbserial-0001` |
| `egi` | Edge gain / image enhancement. Range: `0..100`. Default: `50`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"egi":50}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"egi":50}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"egi":50}\n' > /dev/tty.usbserial-0001` |
| `cmd:get` | Read device information, current parameters, and default values. Request JSON: `{"cmd":"get"}`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"cmd":"get"}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"cmd":"get"}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"cmd":"get"}\n' > /dev/tty.usbserial-0001` |
| `cmd:set_video_output` | Select digital video output. `output`: `mipi`, `dvp` (alias: `digital`), `usb`, `bt656`, or `off`; `fps`: `30` or `60`; optional `persist`: `true` saves the format in the thermal module. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"cmd":"set_video_output","output":"mipi","fps":30}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"cmd":"set_video_output","output":"mipi","fps":30}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"cmd":"set_video_output","output":"mipi","fps":30}\n' > /dev/tty.usbserial-0001` |
| `btn:save` | Save current settings to flash memory. Request JSON: `{"btn":"save"}`. | `stty -F /dev/ttyUSB0 921600 raw -echo; printf '{"btn":"save"}\n' > /dev/ttyUSB0` | `$p=New-Object System.IO.Ports.SerialPort 'COM3',921600; $p.Open(); $p.WriteLine('{"btn":"save"}'); $p.Close()` | `stty -f /dev/tty.usbserial-0001 921600 raw -echo; printf '{"btn":"save"}\n' > /dev/tty.usbserial-0001` |

Multiple parameters can be sent in one JSON object:

```json
{"brightness":60,"contrast":40,"palette":2}
```

The device applies supported parameters immediately.

### Manual calibration

Send this command followed by a newline to start calibration with shutter closing:

```json
{"cmd":"calibrate"}
```

This calls the same camera calibration operation as the PWM trigger and works
even when `shutter_auto` is `false`. The 5 second repeat guard applies only to
PWM triggers; space serial calibration requests at least 5 seconds apart.
Send calibration as a separate command without additional settings.

On a successful camera command, the response is:

```json
{"ok":true,"cmd":"calibrate"}
```

If the camera command fails, the response is `{"ok":false,"err":"camera_error"}`.
Diagnostic lines such as `Calib start` and `Calib end` may precede the JSON response.

### Digital video output

Switch to MIPI at 30 Hz:

```json
{"cmd":"set_video_output","output":"mipi","fps":30}
```

Switch to the parallel digital DVP output at 30 Hz:

```json
{"cmd":"set_video_output","output":"digital","fps":30}
```

Disable digital video output:

```json
{"cmd":"set_video_output","output":"off"}
```

Add `"persist":true` to retain the selected output after restarting the thermal
module. This invokes the module's special video-output save operation, which saves
both its current digital and analog output formats.

## Responses

After a parameter update, the device returns the actual applied value:

```json
{"ok":true,"params":{"brightness":60}}
```

After a manual shutter command, the device returns:

```json
{"ok":true,"shutter":"close"}
```

For `{"cmd":"get"}`, the device returns:

```json
{
  "ok": true,
  "info": {
    "name": "...",
    "version": "...",
    "serial": "..."
  },
  "params": {
    "brightness": 50,
    "contrast": 50,
    "palette": 0,
    "scene": 3,
    "dde": 65,
    "anr": 50,
    "shutter_period": 1,
    "shutter_auto": true,
    "tnr": 50,
    "egi": 50
  },
  "defaults": {
    "brightness": 50,
    "contrast": 50,
    "palette": 0,
    "scene": 3,
    "dde": 65,
    "anr": 50,
    "shutter_period": 1,
    "shutter_auto": true,
    "tnr": 50,
    "egi": 50
  }
}
```

For `{"btn":"save"}`, the device returns:

```json
{"ok":true,"saved":true}
```

For a video output change, the device returns:

```json
{"ok":true,"video_output":{"output":"mipi","enabled":true,"fps":30,"persisted":false}}
```

The response is sent only after the synchronous camera or flash operation has completed.

## Errors

Invalid JSON:

```json
{"ok":false,"err":"json_parse"}
```

Line longer than 512 characters:

```json
{"ok":false,"err":"line_too_long"}
```

Other possible errors are `invalid_value`, `unknown_field`, `unknown_command`,
`camera_error`, `flash_error`, `object_required`, and `empty_command`.

## LED indication

GPIO 27 indicates the result after each completed command:

- one 50 ms flash: success;
- two 80 ms flashes: invalid JSON or command;
- one 300 ms flash: camera or flash failure.

The LED timing is non-blocking and does not delay the UART response. The PWM input is
reserved for manual shutter calibration and is protected by a 5 second repeat guard.

### Video rotation

`rotation` accepts integer degrees: **0 or 180** (default: 0).

```json
{"rotation":180}
{"rotation":0}
{"rotation":180,"btn":"save"}
```

`cmd:get` includes `rotation` in `params` and `defaults`. Saving persists it in
ESP32 flash and reapplies it after restart. Older saved settings are migrated
without losing their values.

90 and 270 degrees are **not supported** by the documented MINI2 control
protocol and return `invalid_value`, as do other unsupported angles and types.
The ESP32 firmware controls the module over I2C; it does not process video frames.
Quarter-turn rotation requires processing in a video receiver or different
module firmware with a documented rotation command. SDK `rotate_left_90` and
`rotate_right_90` operate on host frame buffers, not on the module output.

180 degrees uses MINI2 mirror + flip (`10 10 43 00 03 ...`), replacing any
existing mirror/flip state. The manufacturer's instruction set warns that
mirror/flip is unavailable during electronic zoom, image freeze, or external
synchronization. Confirm the image on the target hardware in the intended mode.
