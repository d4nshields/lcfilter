# lcfilter

> **Three-stream log routing for Android development.**

Cut through the noise of Android logcat output. **lcfilter** routes your logs to three streams: your app's logs, known noise to ignore, and everything else you're still evaluating.

## The Problem

You run your Android app and... **thousands of lines of logcat output flood your terminal**. System services, GC events, framework internals—none of it tells you if *your code* is working.

You need a way to focus on **signal over noise**.

## The Solution

**lcfilter** brings three-stream routing to Android logs:

```bash
# In your Android project directory
lcfilter init      # Creates .logcatignore and .logcatscope
lcfilter monitor   # See only what matters
```

### Three-Stream Routing

Logs are routed to three streams based on simple rules:

1. **In-Scope** — Tags listed in `.logcatscope` (your app's logs)
2. **Ignored** — Matches rules in `.logcatignore` (known noise)
3. **Noise** — Everything else (monitor this to refine your filters)

```
┌─────────────────────────────────────────────────────────────┐
│                     logcat output                           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   Tag in .logcatscope? │
              └───────────┬────────────┘
                    yes   │   no
                ┌─────────┴─────────┐
                ▼                   ▼
         ┌──────────┐    ┌────────────────────┐
         │ In-Scope │    │ Matches .logcatignore? │
         │ (stdout) │    └──────────┬─────────┘
         └──────────┘         yes   │   no
                          ┌─────────┴─────────┐
                          ▼                   ▼
                   ┌──────────┐        ┌──────────┐
                   │ Ignored  │        │  Noise   │
                   │(/dev/null)│        │ (stdout) │
                   └──────────┘        └──────────┘
```

**The workflow:**
1. Set your app's debug tags in `.logcatscope`
2. Monitor the noise stream over time
3. Add high-volume/low-relevance patterns to `.logcatignore`
4. Keep noise manageable for automated monitoring and alerts

## Quick Start

### Installation

```bash
# With pipx (recommended)
pipx install git+https://github.com/d4nshields/lcfilter.git

# Or for development
git clone https://github.com/d4nshields/lcfilter.git
cd lcfilter
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

### Basic Usage

```bash
# Initialize in your Android project
cd your-android-project
lcfilter init

# Edit .logcatignore and .logcatscope for your project

# Start monitoring (or use 'mon' for short)
lcfilter monitor
lcfilter mon --clear          # Clear buffer first
lcfilter mon -- -s MyTag:*    # Pass args to adb logcat

# Route streams to files
lcfilter mon --ignored=ignored.log    # Save ignored to file
lcfilter mon --in-scope=app.log --noise=/dev/null  # Only app logs

# Test filters against saved logs
lcfilter dry-run -i captured.txt --stats
```

## Commands

| Command | Description |
|---------|-------------|
| `init` | Create sample config files |
| `monitor` / `mon` | Stream filtered logcat in real-time |
| `dry-run` | Test filters against a log file |
| `clear` | Clear the device's logcat buffer |

### Monitor Options

```bash
lcfilter monitor [OPTIONS] [-- ADB_ARGS...]

Options:
  --ignore-file PATH    Path to .logcatignore file (default: .logcatignore)
  --scope-file PATH     Path to .logcatscope file (default: .logcatscope)
  --raw                 Bypass filtering, print everything
  --color/--no-color    Enable/disable colored output
  -c, --clear           Clear logcat buffer before starting

Stream Routing:
  --in-scope FILE       Route in-scope logs to file (default: stdout)
  --ignored FILE        Route ignored logs to file (default: /dev/null)
  --noise FILE          Route noise logs to file (default: stdout)
```

## Configuration

### `.logcatscope` — Your App's Tags

A simple list of tags that belong to your app. One tag per line.

```
# .logcatscope - Tags that belong to my app
# Comments start with #

# Main app tags
MyApp
MyAppNetwork
MyAppDb

# Flutter tags
flutter

# Third-party libraries you care about
OkHttp
```

Tags in this file are **always** routed to the in-scope stream, regardless of ignore rules.

### `.logcatignore` — Known Noise to Hide

```gitignore
# Hide by log level
LEVEL:V
LEVEL:D

# Hide by tag
TAG:chatty
TAG:ViewRootImpl

# Hide by tag + level combo
TAGLEVEL:ActivityManager:I

# Hide by regex on message
PATTERN:^GC.*freed

# Hide by regex on entire line
LINEPATTERN:.*\bART\b.*\bGC\b.*
```

**Note:** These rules only apply to logs that are NOT in scope. Your app's logs (tags in `.logcatscope`) are never hidden by `.logcatignore` rules.

## Features

- **Three-stream routing** — Separate your app, known noise, and unknown noise
- **Scope-aware protection** — Your app's logs are never hidden by broad rules
- **Flexible routing** — Route any stream to stdout, file, or /dev/null
- **Multiple formats** — Supports threadtime, brief, tag, time, process formats
- **Color-coded output** — Log levels are color-coded for quick scanning
- **Dry-run mode** — Test your filters against saved log files
- **Extensible** — Filter engine supports pre/post hooks for custom logic

## Current Status: Alpha

This is early software. It works, it's tested, but the API may change.

## We Want Your Feedback

This project is looking for early testers who are interested in:

- **Using it** — Try it on your Android projects and tell us what's missing
- **Breaking it** — Find edge cases, report bugs, suggest improvements
- **Shaping it** — Help define what features would help your workflow

### How to Contribute

1. **Try it out** and [open an issue](https://github.com/d4nshields/lcfilter/issues) with your experience
2. **Share ideas** for features that would help your workflow
3. **Submit PRs** for bug fixes or improvements
4. **Star the repo** if you find it useful

## Development

```bash
# Setup
git clone https://github.com/d4nshields/lcfilter.git
cd lcfilter
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Test
pytest
pytest --cov=lcfilter

# Run
lcfilter --help
```

## Requirements

- Python 3.11+
- `adb` in PATH (Android SDK platform-tools)

## License

MIT — Use it, fork it, build on it.

---

*Cut through the noise. See what matters.*
