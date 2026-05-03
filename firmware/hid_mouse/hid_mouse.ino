// hid_mouse — Composite HID (mouse + keyboard) for the human-like
// AI competition.
//
// Identifies as a real USB HID device (VID/PID + descriptors injected
// at compile time). Receives ASCII commands over USB serial and
// produces real HID reports indistinguishable from a physical mouse +
// keyboard at the OS Raw Input level.
//
// **v0.4 — relative-delta mouse.** Earlier versions used HID-Project's
// AbsoluteMouse (digitizer / tablet HID descriptor). Lineage Classic
// filters tablet-style absolute pointer reports, so hover events never
// reached the game's tooltip system. The standard ``Mouse`` class
// uses a relative-delta descriptor that matches a regular consumer
// USB mouse — Lineage treats those reports identically to a physical
// mouse.
//
// Protocol (line-terminated by \n):
//   MR dx dy   mouse: move by relative delta. dx/dy are clamped on the
//              firmware side to ±127 per report (HID limit). Panel
//              must chunk longer moves into multiple MR commands.
//   C          mouse: left click
//   R          mouse: right click
//   D          mouse: left button press (hold)
//   U          mouse: left button release
//   K name     keyboard: tap (press + release) the named key
//   KD name    keyboard: hold the named key down
//   KU name    keyboard: release key
//   P          ping        (responds: pong)
//   V          version     (responds: hid_mouse v<n>)
//
// Each command responds with `ok` on success or `err <reason>` on
// failure.

#include <HID-Project.h>

const unsigned long BAUD = 115200;
const char VERSION[] = "hid_mouse v0.5";  // bumped: ASCII→HID keymap fix
const size_t BUFSIZE = 64;

char buf[BUFSIZE];
size_t bufLen = 0;

void setup() {
  Serial.begin(BAUD);
  Mouse.begin();           // relative-delta HID mouse
  BootKeyboard.begin();
}

void loop() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      buf[bufLen] = '\0';
      handleLine(buf);
      bufLen = 0;
      continue;
    }
    if (bufLen < BUFSIZE - 1) {
      buf[bufLen++] = c;
    } else {
      bufLen = 0;
      Serial.println(F("err overflow"));
    }
  }
}

KeyboardKeycode lookupKey(const char* name) {
  if (!name || !name[0]) return KEY_RESERVED;
  // Single-char: convert ASCII a-z / 0-9 to proper HID usage codes.
  // Earlier (v0.4) this cast the ASCII byte directly to
  // KeyboardKeycode — e.g. 'm' (0x6D) became HID code 0x6D which is
  // not the M key, so letter keys silently did nothing in-game. Tab
  // and F-keys worked because they used the KEY_TAB / KEY_F1
  // constants directly without going through this path.
  if (name[1] == '\0') {
    char c = name[0];
    if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
    if (c >= 'a' && c <= 'z') {
      return (KeyboardKeycode)(KEY_A + (c - 'a'));
    }
    if (c >= '1' && c <= '9') {
      return (KeyboardKeycode)(KEY_1 + (c - '1'));
    }
    if (c == '0') return KEY_0;
    if (c == ' ') return (KeyboardKeycode)0x2C;  // HID space
  }
  if (!strcasecmp(name, "tab"))       return KEY_TAB;
  if (!strcasecmp(name, "esc"))       return KEY_ESC;
  if (!strcasecmp(name, "escape"))    return KEY_ESC;
  if (!strcasecmp(name, "enter"))     return KEY_ENTER;
  if (!strcasecmp(name, "return"))    return KEY_ENTER;
  if (!strcasecmp(name, "space"))     return (KeyboardKeycode)0x2C;  // HID space
  if (!strcasecmp(name, "backspace")) return KEY_BACKSPACE;
  if (!strcasecmp(name, "up"))        return KEY_UP_ARROW;
  if (!strcasecmp(name, "down"))      return KEY_DOWN_ARROW;
  if (!strcasecmp(name, "left"))      return KEY_LEFT_ARROW;
  if (!strcasecmp(name, "right"))     return KEY_RIGHT_ARROW;
  if (!strcasecmp(name, "home"))      return KEY_HOME;
  if (!strcasecmp(name, "end"))       return KEY_END;
  if (!strcasecmp(name, "pageup"))    return KEY_PAGE_UP;
  if (!strcasecmp(name, "pagedown"))  return KEY_PAGE_DOWN;
  if (!strcasecmp(name, "insert"))    return KEY_INSERT;
  if (!strcasecmp(name, "delete"))    return KEY_DELETE;
  if (!strcasecmp(name, "shift"))     return KEY_LEFT_SHIFT;
  if (!strcasecmp(name, "ctrl"))      return KEY_LEFT_CTRL;
  if (!strcasecmp(name, "alt"))       return KEY_LEFT_ALT;
  if (!strncasecmp(name, "f", 1)) {
    int n = atoi(name + 1);
    if (n >= 1 && n <= 12) {
      return (KeyboardKeycode)(KEY_F1 + (n - 1));
    }
  }
  return KEY_RESERVED;
}

KeyboardKeycode parseKeyCommand(const char* line, char* outVerb) {
  *outVerb = line[0];
  size_t verbLen = 1;
  if (line[1] && line[1] != ' ') {
    *outVerb = line[1];
    verbLen = 2;
  }
  const char* p = line + verbLen;
  while (*p == ' ') p++;
  if (!*p) return KEY_RESERVED;
  return lookupKey(p);
}

void handleLine(const char* line) {
  if (line[0] == '\0') return;

  switch (line[0]) {
    case 'P':
      Serial.println(F("pong"));
      return;

    case 'V':
      Serial.println(VERSION);
      return;

    case 'C':
      Mouse.click(MOUSE_LEFT);
      Serial.println(F("ok"));
      return;

    case 'R':
      Mouse.click(MOUSE_RIGHT);
      Serial.println(F("ok"));
      return;

    case 'D':
      Mouse.press(MOUSE_LEFT);
      Serial.println(F("ok"));
      return;

    case 'U':
      Mouse.release(MOUSE_LEFT);
      Serial.println(F("ok"));
      return;

    case 'M': {
      // MR dx dy — relative move. dx/dy are signed; we clamp to ±127
      // per HID report. The panel MUST chunk longer moves itself
      // (sending multiple MRs); doing it on the AVR adds latency.
      if (line[1] != 'R') {
        Serial.println(F("err unknown_cmd M"));
        return;
      }
      const char* p = line + 2;
      while (*p == ' ') p++;
      char* endX = nullptr;
      long dx = strtol(p, &endX, 10);
      if (endX == p) { Serial.println(F("err parse_dx")); return; }
      while (*endX == ' ') endX++;
      char* endY = nullptr;
      long dy = strtol(endX, &endY, 10);
      if (endY == endX) { Serial.println(F("err parse_dy")); return; }
      if (dx < -127 || dx > 127 || dy < -127 || dy > 127) {
        Serial.println(F("err range"));
        return;
      }
      Mouse.move((signed char)dx, (signed char)dy);
      Serial.println(F("ok"));
      return;
    }

    case 'K': {
      char verb = 'K';
      KeyboardKeycode code = parseKeyCommand(line, &verb);
      if (code == KEY_RESERVED) {
        Serial.println(F("err unknown_key"));
        return;
      }
      if (verb == 'K') {
        BootKeyboard.press(code);
        BootKeyboard.release(code);
      } else if (verb == 'D') {
        BootKeyboard.press(code);
      } else if (verb == 'U') {
        BootKeyboard.release(code);
      } else {
        Serial.println(F("err bad_verb"));
        return;
      }
      Serial.println(F("ok"));
      return;
    }

    default:
      Serial.print(F("err unknown_cmd "));
      Serial.println(line[0]);
  }
}
