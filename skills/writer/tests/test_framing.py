"""Tests for framing state (stdlib unittest only).

Covers: propose/list/select roundtrip, pitch rendering, north-star
handoff, unknown-frame rejection, and the density-coverage heuristic.
Run: `python3 -m unittest discover -s skills/writer/tests -t .`
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO / "skills" / "writer" / "src"))

import writer  # noqa: E402


class FramingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="writer-framing-test-")
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.saved = dict(os.environ)
        os.environ.pop("WRITER_DIR", None)
        self._cwd = os.getcwd()
        os.chdir(self.root)

    def tearDown(self):
        os.chdir(self._cwd)
        os.environ.clear()
        os.environ.update(self.saved)
        self.tmp.cleanup()

    def _two(self):
        return writer.framings_propose([
            {"thesis": "Jev decides; code acts.",
             "why_matters": "Judgment becomes an API.",
             "contrast": "LLMs generate, Jev decides.",
             "mental_model": "Probabilistic function at the boundary.",
             "risk": "Undersells calibration work."},
            {"thesis": "Jev is a faster classifier.",
             "why_matters": "Speed.",
             "contrast": "Slow vs fast.",
             "mental_model": "Turbocharged if-else.",
             "risk": "Technically misleading: hides distributions."},
        ])

    def test_propose_list_ids(self):
        added = self._two()
        self.assertEqual([c["id"] for c in added], ["frame-001", "frame-002"])
        self.assertTrue(all(c["status"] == "candidate" for c in added))
        self.assertEqual(len(writer.framings_list()), 2)

    def test_pitch_is_comparable_text(self):
        pitch = writer.framing_pitch(self._two()[0])
        self.assertIn("Jev decides; code acts.", pitch)
        self.assertIn("Mental model:", pitch)

    def test_select_persists_reasoning(self):
        self._two()
        selection = writer.framings_select(
            "frame-001", "Which organizes the article?",
            "Technically truthful; the rival hides distributions.",
            judge="model")
        self.assertEqual(selection["frame_id"], "frame-001")
        merged = writer.framing_get()
        self.assertEqual(merged["thesis"], "Jev decides; code acts.")
        self.assertEqual(merged["selection"]["judge"], "model")
        statuses = {c["id"]: c["status"] for c in writer.framings_list()}
        self.assertEqual(statuses, {"frame-001": "selected",
                                    "frame-002": "candidate"})

    def test_select_unknown_rejects(self):
        with self.assertRaises(KeyError):
            writer.framings_select("frame-999", "c", "r")

    def test_brief_handoff(self):
        self._two()
        writer.framings_select("frame-001", "c", "truthful beats clever")
        writer.claims_add("Jev returns probability distributions",
                          claim_type="technical", importance="high",
                          draft_id="draft-001")
        writer.claims_add("I like the vibe", claim_type="opinion",
                          importance="low", draft_id="draft-001")
        brief = writer.framing_brief()
        self.assertIn("Core thesis:", brief)
        self.assertIn("Do not lose:", brief)
        self.assertIn("Jev returns probability distributions", brief)
        self.assertNotIn("I like the vibe", brief)

    def test_brief_without_selection_errors(self):
        with self.assertRaises(FileNotFoundError):
            writer.framing_brief()

    def test_coverage_flags_lost_claims(self):
        writer.project_init("coverage")
        writer.drafts_save("Jev returns probability distributions for every "
                           "question asked today.",
                           reason="parent")
        writer.drafts_save("Jev is fast and friendly for all users.",
                           parent="draft-001", reason="thin revision")
        writer.claims_add("Jev returns probability distributions",
                          claim_type="technical", importance="high",
                          draft_id="draft-001")
        report = writer.claims_coverage("draft-001", "draft-002")
        self.assertEqual(report["preserved"], [])
        self.assertEqual(report["possibly_lost"], ["claim-001"])


if __name__ == "__main__":
    unittest.main()
