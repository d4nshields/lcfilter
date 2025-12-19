"""Command-line interface for lcfilter."""

import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.text import Text

from . import __version__
from .config_ignore import (
    parse_ignore_file,
    generate_sample_ignore_file,
    IgnoreParseError,
)
from .config_scope import (
    parse_scope_file,
    generate_sample_scope_file,
    ScopeParseError,
)
from .filter_engine import FilterEngine, FilterStats
from .parser_logcat import parse_logcat_line, LogcatStreamParser
from .models import IgnoreConfig, ScopeConfig, LogLevel, RouteCategory
from .stream_router import StreamRouter, RoutingConfig

app = typer.Typer(
    name="lcfilter",
    help="Filter Android logcat output using .logcatignore and .logcatscope config files.",
    add_completion=False,
)

console = Console()
err_console = Console(stderr=True)

# Default file names
DEFAULT_IGNORE_FILE = ".logcatignore"
DEFAULT_SCOPE_FILE = ".logcatscope"


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"lcfilter {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """lcfilter - Filter Android logcat output."""
    pass


@app.command()
def init(
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Overwrite existing config files.",
        ),
    ] = False,
) -> None:
    """Create sample .logcatignore and .logcatscope files in the current directory."""
    cwd = Path.cwd()
    ignore_path = cwd / DEFAULT_IGNORE_FILE
    scope_path = cwd / DEFAULT_SCOPE_FILE

    created_files = []
    skipped_files = []

    # Handle .logcatignore
    if force and ignore_path.exists():
        ignore_path.unlink()
    if generate_sample_ignore_file(ignore_path):
        created_files.append(DEFAULT_IGNORE_FILE)
    else:
        skipped_files.append(DEFAULT_IGNORE_FILE)

    # Handle .logcatscope
    if force and scope_path.exists():
        scope_path.unlink()
    if generate_sample_scope_file(scope_path):
        created_files.append(DEFAULT_SCOPE_FILE)
    else:
        skipped_files.append(DEFAULT_SCOPE_FILE)

    # Report results
    if created_files:
        console.print(f"[green]Created:[/green] {', '.join(created_files)}")

    if skipped_files:
        console.print(
            f"[yellow]Skipped (already exist):[/yellow] {', '.join(skipped_files)}"
        )
        console.print("[dim]Use --force to overwrite existing files.[/dim]")


@app.command()
def clear() -> None:
    """Clear the logcat buffer (runs 'adb logcat -c')."""
    try:
        subprocess.run(["adb", "logcat", "-c"], check=True, capture_output=True)
        console.print("[green]Logcat buffer cleared.[/green]")
    except subprocess.CalledProcessError as e:
        err_console.print(f"[red]Failed to clear logcat buffer:[/red] {e}")
        raise typer.Exit(1)
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] adb not found. Is it installed and in PATH?")
        raise typer.Exit(1)


@app.command("dry-run")
def dry_run(
    input_file: Annotated[
        Path,
        typer.Option(
            "--input",
            "-i",
            help="Path to a file containing logcat output.",
            exists=True,
            readable=True,
        ),
    ],
    ignore_file: Annotated[
        Path,
        typer.Option(
            "--ignore-file",
            help="Path to .logcatignore file.",
        ),
    ] = Path(DEFAULT_IGNORE_FILE),
    scope_file: Annotated[
        Optional[Path],
        typer.Option(
            "--scope-file",
            help="Path to .logcatscope file.",
        ),
    ] = None,
    stats: Annotated[
        bool,
        typer.Option(
            "--stats",
            "-s",
            help="Show filtering statistics at the end.",
        ),
    ] = False,
    color: Annotated[
        bool,
        typer.Option(
            "--color/--no-color",
            help="Enable/disable colored output.",
        ),
    ] = True,
) -> None:
    """Read logcat lines from a file, apply ignore rules, and print filtered output."""
    # Load config files
    ignore_config = _load_ignore_config(ignore_file)
    scope_config = _load_scope_config(scope_file)

    # Create filter engine
    engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)
    filter_stats = FilterStats() if stats else None

    # Read and filter input file
    try:
        content = input_file.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        err_console.print(f"[red]Error reading input file:[/red] {e}")
        raise typer.Exit(1)

    for line in content.splitlines():
        entry = parse_logcat_line(line)
        result = engine.filter_entry(entry)

        if filter_stats:
            filter_stats.record(result)

        if result.should_display:
            _print_entry(entry, color=color)

    # Print stats if requested
    if filter_stats:
        err_console.print()
        err_console.print("[bold]Filter Statistics:[/bold]")
        err_console.print(filter_stats.summary())


@app.command("monitor")
def monitor(
    ignore_file: Annotated[
        Path,
        typer.Option(
            "--ignore-file",
            help="Path to .logcatignore file.",
        ),
    ] = Path(DEFAULT_IGNORE_FILE),
    scope_file: Annotated[
        Optional[Path],
        typer.Option(
            "--scope-file",
            help="Path to .logcatscope file.",
        ),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw",
            help="Print unfiltered logcat output (bypass routing).",
        ),
    ] = False,
    color: Annotated[
        bool,
        typer.Option(
            "--color/--no-color",
            help="Enable/disable colored output.",
        ),
    ] = True,
    clear: Annotated[
        bool,
        typer.Option(
            "--clear",
            "-c",
            help="Clear the logcat buffer before starting.",
        ),
    ] = False,
    in_scope_output: Annotated[
        Optional[str],
        typer.Option(
            "--in-scope",
            help="Route in-scope logs to file (default: stdout).",
        ),
    ] = None,
    ignored_output: Annotated[
        Optional[str],
        typer.Option(
            "--ignored",
            help="Route ignored logs to file (default: /dev/null).",
        ),
    ] = None,
    noise_output: Annotated[
        Optional[str],
        typer.Option(
            "--noise",
            help="Route noise logs to file (default: stdout).",
        ),
    ] = None,
    adb_args: Annotated[
        Optional[list[str]],
        typer.Argument(
            help="Additional arguments to pass to adb logcat.",
        ),
    ] = None,
) -> None:
    """Run adb logcat with three-stream routing.

    Logs are routed to three streams based on hierarchical tests:
    1. In-scope (tag in .logcatscope) -> --in-scope stream
    2. Ignored (matches .logcatignore) -> --ignored stream
    3. Noise (everything else) -> --noise stream

    Any additional arguments after -- are passed directly to adb logcat.

    Examples:
        lcfilter monitor
        lcfilter mon --raw
        lcfilter monitor --ignored=ignored.log
        lcfilter monitor --in-scope=app.log --noise=/dev/null
        lcfilter monitor -- -s MyTag:*
    """
    # Load config files (unless raw mode)
    ignore_config = None
    scope_config = None

    if not raw:
        ignore_config = _load_ignore_config(ignore_file)
        scope_config = _load_scope_config(scope_file)

    # Create filter engine
    engine = FilterEngine(ignore_config=ignore_config, scope_config=scope_config)

    # Build adb command
    cmd = ["adb", "logcat"]

    if clear:
        # Clear buffer first
        try:
            subprocess.run(["adb", "logcat", "-c"], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            err_console.print(f"[red]Failed to clear logcat buffer:[/red] {e}")
        except FileNotFoundError:
            err_console.print("[red]Error:[/red] adb not found. Is it installed and in PATH?")
            raise typer.Exit(1)

    if adb_args:
        cmd.extend(adb_args)

    # Run adb logcat
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
    except FileNotFoundError:
        err_console.print("[red]Error:[/red] adb not found. Is it installed and in PATH?")
        raise typer.Exit(1)

    # Set up routing
    routing_config = RoutingConfig.from_options(
        in_scope=in_scope_output,
        ignored=ignored_output,
        noise=noise_output,
    )

    try:
        assert process.stdout is not None

        if raw:
            # Raw mode: bypass routing, print everything to stdout
            for line in process.stdout:
                entry = parse_logcat_line(line)
                _print_entry(entry, color=color)
        else:
            # Normal mode: route to three streams
            with StreamRouter(routing_config) as router:
                for line in process.stdout:
                    entry = parse_logcat_line(line)
                    result = engine.route_entry(entry)

                    # Write to appropriate stream
                    if color and _is_stdout_stream(result.category, routing_config):
                        # Use colored output for stdout streams
                        _print_entry_to_category(entry, result.category, routing_config, color=True)
                    else:
                        # Plain output for file streams
                        router.write(result.category, entry.raw_line)

    except KeyboardInterrupt:
        err_console.print("\n[dim]Interrupted.[/dim]")
    finally:
        process.terminate()
        process.wait()


def _is_stdout_stream(category: RouteCategory, config: RoutingConfig) -> bool:
    """Check if a category routes to stdout."""
    if category == RouteCategory.IN_SCOPE:
        return config.in_scope.is_stdout()
    elif category == RouteCategory.IGNORED:
        return config.ignored.is_stdout()
    else:  # NOISE
        return config.noise.is_stdout()


def _print_entry_to_category(
    entry, category: RouteCategory, config: RoutingConfig, color: bool = True
) -> None:
    """Print entry to stdout if that category goes to stdout."""
    if _is_stdout_stream(category, config):
        _print_entry(entry, color=color)


# Register 'mon' as an alias for 'monitor'
app.command("mon", hidden=True)(monitor)


def _load_ignore_config(path: Path) -> IgnoreConfig:
    """Load ignore config from file, with fallback to empty config."""
    if not path.exists():
        err_console.print(
            f"[yellow]Warning:[/yellow] {path} not found. "
            "Run 'lcfilter init' to create one."
        )
        return IgnoreConfig()

    try:
        return parse_ignore_file(path)
    except IgnoreParseError as e:
        err_console.print(f"[red]Error parsing {path}:[/red] {e}")
        raise typer.Exit(1)


def _load_scope_config(path: Path | None) -> ScopeConfig:
    """Load scope config from file, with fallback to empty config."""
    if path is None:
        path = Path(DEFAULT_SCOPE_FILE)

    if not path.exists():
        # Scope file is optional, don't warn
        return ScopeConfig()

    try:
        return parse_scope_file(path)
    except ScopeParseError as e:
        err_console.print(f"[red]Error parsing {path}:[/red] {e}")
        raise typer.Exit(1)


# Level to color mapping for rich output
LEVEL_COLORS = {
    LogLevel.VERBOSE: "dim",
    LogLevel.DEBUG: "blue",
    LogLevel.INFO: "green",
    LogLevel.WARNING: "yellow",
    LogLevel.ERROR: "red",
    LogLevel.FATAL: "red bold",
    LogLevel.SILENT: "dim",
}


def _print_entry(entry, color: bool = True) -> None:
    """Print a log entry with optional coloring."""
    if not color:
        console.print(entry.raw_line, highlight=False)
        return

    # Apply color based on log level
    if entry.level and entry.level in LEVEL_COLORS:
        style = LEVEL_COLORS[entry.level]
        text = Text(entry.raw_line, style=style)
        console.print(text, highlight=False)
    else:
        console.print(entry.raw_line, highlight=False)


if __name__ == "__main__":
    app()
