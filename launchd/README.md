# launchd setup

This project uses a user LaunchAgent for LLM-free scheduling on macOS.

Installed label:
- `com.openclaw.forecast-snapshot-tracker`

Installed plist target:
- `~/Library/LaunchAgents/com.openclaw.forecast-snapshot-tracker.plist`

Behavior:
- Runs `/opt/homebrew/bin/python3 scripts/run_once.py`
- Starts at load
- Repeats every 300 seconds (5 minutes)
- Writes logs to `data/logs/launchd.stdout.log` and `data/logs/launchd.stderr.log`

Useful commands:
```bash
launchctl print gui/$(id -u)/com.openclaw.forecast-snapshot-tracker
launchctl kickstart -k gui/$(id -u)/com.openclaw.forecast-snapshot-tracker
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.openclaw.forecast-snapshot-tracker.plist
```
