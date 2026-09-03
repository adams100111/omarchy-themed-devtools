<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>name</key><string>Omarchy</string>
  <key>settings</key>
  <array>
    <dict><key>settings</key><dict>
      <key>background</key><string>{{ background }}</string>
      <key>foreground</key><string>{{ foreground }}</string>
      <key>caret</key><string>{{ accent }}</string>
      <key>selection</key><string>{{ selection }}</string>
      <key>lineHighlight</key><string>{{ lighter_background }}</string>
    </dict></dict>
    <dict><key>name</key><string>Comment</string><key>scope</key><string>comment</string>
      <key>settings</key><dict><key>foreground</key><string>{{ muted }}</string></dict></dict>
    <dict><key>name</key><string>String</string><key>scope</key><string>string</string>
      <key>settings</key><dict><key>foreground</key><string>{{ green }}</string></dict></dict>
    <dict><key>name</key><string>Number</string><key>scope</key><string>constant.numeric</string>
      <key>settings</key><dict><key>foreground</key><string>{{ orange }}</string></dict></dict>
    <dict><key>name</key><string>Constant</string><key>scope</key><string>constant.language</string>
      <key>settings</key><dict><key>foreground</key><string>{{ orange }}</string></dict></dict>
    <dict><key>name</key><string>Keyword</string><key>scope</key><string>keyword, storage.type</string>
      <key>settings</key><dict><key>foreground</key><string>{{ magenta }}</string></dict></dict>
    <dict><key>name</key><string>Function</string><key>scope</key><string>entity.name.function</string>
      <key>settings</key><dict><key>foreground</key><string>{{ blue }}</string></dict></dict>
    <dict><key>name</key><string>Class</string><key>scope</key><string>entity.name.class, entity.name.type</string>
      <key>settings</key><dict><key>foreground</key><string>{{ yellow }}</string></dict></dict>
    <dict><key>name</key><string>Variable</string><key>scope</key><string>variable</string>
      <key>settings</key><dict><key>foreground</key><string>{{ foreground }}</string></dict></dict>
    <dict><key>name</key><string>Tag</string><key>scope</key><string>entity.name.tag</string>
      <key>settings</key><dict><key>foreground</key><string>{{ red }}</string></dict></dict>
    <dict><key>name</key><string>Invalid</string><key>scope</key><string>invalid</string>
      <key>settings</key><dict><key>foreground</key><string>{{ bright_red }}</string></dict></dict>
  </array>
  <key>uuid</key><string>6f1a4c0e-0f2f-4c1e-9a3d-omarchythemed</string>
</dict>
</plist>
