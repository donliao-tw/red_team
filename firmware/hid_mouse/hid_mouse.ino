// hid_mouse — Absolute-positioning HID mouse for the human-like AI competition.
//
// Identifies as a real USB HID mouse (VID/PID injected at compile time).
// Receives ASCII commands over USB serial and produces real HID reports
// indistinguishable from a physical mouse at the OS Raw Input level.
//
// Protocol (line-terminated by \n):
//   M x y    — move to absolute (x, y) where 0 <= x,y <= 32767
//   C        — left click
//   R        — right click
//   D        — left button press (hold)
//   U        — left button release
//   P        — ping        (responds: pong)
//   V        — version     (responds: hid_mouse v<n>)
//
// Each command responds with `ok` on success or `err <reason>` on failure.

#include <HID-Project.h>

const unsigned long BAUD = 115200;
const char VERSION[] = "hid_mouse v0.1";
const size_t BUFSIZE = 64;

char buf[BUFSIZE];
size_t bufLen = 0;

void setup() {
  Serial.begin(BAUD);
  AbsoluteMouse.begin();
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
      // Overflow — discard until newline.
      bufLen = 0;
      Serial.println(F("err overflow"));
    }
  }
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
      AbsoluteMouse.click(MOUSE_LEFT);
      Serial.println(F("ok"));
      return;

    case 'R':
      AbsoluteMouse.click(MOUSE_RIGHT);
      Serial.println(F("ok"));
      return;

    case 'D':
      AbsoluteMouse.press(MOUSE_LEFT);
      Serial.println(F("ok"));
      return;

    case 'U':
      AbsoluteMouse.release(MOUSE_LEFT);
      Serial.println(F("ok"));
      return;

    case 'M': {
      // Expected form: "M x y" — leading 'M ' then two ints.
      const char* p = line + 1;
      while (*p == ' ') p++;
      char* endX = nullptr;
      long x = strtol(p, &endX, 10);
      if (endX == p) { Serial.println(F("err parse_x")); return; }
      while (*endX == ' ') endX++;
      char* endY = nullptr;
      long y = strtol(endX, &endY, 10);
      if (endY == endX) { Serial.println(F("err parse_y")); return; }
      if (x < 0 || x > 32767 || y < 0 || y > 32767) {
        Serial.println(F("err range"));
        return;
      }
      AbsoluteMouse.moveTo((int)x, (int)y);
      Serial.println(F("ok"));
      return;
    }

    default:
      Serial.print(F("err unknown_cmd "));
      Serial.println(line[0]);
  }
}
