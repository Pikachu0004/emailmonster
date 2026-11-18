#!/usr/bin/env bash
# ==============================================================================
# Devengers Mail Engine - 6:00 PM IST Daily Automation Setup
# ==============================================================================

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
PLIST_NAME="com.devengers.mailengine.plist"
PLIST_SRC="$DIR/scripts/$PLIST_NAME"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_DEST="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo "⚡ Devengers Mail Engine - Daily 6:00 PM IST Scheduler Setup"
echo "Working directory: $DIR"

mkdir -p "$DIR/logs"
mkdir -p "$LAUNCH_AGENTS_DIR"

case "$1" in
  launchd|mac)
    echo "Installing native macOS LaunchAgent (Runs every day at 18:00 IST)..."
    # Unload if already loaded
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    cp "$PLIST_SRC" "$PLIST_DEST"
    launchctl load "$PLIST_DEST"
    echo "✓ Success: Scheduled to run every day at 6:00 PM IST via macOS Launchd."
    echo "Logs will be recorded at: $DIR/logs/daily_send.log"
    ;;

  cron)
    echo "Setting up standard Crontab (0 18 * * *)..."
    CRON_CMD="0 18 * * * cd '$DIR' && ./venv/bin/python3 run.py send --limit 300 >> '$DIR/logs/daily_send.log' 2>&1"
    (crontab -l 2>/dev/null | grep -v "com.devengers.mailengine\|run.py send"; echo "$CRON_CMD") | crontab -
    echo "✓ Success: Crontab entry added for 18:00 (6:00 PM IST) daily."
    ;;

  status)
    echo "Checking Launchd status..."
    launchctl list | grep "devengers" || echo "Launchd agent not loaded."
    echo "Checking Crontab status..."
    crontab -l 2>/dev/null | grep "run.py send" || echo "Crontab entry not found."
    ;;

  stop|uninstall)
    echo "Disabling daily 6:00 PM scheduler..."
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    rm -f "$PLIST_DEST"
    (crontab -l 2>/dev/null | grep -v "run.py send") | crontab - || true
    echo "✓ Successfully disabled daily schedule."
    ;;

  *)
    echo "Usage: ./scripts/setup_schedule.sh [mac | cron | status | stop]"
    echo "  mac    - Install native macOS background job (Recommended for Mac)"
    echo "  cron   - Install crontab job (Runs at 0 18 * * *)"
    echo "  status - Check whether scheduler is active"
    echo "  stop   - Remove/disable the daily schedule"
    exit 1
    ;;
esac
