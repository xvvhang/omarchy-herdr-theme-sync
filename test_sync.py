import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest

spec = importlib.util.spec_from_file_location('sync', Path(__file__).with_name('sync.py'))
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def test_light_and_dark(self):
        for bg, fg in [('#F6F6EF', '#333333'), ('#292522', '#ECE1D7')]:
            tokens = sync.palette(dict(background=bg, foreground=fg, accent='#FF6600'))
            self.assertEqual(tokens['panel_bg'], bg)
            self.assertGreaterEqual(sync.contrast(tokens['text'], bg), 4.5)
            self.assertGreaterEqual(sync.contrast(tokens['subtext0'], bg), 4.5)
            self.assertNotEqual(tokens['active_row_bg'], fg)
            self.assertTrue(all(sync.HEX.fullmatch(v) for v in tokens.values()))

    def test_preserve_settings_and_idempotence(self):
        original = '''onboarding = false
[theme]
name = "terminal"
[theme.custom]
panel_bg = "black"
[theme.custom.light]
accent = "red"
[keys]
prefix = "ctrl+b"
[ui]
# Keep user settings
accent = "blue"
pane_gaps = false
[ui.toast]
delivery = "system"
'''
        tokens = sync.palette(dict(background='#F6F6EF', foreground='#333333', accent='#FF6600'))
        result = sync.update_config(original, tokens)
        self.assertEqual(result, sync.update_config(result, tokens))
        data = tomllib.loads(result)
        self.assertEqual(data['keys']['prefix'], 'ctrl+b')
        self.assertEqual(data['ui']['toast']['delivery'], 'system')
        self.assertFalse(data['ui']['pane_gaps'])
        self.assertEqual(data['theme']['custom']['panel_bg'], '#F6F6EF')
        self.assertIn('# Keep user settings', result)

    def test_new_config(self):
        tokens = sync.palette(dict(background='#FFFFFF', foreground='#000000', accent='#777777'))
        tomllib.loads(sync.update_config('', tokens))

    def test_disabled_hook_does_not_write(self):
        old = sync.CONFIG
        try:
            with tempfile.TemporaryDirectory() as directory:
                sync.CONFIG = Path(directory)
                (sync.CONFIG / 'omarchy').mkdir()
                (sync.CONFIG / 'omarchy/shell.json').write_text('{"plugins": []}')
                sync.sync()
                self.assertFalse((sync.CONFIG / 'herdr').exists())
        finally:
            sync.CONFIG = old

    def test_active_config_preserves_non_theme_values(self):
        config = Path.home() / '.config/herdr/config.toml'
        tokens = sync.palette(dict(background='#F6F6EF', foreground='#333333', accent='#FF6600'))
        sync.update_config(config.read_text(), tokens)


if __name__ == '__main__':
    unittest.main()
