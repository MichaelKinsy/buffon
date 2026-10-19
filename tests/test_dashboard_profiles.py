# SPDX-License-Identifier: Apache-2.0
"""The profiles of the harnesses (profiles/<project>.toml and profiles/assets/): what each project says about itself, stored from its own README at a pinned ref.
The files are checked against the schema, every logo is the file the profile hashes and passes the SVG or PNG rules, a changed logo or a moving ref stops the build,
the site carries a copy of each logo, and the maintainer tool's reading of a README is deterministic. Nothing here uses the network."""
import hashlib
import shutil
import struct
import zlib
import os
import tempfile
import tomllib
import unittest

from buffon.dashboard import build as dashboard, model, profiles_check
from tests.report_demo import demo_raw
from tests.test_dashboard import ROOT, built
from tools import profiles_refresh

PROFILES = os.path.join(ROOT, "profiles")
ASSETS = os.path.join(PROFILES, "assets")
GOOD = {"project": "X", "harnesses": ["x"], "maker": "M", "maker_url": "https://m.example", "tagline": "T", "tagline_source": "https://m.example/readme",
        "retrieved": "2026-10-18", "licence": "MIT", "links": {"home": "https://x.example", "repo": "https://github.com/o/x"}, "quotes": [{"text": "a b c", "source": "https://m.example/q", "about": "goal"}]}
README = {"readme_url": "https://github.com/o/x/blob/v1.0.0/README.md", "readme_ref": "v1.0.0", "readme_title": "X", "readme_head": ["One.", "Two."]}
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><path d="M0 0h8v8z" fill="#123456"/></svg>\n'
# a 1x1 PNG
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


def parsed(name):
    with open(os.path.join(PROFILES, name), "rb") as f:
        return tomllib.load(f)


def with_logo(tmp, data, content=SVG, name="x.svg"):
    """A profiles folder in tmp holding x.toml with the logo keys for content stored as name."""
    os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
    with open(os.path.join(tmp, "assets", name), "wb") as f:
        f.write(content)
    return dict(data, **README, logo=name, logo_source="https://x.example/logo", logo_sha256=hashlib.sha256(content).hexdigest())

def with_mark(tmp, data, content, name, **extra):
    """The profile data with a mark stored as name in tmp/assets (its hash, source and ref included)."""
    os.makedirs(os.path.join(tmp, "assets"), exist_ok=True)
    with open(os.path.join(tmp, "assets", name), "wb") as f:
        f.write(content)
    return dict(data, mark=name, mark_source="https://x.example/mark", mark_ref="v1.0.0", mark_sha256=hashlib.sha256(content).hexdigest(), **extra)



def write_profile(tmp, data, name="x.toml"):
    with open(os.path.join(tmp, name), "w", encoding="utf-8") as f:
        f.write(profiles_refresh.toml_text(data))


def make_png(width, height):
    """A valid PNG of one flat colour, width x height."""
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    rows = b"".join(b"\x00" + b"\x10\x20\x30" * width for _ in range(height))
    return profiles_check.PNG_MAGIC + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


class Schema(unittest.TestCase):
    def test_every_real_profile_is_valid_and_names_arms_that_exist(self):
        profiles = dashboard.load_profiles(PROFILES)
        self.assertGreaterEqual(len(profiles), 8)
        arms = set(os.listdir(os.path.join(ROOT, "arms")))
        seen = set()
        for p in profiles:
            self.assertEqual(dashboard.check_profile(parsed(p["slug"] + ".toml"), p["slug"]), [])
            for h in p["harnesses"]:
                self.assertIn(h, arms, p["slug"])
                self.assertNotIn(h, seen, f"{h} is in two profiles")
                seen.add(h)
            self.assertLessEqual(len(p["quotes"]), 3)
            for q in p["quotes"]:
                self.assertLessEqual(len(q["text"].split()), 40, p["slug"])
                self.assertTrue(q["source"].startswith("https://"))
            self.assertRegex(p["retrieved"], r"^\d{4}-\d{2}-\d{2}$")

    def test_a_profile_that_breaks_the_schema_is_named_with_every_problem(self):
        self.assertEqual(dashboard.check_profile(GOOD, "x.toml"), [])
        bad = dict(GOOD, maker_url="http://m.example", links={"home": "http://x.example", "blog": "https://x.example"}, quotes=[dict(GOOD["quotes"][0], text="word " * 41)] + GOOD["quotes"] * 3)
        problems = " | ".join(dashboard.check_profile(bad, "x.toml"))
        for part in ("maker_url is not an https URL", "link home is not an https URL", "unknown link blog", "4 quotes, at most 3", "quote 1 has more than 40 words"):
            self.assertIn(part, problems)
        self.assertIn("missing licence", " ".join(dashboard.check_profile({k: v for k, v in GOOD.items() if k != "licence"}, "x.toml")))

    def test_a_bad_profile_stops_the_build_before_the_slow_part_and_two_profiles_cannot_claim_one_harness(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("a.toml", "b.toml"):
                with open(os.path.join(tmp, name), "w") as f:
                    f.write('project = "P"\nharnesses = ["x"]\nmaker = "M"\nmaker_url = "https://m.example"\ntagline = "T"\ntagline_source = "https://m.example"\nretrieved = "2026-10-17"\nlicence = "MIT"\n')
            with self.assertRaisesRegex(dashboard.DashboardError, "harness x is also in a.toml"):
                dashboard.load_profiles(tmp)
            os.remove(os.path.join(tmp, "b.toml"))
            with open(os.path.join(tmp, "c.toml"), "w") as f:
                f.write('project = "P"\n')
            with self.assertRaisesRegex(dashboard.DashboardError, "c.toml: missing maker"):
                dashboard.load_profiles(tmp)
            with self.assertRaises(dashboard.DashboardError):
                dashboard.build(["/nowhere"], os.path.join(tmp, "site"), profiles_dir=tmp)   # fails on the profile, not on the missing run

    def test_the_manifest_notes_of_a_harness_travel_with_it(self):
        self.assertIn("Pi-compatible runtime", model.command_of("pibolt")["notes"])


class Readme(unittest.TestCase):
    def test_every_real_profile_with_readme_keys_has_them_all_and_a_pinned_ref(self):
        with_keys = 0
        for name in sorted(os.listdir(PROFILES)):
            if not name.endswith(".toml"):
                continue
            data = parsed(name)
            if "readme_url" not in data:
                self.assertFalse(any(k in data for k in dashboard.PROFILE_README), name)
                continue
            with_keys += 1
            self.assertEqual(dashboard.check_profile(data, name), [], name)
            self.assertFalse(profiles_check.branch_name(data["readme_ref"]), name)
            self.assertIn(f"/blob/{data['readme_ref']}/", data["readme_url"], name)
            self.assertTrue(1 <= len(data["readme_head"]) <= 2, name)
            self.assertTrue(data["readme_title"].strip(), name)
        self.assertGreaterEqual(with_keys, 8)

    def test_the_loaded_profile_carries_the_readme_and_the_logo_path_and_none_when_there_are_none(self):
        for p in dashboard.load_profiles(PROFILES):
            data = parsed(p["slug"] + ".toml")
            if "readme_url" in data:
                self.assertEqual(p["readme"]["url"], data["readme_url"])
                self.assertEqual(p["readme"]["ref"], data["readme_ref"])
                self.assertEqual(p["readme"]["head"], data["readme_head"])
                self.assertEqual(p["readme"]["retrieved"], data["retrieved"])
                self.assertEqual(p["readme"]["repo"], data["links"]["repo"].split("github.com/")[1])
            if "logo" in data:
                self.assertEqual(p["logo"], "assets/profiles/" + data["logo"])
                self.assertEqual(p["logo_source"], data["logo_source"])
            else:
                self.assertIsNone(p["logo"])
                self.assertIsNone(p["logo_source"])
            if "mark" in data:
                self.assertEqual((p["mark"], p["mark_source"], p["mark_ref"], p["mark_pixel"]), ("assets/profiles/" + data["mark"], data["mark_source"], data["mark_ref"], "mark_crop" in data))
            else:
                self.assertIsNone(p["mark"])
                self.assertEqual(p["monogram"], data.get("monogram"))
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, dict(GOOD))
            [p] = dashboard.load_profiles(tmp)
            self.assertEqual((p["readme"], p["logo"], p["logo_source"]), (None, None, None))
            write_profile(tmp, dict(GOOD, **README))
            [p] = dashboard.load_profiles(tmp)
            self.assertEqual(p["readme"], {"url": README["readme_url"], "ref": "v1.0.0", "repo": "o/x", "title": "X", "head": ["One.", "Two."], "retrieved": "2026-10-18"})

    def test_a_branch_as_the_ref_or_three_paragraphs_or_a_partial_set_fail(self):
        for ref in ("main", "master", "HEAD", "refs/heads/dev", "origin/main"):
            self.assertTrue(any("is a branch" in p for p in dashboard.check_profile(dict(GOOD, **dict(README, readme_ref=ref)), "x.toml")), ref)
        problems = dashboard.check_profile(dict(GOOD, **dict(README, readme_head=["a", "b", "c"])), "x.toml")
        self.assertTrue(any("1 to 2 non-empty paragraphs" in p for p in problems), problems)
        self.assertTrue(dashboard.check_profile(dict(GOOD, **dict(README, readme_head=[])), "x.toml") or dashboard.check_profile(dict(GOOD, **dict(README, readme_head=[" "])), "x.toml"))
        for key in dashboard.PROFILE_README:
            part = {k: v for k, v in README.items() if k != key}
            self.assertTrue(any("go together" in p for p in dashboard.check_profile(dict(GOOD, **part), "x.toml")), key)
        self.assertTrue(any("readme_url is not an https URL" in p for p in dashboard.check_profile(dict(GOOD, **dict(README, readme_url="http://x/README.md")), "x.toml")))

    def test_a_bad_ref_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, dict(GOOD, **dict(README, readme_ref="main")))
            with self.assertRaisesRegex(dashboard.DashboardError, "x.toml: readme_ref main is a branch"):
                dashboard.load_profiles(tmp)


class Logos(unittest.TestCase):
    def real_logos(self):
        return [(name, parsed(name)) for name in sorted(os.listdir(PROFILES)) if name.endswith(".toml") and "logo" in parsed(name)]

    def test_every_logo_is_the_file_its_hash_names_and_stays_within_the_rules(self):
        logos = self.real_logos()
        self.assertTrue(logos)
        for name, data in logos:
            with open(os.path.join(ASSETS, data["logo"]), "rb") as f:
                raw = f.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), data["logo_sha256"], name)
            self.assertTrue(data["logo_source"].startswith("https://"), name)
            if data["logo"].endswith(".svg"):
                self.assertEqual(profiles_check.svg_problems(raw), [], name)
            else:
                self.assertEqual(profiles_check.raster_problems(raw), [], name)
                self.assertLessEqual(len(raw), 250 * 1024)
                self.assertLessEqual(profiles_check.raster_size(raw)[0], 960)
        used = {d["logo"] for _, d in logos} | {parsed(n)["mark"] for n in os.listdir(PROFILES) if n.endswith(".toml") and "mark" in parsed(n)}
        for file in os.listdir(ASSETS):
            self.assertIn(file, used, f"{file} is in profiles/assets and no profile uses it")

    def test_a_logo_changed_after_it_was_stored_fails_the_build_naming_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, with_logo(tmp, GOOD))
            self.assertEqual(dashboard.load_profiles(tmp)[0]["logo"], "assets/profiles/x.svg")
            with open(os.path.join(tmp, "assets", "x.svg"), "ab") as f:
                f.write(b"<!-- changed -->")
            with self.assertRaisesRegex(dashboard.DashboardError, r"x\.toml: logo file x\.svg does not match its logo_sha256"):
                dashboard.load_profiles(tmp)
            os.remove(os.path.join(tmp, "assets", "x.svg"))
            with self.assertRaisesRegex(dashboard.DashboardError, r"logo file x\.svg is missing"):
                dashboard.load_profiles(tmp)

    def test_a_logo_that_breaks_the_rules_fails_even_when_its_hash_matches(self):
        evil = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><script>alert(1)</script></svg>'
        big = PNG[:16] + (961).to_bytes(4, "big") + PNG[20:]
        for content, name, part in ((evil, "x.svg", "a script element"), (big, "x.png", "961x1 px"), (PNG + b"0" * 260000, "x.png", "bytes, at most")):
            with tempfile.TemporaryDirectory() as tmp:
                write_profile(tmp, with_logo(tmp, GOOD, content, name))
                with self.assertRaisesRegex(dashboard.DashboardError, part):
                    dashboard.load_profiles(tmp)
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, with_logo(tmp, GOOD, PNG, "x.png"))
            self.assertEqual(dashboard.load_profiles(tmp)[0]["logo"], "assets/profiles/x.png")

    def test_the_logo_keys_go_together_and_a_file_name_cannot_leave_the_assets_folder(self):
        data = with_logo(tempfile.mkdtemp(), GOOD)
        for key in dashboard.PROFILE_LOGO:
            self.assertTrue(any("go together" in p for p in dashboard.check_profile({k: v for k, v in data.items() if k != key}, "x.toml")), key)
        self.assertTrue(any("must be a .svg, .png or .webp" in p for p in dashboard.check_profile(dict(data, logo="../x.svg"), "x.toml")))
        self.assertTrue(any("logo_source is not an https URL" in p for p in dashboard.check_profile(dict(data, logo_source="http://x/logo.svg"), "x.toml", ASSETS)))

    def test_the_built_site_carries_a_copy_of_every_logo_and_mark(self):
        out = built(demo_raw(rounds=2), faith=False)
        profiles = dashboard.load_profiles(PROFILES)
        files = [p[k] for p in profiles for k in ("logo", "mark") if p[k]]
        self.assertTrue(files)
        for file in files:
            with open(os.path.join(out, file), "rb") as site, open(os.path.join(ASSETS, os.path.basename(file)), "rb") as stored:
                self.assertEqual(site.read(), stored.read(), file)
        self.assertEqual(sorted(os.listdir(os.path.join(out, "assets", "profiles"))), sorted(os.path.basename(f) for f in files))
        with open(os.path.join(out, "data", "site.js"), encoding="utf-8") as f:
            text = f.read()
        for p in profiles:
            if p["mark"]:
                self.assertIn(p["mark"], text)

    def test_a_site_without_logos_has_no_profiles_assets_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, dict(GOOD, harnesses=["pi-node"]))
            out = os.path.join(tmp, "site")
            dashboard.copy_profile_logos(dashboard.load_profiles(tmp), tmp, out)
            self.assertFalse(os.path.exists(out))


class Marks(unittest.TestCase):
    """The square mark of a card: stored with its source, ref and sha256, cropped reproducibly, or the owner's own file, which is never fetched."""

    def test_every_real_profile_has_a_pinned_mark_or_initials_and_the_file_is_the_one_its_hash_names(self):
        marks = 0
        for name in sorted(os.listdir(PROFILES)):
            if not name.endswith(".toml"):
                continue
            data = parsed(name)
            if "mark" not in data:
                self.assertTrue(data.get("monogram"), f"{name} has neither a mark nor initials")
                continue
            marks += 1
            self.assertEqual(dashboard.check_profile(data, name), [], name)
            self.assertFalse(profiles_check.branch_name(data["mark_ref"]), name)
            with open(os.path.join(ASSETS, data["mark"]), "rb") as f:
                raw = f.read()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), data["mark_sha256"], name)
            if "mark_crop" in data:
                self.assertEqual(profiles_check.raster_size(raw), (128, 128), name)
                self.assertEqual(data["mark_crop"][2], data["mark_crop"][3], name)
        self.assertGreaterEqual(marks, 8)

    def test_the_pig_mark_is_the_owners_file_pinned_by_its_hash_and_is_never_fetched(self):
        data = parsed("pig.toml")
        self.assertEqual(data["mark_sha256"], "68fe0a30eb1d41cbb756af5f79894707302ab7258851c5e8a3628d7458c6adc0")
        self.assertEqual(data["mark_ref"], "d384e92715fb")
        self.assertFalse(data["mark_source"].startswith("https://"))
        self.assertTrue(data["mark_note"])

        def no_network(url):
            raise AssertionError("fetched " + url)
        said, written = profiles_refresh.place_mark(dict(data), "pig", None, "ref", no_network, assets=ASSETS)
        self.assertIsNone(written)
        self.assertIn("not fetched", said[0])
        with self.assertRaisesRegex(profiles_refresh.RefreshError, "does not match its mark_sha256"):
            profiles_refresh.place_mark(dict(data, mark_sha256="0" * 64), "pig", None, "ref", no_network, assets=ASSETS)

    def test_the_mark_keys_go_together_a_crop_is_a_square_and_a_file_that_is_not_from_a_url_needs_a_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = with_mark(tmp, GOOD, SVG, "x-mark.svg")
            self.assertEqual(dashboard.check_profile(data, "x.toml", os.path.join(tmp, "assets")), [])
            for key in dashboard.PROFILE_MARK:
                self.assertTrue(any("go together" in p for p in dashboard.check_profile({k: v for k, v in data.items() if k != key}, "x.toml", os.path.join(tmp, "assets"))), key)
            self.assertTrue(any("mark_crop" in p for p in dashboard.check_profile(dict(data, mark_crop=[0, 0, 10, 20]), "x.toml", os.path.join(tmp, "assets"))))
            self.assertTrue(any("mark_note" in p for p in dashboard.check_profile(dict(data, mark_source="somewhere private"), "x.toml", os.path.join(tmp, "assets"))))
            self.assertEqual(dashboard.check_profile(dict(data, mark_source="somewhere private", mark_note="supplied by the owner"), "x.toml", os.path.join(tmp, "assets")), [])
            self.assertTrue(any("mark_bg" in p for p in dashboard.check_profile(dict(data, mark_bg="red"), "x.toml", os.path.join(tmp, "assets"))))
            self.assertTrue(any("without a mark" in p for p in dashboard.check_profile(dict(GOOD, mark_bg="#123456"), "x.toml")))
            self.assertTrue(any("must be a .svg" in p for p in dashboard.check_profile(dict(data, mark="../x-mark.svg"), "x.toml", os.path.join(tmp, "assets"))))

    def test_a_mark_changed_after_it_was_stored_or_broken_fails_the_build_naming_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, with_mark(tmp, GOOD, SVG, "x-mark.svg"))
            self.assertEqual(dashboard.load_profiles(tmp)[0]["mark"], "assets/profiles/x-mark.svg")
            with open(os.path.join(tmp, "assets", "x-mark.svg"), "ab") as f:
                f.write(b"<!-- changed -->")
            with self.assertRaisesRegex(dashboard.DashboardError, r"x\.toml: mark file x-mark\.svg does not match its mark_sha256"):
                dashboard.load_profiles(tmp)
        evil = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><script>alert(1)</script></svg>'
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, with_mark(tmp, GOOD, evil, "x-mark.svg"))
            with self.assertRaisesRegex(dashboard.DashboardError, "a script element"):
                dashboard.load_profiles(tmp)
        with tempfile.TemporaryDirectory() as tmp:   # a cropped mark is 128 px
            write_profile(tmp, with_mark(tmp, GOOD, make_png(64, 64), "x-mark.png", mark_crop=[0, 0, 10, 10]))
            with self.assertRaisesRegex(dashboard.DashboardError, "128 x 128"):
                dashboard.load_profiles(tmp)

    @unittest.skipUnless(shutil.which("ffmpeg"), "the maintainer tool crops with ffmpeg")
    def test_a_crop_is_a_128_px_png_and_the_same_bytes_give_the_same_crop(self):
        source = make_png(300, 200)
        first = profiles_refresh.crop_mark(source, [10, 20, 100, 100])
        self.assertEqual(profiles_check.raster_size(first), (128, 128))
        self.assertEqual(profiles_refresh.crop_mark(source, [10, 20, 100, 100]), first)

    @unittest.skipUnless(shutil.which("ffmpeg"), "the maintainer tool crops with ffmpeg")
    def test_a_refresh_crops_the_mark_source_and_takes_the_ref_from_its_github_url(self):
        base = "https://raw.githubusercontent.com/o/x/v1.0.0"
        pages = {base + "/README.md": Tool.TEXT.encode(), base + "/docs/big.png": make_png(300, 300), base + "/docs/logo.svg": SVG}
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, dict(GOOD, mark_source=base + "/docs/big.png", mark_crop=[10, 10, 200, 200]))
            profiles_refresh.refresh("x", ref="v1.0.0", today="2026-10-18", profiles=tmp, get=lambda url: pages[url])
            [p] = dashboard.load_profiles(tmp)
            self.assertEqual((p["mark"], p["mark_ref"], p["mark_pixel"], p["logo"]), ("assets/profiles/x-mark.png", "v1.0.0", True, None))   # the README's own drawing is passed over: the profile names the mark
            with open(os.path.join(tmp, "assets", "x-mark.png"), "rb") as f:
                self.assertEqual(profiles_check.raster_size(f.read()), (128, 128))


class Sanitiser(unittest.TestCase):
    def svg(self, inner, attrs=""):
        return f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 8 8"{attrs}>{inner}</svg>'.encode()

    def test_the_checker_accepts_a_plain_drawing_and_rejects_what_can_run_or_load(self):
        self.assertEqual(profiles_check.svg_problems(SVG), [])
        self.assertEqual(profiles_check.svg_problems(self.svg('<defs><linearGradient id="g"/></defs><rect fill="url(#g)" width="8" height="8"/><use xlink:href="#g"/>')), [])
        bad = {"script": '<script>1</script>', "foreignObject": '<foreignObject><p/></foreignObject>', "event": '<rect onclick="x()" width="1" height="1"/>',
               "external href": '<image href="https://x.example/a.png"/>', "external xlink href": '<use xlink:href="a.svg#b"/>', "external url()": '<rect fill="url(https://x.example/a)"/>',
               "data href": '<image href="data:text/html;base64,AAAA"/>', "import": '<style>@import "a.css";</style>', "link text": '<text>https://x.example</text>',
               "javascript": '<a href="javascript:alert(1)"/>', "iframe": '<iframe/>'}
        for what, inner in bad.items():
            self.assertTrue(profiles_check.svg_problems(self.svg(inner)), what)
        self.assertEqual(profiles_check.svg_problems(self.svg('<image href="data:image/png;base64,AAAA"/>')), [])
        self.assertTrue(profiles_check.svg_problems(b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'))   # no viewBox, no size
        self.assertTrue(profiles_check.svg_problems(b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'))   # not well-formed
        self.assertTrue(profiles_check.svg_problems(b"<html></html>"))

    def test_the_sanitiser_removes_them_and_keeps_the_drawing(self):
        dirty = self.svg('<metadata>https://x.example</metadata><script>alert(1)</script><foreignObject><p/></foreignObject><a xlink:href="https://x.example"><rect onclick="x()" '
                         'fill="#123" width="8" height="8"/></a><style>@import url(https://x.example/a.css); .a{fill:red}</style><image href="https://x.example/a.png"/>', ' xmlns:i="https://i.example" i:x="1"')
        clean = profiles_check.sanitize_svg(dirty)
        self.assertEqual(profiles_check.svg_problems(clean), [])
        text = clean.decode()
        self.assertIn('fill="#123"', text)
        for gone in ("script", "foreignObject", "onclick", "x.example", "metadata"):
            self.assertNotIn(gone, text)
        self.assertEqual(profiles_check.sanitize_svg(clean), clean)   # stable
        with self.assertRaises(ValueError):
            profiles_check.sanitize_svg(b"<svg xmlns='http://www.w3.org/2000/svg'><rect/></svg>")
        with self.assertRaises(ValueError):
            profiles_check.sanitize_svg(b"not xml")

    def test_a_stored_picture_is_judged_by_its_header(self):
        self.assertEqual(profiles_check.png_size(PNG), (1, 1))
        self.assertEqual(profiles_check.raster_problems(PNG), [])
        self.assertTrue(profiles_check.raster_problems(b"GIF89a" + b"0" * 30))
        self.assertTrue(profiles_check.raster_problems(make_png(961, 10)))
        self.assertTrue(profiles_check.raster_problems(make_png(900, 900) + b"0" * 300000))


class Tool(unittest.TestCase):
    TEXT = """<p align="center">
  <a href="https://x.example"><img alt="x logo" src="docs/logo.svg" width="128"></a>
</p>
<p align="center">
  <a href="https://ci.example"><img alt="CI" src="https://img.shields.io/badge/ci-passing.svg" /></a>
</p>

> New issues are closed by default.

# The **X** Tool

[![npm](https://img.shields.io/npm/v/x)](https://npm.example/x)

X is a [small](https://x.example/small) tool with `code`, <b>bold</b> text and an image ![pic](a.png).
It runs *anywhere*.

Second paragraph here.

Third paragraph is left out.

## Install
"""

    def test_the_head_is_the_titles_first_paragraphs_as_plain_text_and_the_picture_is_the_first_image_that_is_not_a_badge(self):
        p = profiles_refresh.parse_readme(self.TEXT, "x")
        self.assertEqual(p["title"], "The X Tool")
        self.assertEqual(p["head"], ["X is a small tool with code, bold text and an image . It runs anywhere.", "Second paragraph here."])
        self.assertEqual(p["logos"][0], ("docs/logo.svg", "x logo"))

    def test_the_first_picture_before_the_first_section_is_the_project_picture_whatever_it_shows_and_a_badge_never_is(self):
        read = lambda text: profiles_refresh.parse_readme(text, "x")["logos"]
        self.assertEqual(read("# X\n\n![logo](a.svg)\n\nWords.\n"), [("a.svg", "logo")])
        self.assertEqual(read('<p align="center"><img src="b.png" alt="X project banner"></p>\n\n# X\n\nWords.\n'), [("b.png", "X project banner")])   # a banner, above the title
        self.assertEqual(read("# X\n\nWords.\n\n<img src=\"./demo.gif\" />\n\n## Install\n\n![late](c.png)\n"), [("./demo.gif", "")])   # a demo after the first paragraph; nothing after a section heading
        self.assertEqual(read("# X\n\n[![npm](https://img.shields.io/npm/v/x)](y)\n\nWords.\n"), [])
        self.assertEqual(read("Words.\n\n## Install\n\n![late](a.svg)\n"), [])
        self.assertEqual(profiles_refresh.logo_candidates([]), [])

    def test_a_stored_picture_is_a_mark_when_it_is_a_drawing_or_small_and_squarish_and_a_strip_when_it_is_a_wide_or_large_raster(self):
        self.assertEqual(profiles_check.image_kind("x.svg", SVG), "mark")
        self.assertEqual(profiles_check.image_kind("x.svg", b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 100"/>'), "mark")   # a wide wordmark is never cropped
        self.assertEqual(profiles_check.image_kind("x.png", make_png(200, 200)), "mark")
        self.assertEqual(profiles_check.image_kind("x.png", make_png(600, 200)), "strip")
        self.assertEqual(profiles_check.image_kind("x.png", make_png(500, 500)), "strip")   # large, even if square

    @unittest.skipUnless(shutil.which("ffmpeg"), "the maintainer tool scales pictures with ffmpeg")
    def test_a_large_picture_is_stored_as_a_downscaled_copy_within_the_caps_and_the_same_bytes_give_the_same_copy(self):
        big = make_png(1600, 500)
        self.assertTrue(profiles_check.raster_problems(big))
        ext, data, note = profiles_refresh.make_logo("https://x.example/a.png", big)
        self.assertIn(ext, ("png", "webp"))
        self.assertEqual(profiles_check.raster_problems(data), [])
        self.assertEqual(profiles_check.raster_size(data)[0], 960)
        self.assertEqual(profiles_refresh.make_logo("https://x.example/a.png", big)[1], data)
        small = make_png(100, 100)
        self.assertEqual(profiles_refresh.make_logo("https://x.example/a.png", small), ("png", small, "as published"))

    def test_the_head_stops_at_a_badge_row_and_a_html_head_gives_its_title(self):
        self.assertEqual(profiles_refresh.parse_readme("# X\n\nA tagline.\n\n[![b](https://img.shields.io/x)](y)\n\nMore words.\n", "x")["head"], ["A tagline."])
        p = profiles_refresh.parse_readme('<h1 align="center">Y-Tool</h1>\n\n<p align="center"><b>Y does it.</b><br>All of it.</p>\n', "y")
        self.assertEqual((p["title"], p["head"]), ("Y-Tool", ["Y does it.", "All of it."]))
        self.assertEqual(profiles_refresh.parse_readme("<p><strong>Z CLI</strong> runs here.</p>\n\n## Next\n", "z")["title"], "Z CLI")
        self.assertEqual(profiles_refresh.parse_readme("Only words.\n", "name")["title"], "name")

    def test_a_logo_url_is_resolved_against_the_ref_and_a_branch_ref_is_refused_before_any_fetch(self):
        self.assertEqual(profiles_refresh.resolve("./docs/a b.svg", "o", "r", "v1", ""), "https://raw.githubusercontent.com/o/r/v1/docs/a%20b.svg")
        self.assertEqual(profiles_refresh.resolve("/x/a.svg", "o", "r", "v1", "sub"), "https://raw.githubusercontent.com/o/r/v1/x/a.svg")
        self.assertEqual(profiles_refresh.resolve("http://h.example/a.svg", "o", "r", "v1"), "https://h.example/a.svg")
        self.assertEqual(profiles_refresh.resolve("https://github.com/o/r/blob/main/a.png?raw=true", "o", "r", "v1"), "https://raw.githubusercontent.com/o/r/main/a.png")

        def no_network(url):
            raise AssertionError("fetched " + url)
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, dict(GOOD))
            with self.assertRaisesRegex(profiles_refresh.RefreshError, "main is a branch"):
                profiles_refresh.refresh("x", ref="main", profiles=tmp, get=no_network)

    def test_a_refresh_from_fetched_bytes_writes_the_same_files_every_time_and_a_profile_that_still_loads(self):
        pages = {"https://raw.githubusercontent.com/o/x/v1.0.0/README.md": self.TEXT.encode(), "https://raw.githubusercontent.com/o/x/v1.0.0/docs/logo.svg": SVG}
        written = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as tmp:
                write_profile(tmp, dict(GOOD))
                said = profiles_refresh.refresh("x", ref="v1.0.0", today="2026-10-18", profiles=tmp, get=lambda url: pages[url])
                with open(os.path.join(tmp, "x.toml"), "rb") as f, open(os.path.join(tmp, "assets", "x-mark.svg"), "rb") as g:
                    written.append((f.read(), g.read()))
                [p] = dashboard.load_profiles(tmp)
                self.assertEqual(p["readme"]["title"], "The X Tool")
                self.assertEqual(p["readme"]["ref"], "v1.0.0")
                self.assertEqual((p["mark"], p["mark_ref"], p["logo"]), ("assets/profiles/x-mark.svg", "v1.0.0", None))   # the README's first picture is a drawing: it is the mark, not a README figure
                self.assertEqual(p["quotes"], GOOD["quotes"])   # the rest of the profile is kept
                self.assertTrue(any("mark: x-mark.svg" in line for line in said))
        self.assertEqual(written[0], written[1])
        # a README whose picture cannot be stored leaves a profile with no picture keys, and a stale file is removed
        with tempfile.TemporaryDirectory() as tmp:
            write_profile(tmp, with_logo(tmp, GOOD))
            pages["https://raw.githubusercontent.com/o/x/v1.0.0/docs/logo.svg"] = b"<html>not found</html>"
            profiles_refresh.refresh("x", ref="v1.0.0", today="2026-10-18", profiles=tmp, get=lambda url: pages[url])
            self.assertNotIn("logo", parsed_at(tmp))
            self.assertEqual(os.listdir(os.path.join(tmp, "assets")), [])
            self.assertEqual(dashboard.load_profiles(tmp)[0]["logo"], None)


def parsed_at(folder):
    with open(os.path.join(folder, "x.toml"), "rb") as f:
        return tomllib.load(f)


if __name__ == "__main__":
    unittest.main()
