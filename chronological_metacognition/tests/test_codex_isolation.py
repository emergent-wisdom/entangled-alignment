"""The generated reading config disables locally configured integrations."""
import io
import json
import os
import sys
import tempfile
try:
    import tomllib
except ImportError:
    import tomli as tomllib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_driver as driver


class CodexIsolationTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.workspace = self.root / 'reading'
        self.config = self.root / 'config.toml'
        self.paths = patch.object(driver, 'codex_config_paths', return_value=[self.config])
        self.paths.start()
        self.addCleanup(self.paths.stop)

    def rendered(self):
        text = driver.codex_config(self.workspace, self.root/'cli.js', 'fixture', ['graph_context'])
        return text, tomllib.loads(text)

    def test_disables_unfamiliar_names_without_copying_credentials(self):
        self.config.write_text('[mcp_servers.private_calendar]\nurl = "https://example.invalid"\n'
                               'http_headers = { Authorization = "Bearer fixture-secret-value" }\n'
                               '[plugins."private-plugin@example"]\nenabled = true\n')
        text, config = self.rendered()
        self.assertFalse(config['mcp_servers']['private_calendar']['enabled'])
        self.assertFalse(config['plugins']['private-plugin@example']['enabled'])
        self.assertNotIn('fixture-secret-value', text)
        self.assertNotIn('example.invalid', text)
        self.assertEqual(config['mcp_servers']['ug']['enabled_tools'], ['graph_context'])

    def test_intended_graph_server_remains_enabled(self):
        self.config.write_text('[mcp_servers.ug]\nenabled = false\n')
        _, config = self.rendered()
        self.assertTrue(config['mcp_servers']['ug']['enabled'])

    def test_names_round_trip_without_creating_nested_or_injected_tables(self):
        names = ['calendar.v2', 'space name', 'quote"name', 'café', 'bracket]name']
        self.config.write_text('\n'.join('[mcp_servers.'+json.dumps(n, ensure_ascii=False)+']\ncommand="unused"' for n in names))
        _, config = self.rendered()
        self.assertEqual(set(config['mcp_servers']), {'ug', *names})
        self.assertTrue(all(config['mcp_servers'][n] == {'enabled':False} for n in names))

    def test_all_layers_are_disabled(self):
        second = self.root/'ancestor.toml'
        self.config.write_text('[mcp_servers.first]\ncommand="unused"\n')
        second.write_text('[mcp_servers.second]\ncommand="unused"\n[plugins.extra]\nenabled=true\n')
        with patch.object(driver, 'codex_config_paths', return_value=[self.config,second]):
            _, config = self.rendered()
        self.assertEqual(set(config['mcp_servers']), {'ug','first','second'})
        self.assertFalse(config['plugins']['extra']['enabled'])

    def test_missing_config_is_an_empty_inventory(self):
        _, config = self.rendered()
        self.assertEqual(set(config['mcp_servers']), {'ug'})
        self.assertNotIn('plugins', config)

    def test_bad_toml_stops_without_revealing_its_contents(self):
        self.config.write_text('secret = "fixture-private-value\n')
        with self.assertRaises(SystemExit) as failure:
            self.rendered()
        self.assertIn('reading setup stopped', str(failure.exception))
        self.assertNotIn('fixture-private-value', str(failure.exception))

    def test_unreadable_config_stops(self):
        with patch.object(Path, 'open', side_effect=PermissionError('fixture-private-value')):
            with self.assertRaises(SystemExit) as failure:
                self.rendered()
        self.assertNotIn('fixture-private-value', str(failure.exception))

    def test_invalid_integration_tables_stop(self):
        for text in ['mcp_servers="bad"', 'plugins=[]', '[mcp_servers]\nserver="bad"', '[plugins]\nplugin=3']:
            with self.subTest(text=text):
                self.config.write_text(text)
                with self.assertRaises(SystemExit): self.rendered()

    def test_legacy_profile_integration_names_are_disabled(self):
        self.config.write_text('[profiles.special.mcp_servers.other]\nenabled=true\n')
        _, config = self.rendered()
        self.assertFalse(config['mcp_servers']['other']['enabled'])

    def test_profile_file_integrations_are_disabled(self):
        profile=self.root/'special.config.toml'
        profile.write_text('[plugins.extra]\nenabled=true\n')
        with patch.object(driver, 'codex_config_paths', return_value=[profile]):
            _, config = self.rendered()
        self.assertFalse(config['plugins']['extra']['enabled'])

    def test_unrelated_model_profile_still_works(self):
        self.config.write_text('[profiles.special]\nmodel="fixture"\n')
        _, config = self.rendered()
        self.assertEqual(set(config['mcp_servers']), {'ug'})

    def test_setup_parse_failure_precedes_any_workspace_write_or_source_load(self):
        self.config.write_text('broken = "\n')
        with patch.object(driver,'load_source') as load:
            with self.assertRaises(SystemExit):
                driver.command_setup(SimpleNamespace(workspace=str(self.workspace)))
        self.assertFalse(self.workspace.exists())
        load.assert_not_called()


class ConfigDiscoveryTests(unittest.TestCase):
    def test_custom_home_and_workspace_ancestors_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); home=root/'alternate'; home.mkdir()
            profile=home/'special.config.toml'; profile.write_text('model="fixture"\n')
            workspace=root/'project'/'reading'
            with patch.dict(os.environ, {'CODEX_HOME':str(home)}):
                files=driver.codex_config_paths(workspace)
            self.assertIn(home/'config.toml',files)
            self.assertIn(profile,files)
            self.assertIn(root/'project'/'.codex'/'config.toml',files)
            self.assertNotIn(workspace/'.codex'/'config.toml',files)
            self.assertEqual(len(files),len(set(files)))

    def test_default_home_is_used_without_environment_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.dict(os.environ, {}, clear=True),patch.object(Path,'home',return_value=root):
                files=driver.codex_config_paths(root/'work')
            self.assertIn(root/'.codex'/'config.toml',files)
