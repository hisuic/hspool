#!/usr/bin/env python3
"""Local curated snippet launcher using rofi and JSONL storage."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


APP_NAME = "hspool"
DEFAULT_ROFI_WIDTH = "80%"
DEFAULT_ROFI_PROMPT = "hspool"
VALID_ACTIONS = {"copy", "exec"}
VALID_STORES = {"public", "private"}


class HspoolError(Exception):
    """Expected application-level error."""


@dataclass
class Item:
    content: str
    action: str
    description: str
    source: Optional[Path] = None

    def to_record(self) -> Dict[str, str]:
        return {
            "content": self.content,
            "action": self.action,
            "description": self.description,
        }

    def display_line(self, content_width: int = 28) -> str:
        prefix = "cmd" if self.action == "exec" else "txt"
        compact = " ".join(self.content.split())
        if len(compact) > content_width:
            shown = compact[: max(0, content_width - 1)] + "…"
        else:
            shown = compact.ljust(content_width)
        return f"{prefix}  {shown}  [{self.description}]"


@dataclass
class AppConfig:
    config_path: Path
    data_files: List[Path]
    public_file: Path
    private_file: Path
    rofi_width: str = DEFAULT_ROFI_WIDTH
    rofi_prompt: str = DEFAULT_ROFI_PROMPT


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config()
        ensure_parent_dirs(config)
        if args.add:
            if should_use_interactive_add(args):
                interactive_add(config)
            else:
                non_interactive_add(config, args)
            return 0
        launch_selector(config)
        return 0
    except KeyboardInterrupt:
        return 130
    except HspoolError as exc:
        print(f"{APP_NAME}: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Curated personal snippet launcher using rofi.",
    )
    parser.add_argument("-add", action="store_true", dest="add", help="add a new item")
    parser.add_argument(
        "--store",
        choices=sorted(VALID_STORES),
        help="where to store the item for -add",
    )
    parser.add_argument(
        "--action",
        choices=sorted(VALID_ACTIONS),
        help="action for the item when using -add",
    )
    parser.add_argument(
        "--description",
        help="description for the item when using -add",
    )
    parser.add_argument(
        "content",
        nargs="?",
        help="item content for non-interactive -add",
    )
    return parser


def should_use_interactive_add(args: argparse.Namespace) -> bool:
    return (
        args.add
        and args.store is None
        and args.action is None
        and args.description is None
        and args.content is None
    )


def load_config() -> AppConfig:
    home = Path.home()
    config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
    config_path = config_home / APP_NAME / "config.toml"
    default_public = data_home / APP_NAME / "public.jsonl"
    default_private = data_home / APP_NAME / "private.jsonl"

    values: Dict[str, Any] = {}
    if config_path.exists():
        values = parse_config_file(config_path)

    data_section = ensure_mapping(values.get("data"), "data")
    rofi_section = ensure_mapping(values.get("rofi"), "rofi")

    public_path = resolve_path(
        data_section.get("public_file", str(default_public)),
        base_dir=config_path.parent,
    )
    private_path = resolve_path(
        data_section.get("private_file", str(default_private)),
        base_dir=config_path.parent,
    )

    files_value = data_section.get("files")
    if files_value is None:
        data_files = [public_path, private_path]
    else:
        if not isinstance(files_value, list) or not all(isinstance(v, str) for v in files_value):
            raise HspoolError("config data.files must be an array of strings")
        data_files = [resolve_path(v, base_dir=config_path.parent) for v in files_value]

    width = rofi_section.get("width", DEFAULT_ROFI_WIDTH)
    prompt = rofi_section.get("prompt", DEFAULT_ROFI_PROMPT)
    if not isinstance(width, str) or not width.strip():
        raise HspoolError("config rofi.width must be a non-empty string")
    if not isinstance(prompt, str) or not prompt.strip():
        raise HspoolError("config rofi.prompt must be a non-empty string")

    return AppConfig(
        config_path=config_path,
        data_files=data_files,
        public_file=public_path,
        private_file=private_path,
        rofi_width=width.strip(),
        rofi_prompt=prompt.strip(),
    )


def parse_config_file(path: Path) -> Dict[str, Any]:
    raw = path.read_bytes()
    if tomllib is not None:
        try:
            parsed = tomllib.loads(raw.decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            raise HspoolError(f"invalid config TOML in {path}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HspoolError(f"invalid config structure in {path}")
        return parsed
    try:
        return parse_minimal_toml(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise HspoolError(f"config file is not valid UTF-8: {path}") from exc


def parse_minimal_toml(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    current = result
    for index, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = strip_inline_comment(line)
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            if not section_name or "." in section_name:
                raise HspoolError(f"unsupported TOML section at line {index}")
            current = result.setdefault(section_name, {})
            if not isinstance(current, dict):
                raise HspoolError(f"invalid section redeclaration at line {index}")
            continue
        if "=" not in line:
            raise HspoolError(f"invalid TOML assignment at line {index}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise HspoolError(f"missing key at line {index}")
        current[key] = parse_toml_value(value.strip(), index)
    return result


def strip_inline_comment(line: str) -> str:
    in_string = False
    escaped = False
    for index, char in enumerate(line):
        if char == "\\" and in_string:
            escaped = not escaped
            continue
        if char == '"' and not escaped:
            in_string = not in_string
        if char == "#" and not in_string:
            return line[:index].rstrip()
        escaped = False
    return line


def parse_toml_value(value: str, line_no: int) -> Any:
    if value.startswith('"') and value.endswith('"'):
        return parse_basic_string(value, line_no)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        parts = split_toml_array(inner, line_no)
        return [parse_toml_value(part, line_no) for part in parts]
    raise HspoolError(f"unsupported TOML value at line {line_no}")


def parse_basic_string(value: str, line_no: int) -> str:
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise HspoolError(f"invalid string at line {line_no}") from exc


def split_toml_array(value: str, line_no: int) -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    in_string = False
    escaped = False
    for char in value:
        if char == "\\" and in_string:
            escaped = not escaped
            current.append(char)
            continue
        if char == '"' and not escaped:
            in_string = not in_string
        if char == "," and not in_string:
            part = "".join(current).strip()
            if not part:
                raise HspoolError(f"invalid empty array item at line {line_no}")
            parts.append(part)
            current = []
        else:
            current.append(char)
        escaped = False
    tail = "".join(current).strip()
    if not tail:
        raise HspoolError(f"invalid trailing comma at line {line_no}")
    parts.append(tail)
    return parts


def ensure_mapping(value: Any, name: str) -> Dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise HspoolError(f"config section {name!r} must be a table")
    return value


def resolve_path(raw: str, base_dir: Path) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise HspoolError("config paths must be non-empty strings")
    expanded = os.path.expandvars(os.path.expanduser(raw.strip()))
    path = Path(expanded)
    if not path.is_absolute():
        path = base_dir / path
    return path


def ensure_parent_dirs(config: AppConfig) -> None:
    config.config_path.parent.mkdir(parents=True, exist_ok=True)
    for path in {config.public_file, config.private_file, *config.data_files}:
        path.parent.mkdir(parents=True, exist_ok=True)


def interactive_add(config: AppConfig) -> None:
    rofi_cmd = build_rofi_base_command(config, prompt=f"{config.rofi_prompt}: content")
    content = prompt_text(rofi_cmd, prompt=f"{config.rofi_prompt}: content")
    description = prompt_text(
        build_rofi_base_command(config, prompt=f"{config.rofi_prompt}: description"),
        prompt=f"{config.rofi_prompt}: description",
    )
    action = prompt_choice(
        config,
        ["copy", "exec"],
        prompt=f"{config.rofi_prompt}: action",
    )
    store = prompt_choice(
        config,
        ["public", "private"],
        prompt=f"{config.rofi_prompt}: store",
    )
    item = build_item(content=content, description=description, action=action)
    append_item(config, store, item)
    notify("hspool", f"Saved {store} item")


def non_interactive_add(config: AppConfig, args: argparse.Namespace) -> None:
    missing = [
        name
        for name, value in (
            ("--store", args.store),
            ("--action", args.action),
            ("--description", args.description),
            ("content", args.content),
        )
        if value is None
    ]
    if missing:
        raise HspoolError(
            "non-interactive -add requires --store, --action, --description, and content"
        )
    item = build_item(
        content=args.content,
        description=args.description,
        action=args.action,
    )
    append_item(config, args.store, item)


def build_item(content: str, description: str, action: str) -> Item:
    content = (content or "").strip()
    description = (description or "").strip()
    action = (action or "").strip()
    if not content:
        raise HspoolError("content must not be empty")
    if not description:
        raise HspoolError("description must not be empty")
    if action not in VALID_ACTIONS:
        raise HspoolError(f"action must be one of: {', '.join(sorted(VALID_ACTIONS))}")
    return Item(content=content, description=description, action=action)


def append_item(config: AppConfig, store: str, item: Item) -> None:
    if store not in VALID_STORES:
        raise HspoolError(f"store must be one of: {', '.join(sorted(VALID_STORES))}")
    target = config.public_file if store == "public" else config.private_file
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item.to_record(), ensure_ascii=False) + "\n")


def launch_selector(config: AppConfig) -> None:
    items = load_items(config.data_files)
    if not items:
        raise HspoolError(
            "no entries found; add one with 'hspool -add' or create JSONL items first"
        )

    lines = [item.display_line() for item in items]
    selected = run_rofi_menu(config, lines, prompt=config.rofi_prompt)
    if selected is None:
        return

    try:
        index = lines.index(selected)
    except ValueError as exc:
        raise HspoolError("rofi returned an unknown selection") from exc

    handle_item(items[index])


def load_items(paths: Iterable[Path]) -> List[Item]:
    items: List[Item] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_no, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise HspoolError(f"invalid JSON in {path}:{line_no}: {exc}") from exc
                items.append(parse_item_record(record, source=path, line_no=line_no))
    return items


def parse_item_record(record: Any, source: Path, line_no: int) -> Item:
    if not isinstance(record, dict):
        raise HspoolError(f"invalid item in {source}:{line_no}: expected JSON object")
    required = {"content", "action", "description"}
    missing = sorted(required - set(record))
    if missing:
        raise HspoolError(
            f"invalid item in {source}:{line_no}: missing {', '.join(missing)}"
        )
    unexpected = sorted(set(record) - required)
    if unexpected:
        raise HspoolError(
            f"invalid item in {source}:{line_no}: unexpected fields {', '.join(unexpected)}"
        )
    content = record.get("content")
    action = record.get("action")
    description = record.get("description")
    if not all(isinstance(value, str) for value in (content, action, description)):
        raise HspoolError(f"invalid item in {source}:{line_no}: fields must be strings")
    return build_item(content=content, description=description, action=action)


def handle_item(item: Item) -> None:
    if item.action == "copy":
        run_required_command(["wl-copy"], input_text=item.content)
        notify("hspool", f"Copied: {item.description}")
        return
    if item.action == "exec":
        try:
            run_required_command(["wl-copy"], input_text=item.content)
        except HspoolError as exc:
            notify(
                "hspool",
                f"Copy failed, command not executed: {item.description}",
                urgency="critical",
            )
            raise exc
        try:
            run_required_command(
                ["bash", "-lc", item.content],
                capture_output=True,
                check=True,
            )
        except HspoolError as exc:
            notify("hspool", f"Command failed: {item.description}", urgency="critical")
            raise exc
        notify("hspool", f"Executed and copied: {item.description}")
        return
    raise HspoolError(f"unsupported action: {item.action}")


def run_rofi_menu(config: AppConfig, lines: Sequence[str], prompt: str) -> Optional[str]:
    cmd = build_rofi_base_command(config, prompt=prompt)
    joined = "\n".join(lines)
    try:
        completed = subprocess.run(
            cmd,
            input=joined,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HspoolError("rofi or rofi-wayland is required but was not found") from exc

    if completed.returncode == 0:
        return completed.stdout.rstrip("\n")
    if completed.returncode == 1:
        return None
    raise HspoolError(format_command_failure(cmd, completed))


def prompt_text(cmd: Sequence[str], prompt: str) -> str:
    try:
        completed = subprocess.run(
            cmd,
            input="",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HspoolError("rofi or rofi-wayland is required but was not found") from exc
    if completed.returncode == 0:
        value = completed.stdout.rstrip("\n")
        if not value.strip():
            raise HspoolError(f"{prompt} must not be empty")
        return value
    if completed.returncode == 1:
        raise HspoolError("selection cancelled")
    raise HspoolError(format_command_failure(cmd, completed))


def prompt_choice(config: AppConfig, choices: Sequence[str], prompt: str) -> str:
    value = run_rofi_menu(config, choices, prompt=prompt)
    if value is None:
        raise HspoolError("selection cancelled")
    value = value.strip()
    if value not in choices:
        raise HspoolError(f"invalid selection for {prompt}: {value}")
    return value


def build_rofi_base_command(config: AppConfig, prompt: str) -> List[str]:
    rofi_bin = shutil.which("rofi-wayland") or shutil.which("rofi")
    if not rofi_bin:
        raise HspoolError("rofi or rofi-wayland is required but was not found")
    return [
        rofi_bin,
        "-dmenu",
        "-i",
        "-matching",
        "fuzzy",
        "-p",
        prompt,
        "-theme-str",
        f"window {{ width: {config.rofi_width}; }}",
    ]


def run_required_command(
    cmd: Sequence[str],
    input_text: Optional[str] = None,
    capture_output: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        completed = subprocess.run(
            list(cmd),
            input=input_text,
            text=True,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HspoolError(f"required command not found: {cmd[0]}") from exc

    if check and completed.returncode != 0:
        raise HspoolError(format_command_failure(cmd, completed))
    return completed


def format_command_failure(
    cmd: Sequence[str], completed: subprocess.CompletedProcess[str]
) -> str:
    parts = [f"command failed ({completed.returncode}): {shlex.join(cmd)}"]
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    if stdout:
        parts.append(f"stdout: {stdout}")
    if stderr:
        parts.append(f"stderr: {stderr}")
    return "; ".join(parts)


def notify(summary: str, body: str, urgency: Optional[str] = None) -> None:
    notify_bin = shutil.which("notify-send")
    if not notify_bin:
        return
    cmd = [notify_bin]
    if urgency:
        cmd.extend(["-u", urgency])
    cmd.extend([summary, body])
    subprocess.run(cmd, check=False)
