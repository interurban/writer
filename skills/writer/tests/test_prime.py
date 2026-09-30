"""Tests for writer Prime-access introspection (stdlib unittest only).

Covers: empty-state readiness, synthetic Prime homes (settings merge,
auth IDs without values, catalog describe), five-role policy + legacy
compat, role resolution, OpenRouter refresh/cache (mocked HTTP).
Run: `python3 -m unittest discover -s skills/writer/tests -t .`
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO / "skills" / "writer" / "src"))

import writer  # noqa: E402


class IsolatedEnv(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="writer-prime-test-")
        self.root = Path(self.tmp.name)
        self.prime_home = self.root / "prime-home"
        self.prime_home.mkdir()
        self.work = self.root / "work"
        self.work.mkdir()
        self.saved = dict(os.environ)
        os.environ["PRIME_AGENT_CODING_AGENT_DIR"] = str(self.prime_home)
        os.environ["WRITER_DIR"] = str(self.work)
        os.environ.pop("OPENROUTER_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def write_prime(self, auth=None, settings=None, catalog=None):
        if auth is not None:
            (self.prime_home / "auth.json").write_text(json.dumps(auth))
        if settings is not None:
            (self.prime_home / "settings.json").write_text(json.dumps(settings))
        if catalog is not None:
            models_dir = self.prime_home / "models"
            models_dir.mkdir(exist_ok=True)
            (models_dir / "catalog.v1.json").write_text(json.dumps(catalog))


class EmptyStateTests(IsolatedEnv):
    def test_not_ready_without_credentials(self):
        status = writer.models_ready()
        self.assertFalse(status["ready"])
        self.assertEqual(status["providers"], [])
        self.assertTrue(any("/login" in r for r in status["reasons"]))
        self.assertTrue(any("OPENROUTER_API_KEY" in r for r in status["reasons"]))

    def test_current_unknown(self):
        current = writer.models_current()
        self.assertEqual(current,
                         {"provider": None, "model": None, "thinking": None,
                          "subagent_default": "inherit",
                          "selector_known": False})

    def test_describe_unknown_stays_unknown(self):
        self.assertEqual(
            writer.models_describe("openrouter/some-model"),
            {"known": False, "provider": "openrouter", "id": "some-model"})

    def test_refresh_without_key(self):
        result = writer.models_refresh_openrouter()
        self.assertFalse(result["live"])
        self.assertIn("OPENROUTER_API_KEY not found", result["reason"])
        self.assertNotIn("sk-", json.dumps(result))

    def test_status_shape(self):
        status = writer.models_status()
        self.assertEqual(sorted(status),
                         ["policy", "primary", "providers", "ready", "reasons"])


class SyntheticPrimeTests(IsolatedEnv):
    SECRET = "SECRET-VALUE-MUST-NEVER-LEAK"

    def setUp(self):
        super().setUp()
        self.write_prime(
            auth={"openai-codex": {"access": self.SECRET}},
            settings={"defaultProvider": "openai-codex",
                      "defaultModel": "gpt-5.5"},
            catalog={"models": [{
                "provider": "openai-codex", "id": "gpt-5.5",
                "name": "GPT-5.5", "reasoning": True,
                "contextWindow": 400000, "maxTokens": 32000,
                "input": ["text"],
                "cost": {"input": 1.0, "output": 8.0,
                         "cacheRead": 0.25, "cacheWrite": 1.0}}]})

    def test_auth_ids_without_values(self):
        self.assertEqual(writer.prime_auth_providers(), ["openai-codex"])
        blob = json.dumps([writer.models_providers(),
                           writer.models_ready(), writer.models_status()])
        self.assertNotIn(self.SECRET, blob)

    def test_settings_merge(self):
        self.assertEqual(
            writer.prime_settings(),
            {"default_provider": "openai-codex", "default_model": "gpt-5.5",
             "subagent_default_model": None, "thinking": None})

    def test_describe_known(self):
        info = writer.models_describe("openai-codex/gpt-5.5")
        self.assertTrue(info["known"])
        self.assertEqual(info["display_name"], "GPT-5.5")
        self.assertEqual(info["context_window"], 400000)
        self.assertEqual(info["cost"]["output"], 8.0)

    def test_env_credential_detected_by_name_only(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
        providers = {p["provider"]: p for p in writer.models_providers()}
        self.assertEqual(providers["openrouter"]["via_env"],
                         "OPENROUTER_API_KEY")
        self.assertNotIn("sk-or-fake",
                         json.dumps([providers, writer.models_status()]))


class PolicyTests(IsolatedEnv):
    def test_five_roles_default_inherit(self):
        policy = writer.models_policy()
        self.assertEqual(sorted(policy),
                         ["critic", "judge", "primary", "research",
                          "verification"])
        for role in ("primary", "research", "judge"):
            self.assertEqual(policy[role], {"model": "inherit"})

    def test_legacy_v1_file(self):
        (self.work / "models.json").write_text(
            json.dumps({"writer": {"model": "openrouter/x"}}))
        self.assertEqual(writer.models_policy()["primary"],
                         {"model": "openrouter/x"})
        self.assertEqual(writer.models_get()["primary"],
                         {"model": "openrouter/x"})

    def test_role_resolution(self):
        writer.models_set_policy({"critic": {"model": "openrouter/y"}})
        self.assertEqual(
            writer.models_role("critic")["selector"], "openrouter/y")
        self.assertEqual(
            writer.models_role("verification"),
            {"selector": None, "thinking_hint": "high",
             "note": "inherit model, high thinking"})
        self.assertEqual(
            writer.models_role("nope")["note"][:12], "unknown role")
        pick = writer.models_role(
            "critic", "openai-codex/gpt-5.5",
            [{"selector": "openai-codex/gpt-5.5"},
             {"selector": "openrouter/moonshotai/kimi-k2.6"}])
        # Explicit override wins over family-picking.
        self.assertEqual(pick["selector"], "openrouter/y")

    def test_family_pick_when_inherit(self):
        writer.models_set_policy({"critic": {"model": "inherit"}})
        # "inherit" model with no strategy resolves to inherit.
        role = writer.models_role("critic", "a/m1", ["b/m2"])
        self.assertIsNone(role["selector"])


class OpenRouterRefreshTests(IsolatedEnv):
    def test_live_listing_cached_without_secrets(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
        payload = {"data": [
            {"id": "moonshotai/kimi-k2.6", "name": "Kimi K2.6",
             "context_length": 262144,
             "pricing": {"prompt": "0.0000006", "completion": "0.0000024"}}]}
        response = mock.MagicMock()
        response.read.return_value = json.dumps(payload).encode()
        response.__enter__.return_value = response
        with mock.patch("urllib.request.urlopen",
                        return_value=response) as urlopen:
            result = writer.models_refresh_openrouter()
            (args, _) = urlopen.call_args
            self.assertIn("openrouter.ai/api/v1/models", args[0].full_url)
            self.assertEqual(
                args[0].get_header("Authorization"), "Bearer sk-or-fake")
        self.assertTrue(result["live"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["models"][0]["id"], "moonshotai/kimi-k2.6")
        cached = writer.models_cached_openrouter()
        self.assertTrue(cached["cached"])
        self.assertNotIn("sk-or-fake", json.dumps(cached))
        cache_file = self.work / "cache" / "openrouter-models.json"
        self.assertNotIn("sk-or-fake", cache_file.read_text())

    def test_http_failure_is_data(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-fake"
        with mock.patch("urllib.request.urlopen",
                        side_effect=OSError("no network")):
            result = writer.models_refresh_openrouter()
        self.assertFalse(result["live"])
        self.assertIn("no network", result["reason"])


class MigrationTests(unittest.TestCase):
    """Legacy `.writer/` auto-migrates to `writing/` on first open."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="writer-migrate-test-")
        self.root = Path(self.tmp.name)
        self.saved_cwd = os.getcwd()
        self.saved = dict(os.environ)
        os.environ.pop("WRITER_DIR", None)

    def tearDown(self):
        os.chdir(self.saved_cwd)
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def _seed_legacy(self, workdir: Path) -> None:
        legacy = workdir / ".writer"
        (legacy / "drafts").mkdir(parents=True)
        (legacy / "project.json").write_text(json.dumps({"name": "old"}))

    def test_legacy_migrates_on_open(self):
        workdir = self.root / "proj"
        workdir.mkdir()
        self._seed_legacy(workdir)
        os.chdir(workdir)
        project = writer.project_get()
        self.assertEqual(project["name"], "old")
        self.assertTrue((workdir / "writing" / "project.json").exists())
        self.assertFalse((workdir / ".writer").exists())

    def test_new_wins_when_both_exist(self):
        workdir = self.root / "proj"
        workdir.mkdir()
        self._seed_legacy(workdir)
        new = workdir / "writing"
        (new / "drafts").mkdir(parents=True)
        (new / "project.json").write_text(json.dumps({"name": "new"}))
        os.chdir(workdir)
        self.assertEqual(writer.project_get()["name"], "new")
        # Legacy left untouched: never merge.
        self.assertTrue((workdir / ".writer" / "project.json").exists())

    def test_fresh_init_uses_visible_dir(self):
        workdir = self.root / "fresh"
        workdir.mkdir()
        os.chdir(workdir)
        writer.project_init("hello")
        self.assertTrue((workdir / "writing" / "project.json").exists())
        self.assertFalse((workdir / ".writer").exists())

    def test_explicit_roots_untouched(self):
        legacy = self.root / "explicit" / ".writer"
        (legacy / "drafts").mkdir(parents=True)
        (legacy / "project.json").write_text(json.dumps({"name": "old"}))
        self.assertEqual(
            writer.project_get(legacy)["name"], "old")
        self.assertFalse((self.root / "explicit" / "writing").exists())


class ArchiveTests(unittest.TestCase):
    """New topics archive the old project; nothing is ever overwritten."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="writer-archive-test-")
        self.root = Path(self.tmp.name)
        self.saved_cwd = os.getcwd()
        self.saved = dict(os.environ)
        os.environ.pop("WRITER_DIR", None)

    def tearDown(self):
        os.chdir(self.saved_cwd)
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def _seed(self, workdir: Path, name: str = "old topic") -> None:
        workdir.mkdir(parents=True, exist_ok=True)
        os.chdir(workdir)
        writer.project_init(name)

    def test_new_topic_archives_and_starts_fresh(self):
        workdir = self.root / "proj"
        self._seed(workdir)
        writer.drafts_save("old body", reason="old")
        result = writer.project_new("New topic", goal="fresh start")
        self.assertEqual(result["project"]["name"], "New topic")
        self.assertIsNotNone(result["archived"])
        archived = Path(result["archived"]["archived_to"])
        self.assertTrue((archived / "project.json").exists())
        self.assertTrue((archived / "drafts" / "draft-001.md").exists())
        # Fresh state: no drafts, no current pointer.
        self.assertEqual(writer.drafts_list(), [])
        self.assertIsNone(writer.project_get()["current_draft_id"])

    def test_new_topic_without_archive_refuses(self):
        workdir = self.root / "proj"
        self._seed(workdir)
        with self.assertRaises(FileExistsError):
            writer.project_new("New topic", archive=False)
        self.assertEqual(writer.project_get()["name"], "old topic")

    def test_archive_missing_errors(self):
        workdir = self.root / "empty"
        workdir.mkdir()
        os.chdir(workdir)
        with self.assertRaises(FileNotFoundError):
            writer.project_archive()

    def test_archive_is_reopenable(self):
        workdir = self.root / "proj"
        self._seed(workdir)
        archived_to = writer.project_archive()["archived_to"]
        self.assertEqual(writer.project_get(archived_to)["name"], "old topic")


if __name__ == "__main__":
    unittest.main()
