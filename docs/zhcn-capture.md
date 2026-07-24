# Raw zhCN TTS capture

`src.tools.tts_capture` records the UTF-8 messages that `saapi64.dll` sends to the D4LF Windows named
pipe. It is intended for collecting untranslated zhCN samples before parser or localization work.

The desktop App exposes the same format through an optional `Diagnostics` tab. Enable `Show Diagnostic Capture Tab`
under `Settings > Advanced` when it is needed. The setting is disabled by default. App capture is the preferred
collection path; the command-line recorder remains a fallback.

## Safety and scope

**This recorder never launches or controls Diablo IV. It performs no mouse or keyboard actions.** It
only waits on `\\.\pipe\d4lf` and stores messages that the game has already chosen to send through
`saapi64.dll`.

**本录制工具绝不会启动或控制《暗黑破坏神 IV》，也不会执行任何鼠标或键盘操作。**

The recorder does not import the item parser, infer English item boundaries, move the pointer, press
keys, take screenshots, or change game settings. It captures all pipe messages, not only item text.

## Before recording

- Use Windows with the repository's normal Python environment.
- Install and sign `saapi64.dll` using the existing TTS setup described in the project README.
- Configure the game itself for the `zhCN` locale and its accessibility TTS output.
- For App capture, close any other TTS listener, enable `Show Diagnostic Capture Tab` under `Settings > Advanced`,
  and use D4LF's `Diagnostics` tab.
- For CLI capture, close D4LF and every other TTS listener. Only one process can own `\\.\pipe\d4lf` at a time.
- Note the exact game build. Both capture paths require it so captures are not detached from their source build.

## Capture in the App

Enable `Show Diagnostic Capture Tab` under `Settings > Advanced`, open `Diagnostics`, select the locale, game build,
category, and game area, then select `Start Capture`. The App taps the raw TTS payload before normal parsing and
blocks new game-input actions until `Stop and Save` is selected. It saves timestamped JSONL and replay files under
`%USERPROFILE%\.d4lf\captures` and never uploads them.

The recorder should be active before collecting samples. Start and operate the game yourself; neither capture path
starts or controls it for you.

## Run the recorder

From PowerShell in the repository root:

```powershell
uv run python -m src.tools.tts_capture `
  --output .\captures\zhCN-3.1.0.72810.jsonl `
  --locale zhCN `
  --game-build 3.1.0.72810 `
  --session-meta area=inventory `
  --session-meta character=rogue
```

`--session-meta KEY=VALUE` is optional and repeatable. Use it for capture context that is not already
represented by the locale and build. Do not put personal or secret information in metadata.

Continue using the game normally. Every message emitted by the DLL is recorded without requiring a
hover, click, key press, or other action from the recorder. Press `Ctrl+C` in the recorder terminal to
stop cleanly.

## Output format

The output is UTF-8 JSON Lines. Each line is one complete DLL message:

```json
{"schema_version":1,"locale":"zhCN","game_build":"2.4.1.12345","session":{"id":"00000000-0000-4000-8000-000000000000","started_at":"2000-01-01T00:00:00.000Z","pipe_name":"\\\\.\\pipe\\d4lf","metadata":{"area":"inventory","character":"rogue"}},"sequence":1,"timestamp":"2000-01-01T00:00:01.000Z","raw_text":"先祖传奇双手剑"}
```

- `schema_version` is currently `1`.
- `locale` and `game_build` are copied from the required CLI arguments.
- `session.id` is a new UUID for each run; `session.started_at` and record `timestamp` values are UTC.
- `session.metadata` contains the optional `--session-meta` values.
- `sequence` starts at `1` and increases once per received pipe message.
- `raw_text` preserves the decoded UTF-8 text exactly except for the single trailing NUL byte added by
  `saapi64.dll` as a transport terminator.

There is no trimming, entity replacement, item grouping, or English boundary detection. Messages such
as `CONNECTED`, `DISCONNECTED`, and `Mouse Button 4` are ordinary records if the DLL sends them.

## Atomic shutdown

Records are written to a temporary file in the output directory. On a clean stop, the recorder flushes
and syncs that file, then atomically replaces the requested output path. Until then, an existing output
file remains unchanged. If capture fails, the temporary file is removed and the previous output is
left in place.

Always use `Ctrl+C` and wait for the `Saved ... messages` confirmation. Closing the terminal or killing
the process cannot guarantee the final atomic rename.

## Replay offline

The App performs this step automatically after `Stop and Save`. For CLI captures, after the game is closed, rebuild
item boundaries without connecting to the named pipe or reading user config:

```powershell
uv run python -m src.tools.tts_replay `
  --input .\captures\zhCN-3.1.0.72810.jsonl `
  --assets-dir .\assets\lang\zhCN `
  --output .\captures\zhCN-3.1.0.72810-report.json
```

The replay command validates UTF-8 JSONL, schema version, locale, game build, and monotonically increasing unique
sequence numbers. Its report hashes the exact capture and language assets, contains every reconstructed raw frame,
and has no current timestamp, so the same inputs produce identical bytes.
