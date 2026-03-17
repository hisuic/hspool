# hspool

Personal Rofi-powered launcher for reusable commands and short text snippets.

---

## Overview

`hspool` is a lightweight CLI tool for storing and quickly retrieving reusable strings such as:

- shell commands
- email addresses
- frequently used text snippets

Entries are searched through **Rofi**, and can either be **copied to the clipboard** or **executed as commands**.

This tool is intentionally simple and minimal.

It is **not**:

- a clipboard history tool
- a password manager
- a secret storage system

It is designed as a **personal snippet pool** for fast reuse.

---

## Features

- Store reusable commands and text snippets
- Search entries using **Rofi**
- Copy snippets to clipboard or execute commands
- Separate **public** and **private** data stores
- Minimal **JSON Lines** storage format
- XDG-friendly file locations
- No external Python dependencies

---

## Requirements

The following tools must be available:

- Python 3
- rofi (or rofi-wayland)
- wl-copy
- notify-send

Typical Linux environments (Arch, Ubuntu, etc.) already include most of these.

---

## Setup

Clone the repository:

```bash
git clone https://github.com/yourname/hspool.git
cd hspool
```

Make the script executable:
```bash
chmod +x hspool
```

Create a symlink so the command is available globally:
```bash
ln -s $(pwd)/hspool ~/.local/bin/hspool
```

Ensure `~/.local/bin` is in your `PATH`.

---

## Usage

### Launch the selector
```bash
hspool
```

This opens a Rofi menu where entries can be searched and selected.

Displayed format:
```bash
cmd  hyprctl reload              [Hyprland config reload]
txt  yourname@example.com        [Main personal email]
```

Prefix meanings:
- `cmd` → command execution
- `txt` → copy to clipboard

---

## Add an entry (interactive)

```bash
hspool -add
```

You will be prompted for:

- content
- description
- action (`copy` or `exec`)
- storage location (`public` or `private`)

---

## Add an entry (non-interactive)

Example:
```bash
hspool -add --store public --action exec \
  --description "Hyprland config reload" \
  -- "hyprctl reload"
```

Example for storing text:
```bash
hspool -add --store private --action copy \
  --description "Main personal email" \
  -- "me@example.com"
```

---

## Data and Paths
hspool follows XDG conventions.

Config file:
```bash
~/.config/hspool/config.toml
```

Data files:
```bash
~/.local/share/hspool/public.jsonl
~/.local/share/hspool/private.jsonl
```

Each entry is stored as one JSON object per line.

Example:
```bash
{"content":"hyprctl reload","action":"exec","description":"Hyprland config reload"}
```
Both files are loaded when searching.

---

## Config
Configuration is optional.

Default behavior works without a config file.

Example `~/.config/hspool/config.toml`:
```bash
rofi_prompt = "hspool"
rofi_width = "80%"

data_files = [
  "~/.local/share/hspool/public.jsonl",
  "~/.local/share/hspool/private.jsonl"
]
```

Defaults:

prompt: `hspool`

rofi width: `80%`

---

## Warning
`private.jsonl` is not encrypted. Do not store secrets in this file.
`hspool` is a convenience tool, not a secure secret manager.
