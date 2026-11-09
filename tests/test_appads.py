import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from appads import extract_records, parse_line, parse_text  # noqa: E402
from build import build  # noqa: E402
from check import validate  # noqa: E402
from common import load_config  # noqa: E402


class ParseTest(unittest.TestCase):
    def test_record(self):
        p = parse_line("Google.com , pub-1, Direct, F08C47FEC0942FA0")
        self.assertEqual(p.record.line(), "google.com, pub-1, DIRECT, f08c47fec0942fa0")

    def test_repairs(self):
        self.assertEqual(parse_line("rubiconproject.com, 15854, RESELLER 0bfd66d529a55807").record.line(),
                         "rubiconproject.com, 15854, RESELLER, 0bfd66d529a55807")
        self.assertEqual(parse_line("xandr.com, 11316, RESELLE").record.rel, "RESELLER")
        recs = [p.record.line() for p in parse_text('bigo.sg, 23166789, DIRECT","appnexus.com, 11924, RESELLER') if p.record]
        self.assertEqual(recs, ["bigo.sg, 23166789, DIRECT", "appnexus.com, 11924, RESELLER"])

    def test_rejects(self):
        for bad in ["smaato.com,to be added,DIRECT", "keenkale, 1, RESELLER", "a.com, 1, SELLER",
                    "fyber.com,>>>>> INSERT PUBLISHER ID HERE <<<<<,DIRECT", "ironsrc.com, [yourId], Direct",
                    "<html>", "Resellers as of March 25, 2025"]:
            self.assertEqual(parse_line(bad).kind, "error", bad)

    def test_variables(self):
        self.assertEqual(parse_line("ownerdomain=lavkastudios.com").var, ("ownerdomain", "lavkastudios.com"))

    def test_extract_glued_email(self):
        text = ("video.unrulymedia.com, 869839498, RESELLERgreyalpha.agency,\ngreyGKcqIXYbcwR, RESELLERvideoshakers.tv,\n"
                "58204917364298, RESELLER, 819580c2afa8a3aatradplusad.com, bf0675b350e773de, RESELLER\n"
                "elixirvideo.co,\n30273, Resellere-planning.net, 8531992c955a0666, RESELLER, c1ba615865ed87b2")
        self.assertEqual([r.line() for r in extract_records(text)], [
            "video.unrulymedia.com, 869839498, RESELLER",
            "greyalpha.agency, greyGKcqIXYbcwR, RESELLER",
            "videoshakers.tv, 58204917364298, RESELLER, 819580c2afa8a3aa",
            "tradplusad.com, bf0675b350e773de, RESELLER",
            "elixirvideo.co, 30273, RESELLER",
            "e-planning.net, 8531992c955a0666, RESELLER, c1ba615865ed87b2",
        ])


class BuildTest(unittest.TestCase):
    """The file built from the repository passes all guardrails."""

    def test_repo_builds_and_validates(self):
        cfg = load_config()
        text, _ = build(cfg)
        self.assertEqual(validate(text, cfg), [])

    def test_guard_catches_broken_file(self):
        cfg = load_config()
        text, _ = build(cfg)
        self.assertTrue(validate(text.replace("pub-1412074265122888", "pub-0"), cfg))   # a required line is missing
        self.assertTrue(validate("<html>oops</html>\n", cfg))                            # HTML instead of the file
        self.assertTrue(validate(text + "managerdomain=bidmachine.io\n", cfg))           # variable that is not allowed


if __name__ == "__main__":
    unittest.main()
