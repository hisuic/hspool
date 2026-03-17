import unittest
from unittest.mock import patch

from hspoollib.app import (
    AppConfig,
    Item,
    build_browser_target,
    build_search_url,
    handle_browser_item,
    is_http_url,
    open_in_browser,
    prepare_browser_command,
)


class BrowserHelpersTest(unittest.TestCase):
    def test_is_http_url_accepts_http(self) -> None:
        self.assertTrue(is_http_url("http://example.com"))

    def test_is_http_url_accepts_https(self) -> None:
        self.assertTrue(is_http_url("https://example.com"))

    def test_is_http_url_rejects_plain_text(self) -> None:
        self.assertFalse(is_http_url("linux rofi script mode"))

    def test_build_search_url_encodes_query(self) -> None:
        self.assertEqual(
            build_search_url(
                "linux rofi script mode",
                "https://www.google.com/search?q={query}",
            ),
            "https://www.google.com/search?q=linux+rofi+script+mode",
        )

    def test_build_browser_target_preserves_direct_url(self) -> None:
        self.assertEqual(
            build_browser_target(
                "https://github.com",
                "https://www.google.com/search?q={query}",
            ),
            "https://github.com",
        )

    def test_build_browser_target_ignores_item_action(self) -> None:
        config = AppConfig(
            config_path=None,  # type: ignore[arg-type]
            data_files=[],
            public_file=None,  # type: ignore[arg-type]
            private_file=None,  # type: ignore[arg-type]
            browser_command="firefox",
            search_url="https://www.google.com/search?q={query}",
        )
        copy_item = Item(
            content="linux rofi script mode",
            action="copy",
            description="search docs",
        )
        exec_item = Item(
            content="linux rofi script mode",
            action="exec",
            description="search docs",
        )

        with patch("hspoollib.app.open_in_browser") as open_in_browser, patch(
            "hspoollib.app.notify"
        ):
            handle_browser_item(copy_item, config)
            copy_target = open_in_browser.call_args.args[0]

        with patch("hspoollib.app.open_in_browser") as open_in_browser, patch(
            "hspoollib.app.notify"
        ):
            handle_browser_item(exec_item, config)
            exec_target = open_in_browser.call_args.args[0]

        self.assertEqual(copy_target, exec_target)
        self.assertEqual(
            copy_target,
            "https://www.google.com/search?q=linux+rofi+script+mode",
        )

    def test_prepare_browser_command_adds_new_window_for_firefox(self) -> None:
        self.assertEqual(
            prepare_browser_command(["firefox"]),
            ["firefox", "--new-window"],
        )

    def test_prepare_browser_command_does_not_duplicate_new_window(self) -> None:
        self.assertEqual(
            prepare_browser_command(["firefox", "--new-window"]),
            ["firefox", "--new-window"],
        )

    def test_open_in_browser_uses_new_window_for_firefox(self) -> None:
        with patch("hspoollib.app.subprocess.Popen") as popen:
            open_in_browser("https://github.com", "firefox")
        self.assertEqual(
            popen.call_args.args[0],
            ["firefox", "--new-window", "https://github.com"],
        )


if __name__ == "__main__":
    unittest.main()
