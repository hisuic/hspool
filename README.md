# hspool

`hspool` is a local curated launcher for reusable strings, mainly shell commands, email addresses, and other short snippets. It uses Rofi as the interactive frontend and stores entries as JSON Lines files.

It is for quickly searching a small personal pool of reusable items and then either copying or executing the selected entry.

It is not:

- a clipboard history tool
- integrated with `cliphist`
- a password vault or secret manager
- a database-backed launcher

## Features

- Python implementation with standard library only
- executable as a normal shebang script
- XDG-friendly config and data paths
- two data stores: `public.jsonl` and `private.jsonl`
- merged search across both stores
- per-item action: `copy` or `exec`
- interactive add flow with Rofi
- script-friendly non-interactive add mode

## Requirements

Target environment:

- Linux
- Wayland-oriented setup such as Hyprland
- `rofi` or `rofi-wayland`
- `wl-copy`
- `notify-send`
- `bash`
- Python 3

No virtualenv or pip packages are required.

## Installation

Clone the repository somewhere under your home directory, for example:

```bash
git clone <your-repo-url> ~/src/hspool
cd ~/src/hspool
chmod +x hspool
ln -sf ~/src/hspool/hspool ~/.local/bin/hspool
```

The executable script imports the local `hspoollib` package from the same repository, so the symlink-to-script workflow is the intended local setup.

## Usage

Open the launcher:

```bash
hspool
```

Interactive add mode:

```bash
hspool -add
```

Non-interactive add mode:

```bash
hspool -add --store public --action exec --description "Hyprland config reload" -- "hyprctl reload"
hspool -add --store private --action copy --description "Main personal email" -- "me@example.com"
```

When launched, entries are displayed as one line in Rofi:

```text
cmd  hyprctl reload              [Hyprland config reload]
txt  yourname@example.com        [Main personal email]
```

Action mapping:

- `exec` -> `cmd`
- `copy` -> `txt`

For `copy`, `hspool` sends the item content to `wl-copy`.

For `exec`, `hspool` runs the content through `bash -lc` so normal shell parsing works as expected. Execution failures are reported back as command errors, and a critical notification is sent if `notify-send` is available.

## Data format

Each item is stored as one JSON object per line:

```json
{"content":"hyprctl reload","action":"exec","description":"Hyprland config reload"}
```

Required schema:

- `content`
- `action`
- `description`

Supported actions in v1:

- `copy`
- `exec`

No titles, tags, type fields, or clipboard-history import features are included.

## File locations

Config:

- `~/.config/hspool/config.toml`

Data:

- `~/.local/share/hspool/public.jsonl`
- `~/.local/share/hspool/private.jsonl`

Directories are created automatically as needed. Missing data files are treated as empty.

`private.jsonl` is for personal non-public entries such as email addresses. It is not encrypted and should not be used for passwords, tokens, API keys, or other secrets.

## Configuration

If `~/.config/hspool/config.toml` does not exist, `hspool` uses sensible defaults.

Supported config values:

```toml
[data]
public_file = "~/.local/share/hspool/public.jsonl"
private_file = "~/.local/share/hspool/private.jsonl"
# Optional override for merged search input order:
# files = [
#   "~/.local/share/hspool/public.jsonl",
#   "~/.local/share/hspool/private.jsonl",
# ]

[rofi]
width = "80%"
prompt = "hspool"
```

`rofi.width` is applied as a theme override for `window { width: ...; }`, so it can
override theme files that set a fixed window width.

Notes:

- `data.files` is optional. If omitted, `hspool` loads `public_file` and `private_file`.
- Relative paths in config are resolved relative to the config file directory.
- On Python 3.11+, TOML is parsed with `tomllib`.
- On older Python 3 versions, `hspool` falls back to a small built-in parser that supports the simple string and string-array config used here.

## Development notes

This repository is intended to stay small and local-tool oriented. The initial implementation deliberately avoids:

- pip dependencies
- subcommand-heavy CLI redesign
- tags or extra metadata
- plugin systems
- secret-management claims

## Troubleshooting

- If `hspool` says no entries were found, add one with `hspool -add`.
- If Rofi does not open, confirm `rofi` or `rofi-wayland` is installed and on `PATH`.
- If copy actions fail, confirm `wl-copy` is installed.
- If exec actions fail, the error includes the failing command and any captured stdout/stderr.
