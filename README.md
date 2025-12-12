# lcfilter

> **Filtered Android logcat viewing with scope-aware protection.**

Cut through the noise of Android logcat output. **lcfilter** lets you define what to hide and what to protect, so you only see the logs that matter.

## The Problem

You run your Android app and... **thousands of lines of logcat output flood your terminal**. System services, GC events, framework internals—none of it tells you if *your code* is working.

You need a way to focus on **signal over noise**.

## The Solution

**lcfilter** brings `.gitignore`-style filtering to Android logs:

```bash
# In your Android project directory
lcfilter init      # Creates .logcatignore and .logcatscope
lcfilter monitor   # See only what matters
```

### Scope-Aware Filtering

The key insight: **your app's logs should never be hidden by broad rules**.

Configure what's "in scope" for your project, and those tags are *protected*—even when you filter out all verbose/debug noise from the system:

```toml
# .logcatscope - Your app's identity
[expected_tags]
tags = ["MyApp", "flutter", "MyNetwork"]
```

```gitignore
# .logcatignore - What to hide
LEVEL:V    # Hides verbose... except from MyApp, flutter, MyNetwork
LEVEL:D    # Hides debug... except from your app
TAG:chatty # System noise, gone
```

**Result:** Clean output. Your logs. Your app's story.

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

## Configuration

### `.logcatignore` — What to Hide

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

### `.logcatscope` — What to Protect

```toml
[app]
package = "com.example.myapp"

[expected_tags]
# These tags are PROTECTED from TAG/LEVEL/TAGLEVEL rules
tags = ["MyApp", "flutter", "MyNetworkLayer"]

[expected_libs]
libs = ["okhttp", "retrofit2"]

[stacktrace_roots]
roots = ["com.example.myapp.", "kotlin."]
```

## Features

- **Real-time filtering** — Stream logcat with instant filtering
- **Scope-aware protection** — Your app's logs are never hidden by broad rules
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
