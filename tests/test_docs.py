# SPDX-License-Identifier: Apache-2.0
"""The documents say what the code does: links resolve, WHAT-WE-MEASURE.md names every family and matches the faithfulness weights, credits and floor, the report's
sections are the template's, and the banned words of tests/banned_words.py stay out of the pages a reader starts with."""
import glob
import os
import re
import tempfile
import tomllib
import unittest

from buffon import cli
from buffon.report import render
from buffon.runner import raw as rawlib
from buffon.agentbench import Protocol, paired_result
from tests.banned_words import BANNED, pattern
from tests.test_report import raw_of, sample, series
from buffon.faithfulness import grading, probes

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "docs", "WHAT-WE-MEASURE.md")
# HARNESS-SURVEY.md quotes other projects' READMEs word for word, links included; those links point into the other projects and are not this repository's.
QUOTING = {"HARNESS-SURVEY.md"}
DOCS = [os.path.join(ROOT, "README.md"), os.path.join(ROOT, "CONTRIBUTING.md")] + [p for p in sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))) if os.path.basename(p) not in QUOTING]
LINK = re.compile(r"\]\(([^)\s]+)\)")
CREDIT_NAMES = {"identical": grading.IDENTICAL, "equivalent-presentation": grading.PRESENTATION, "equivalent-semantics": grading.SEMANTICS, "behaviour-differs": grading.DIFFERS}


README = os.path.join(ROOT, "README.md")
METHODOLOGY = os.path.join(ROOT, "docs", "METHODOLOGY.md")
RUNNING = os.path.join(ROOT, "docs", "RUNNING.md")
CONTRIBUTING = os.path.join(ROOT, "CONTRIBUTING.md")
FIELD = os.path.join(ROOT, "docs", "FIELD.md")
TEMPLATE = os.path.join(ROOT, "docs", "REPORT-TEMPLATE.md")
LIMITATIONS = os.path.join(ROOT, "docs", "LIMITATIONS.md")
PRESENTED = [README, METHODOLOGY, RUNNING, PAGE, FIELD, LIMITATIONS]   # the pages named in BANNED['claim']
# Words that state a verdict or sell are listed in tests/banned_words.py. The documents give numbers with units and spread.
CLAIM_WORDS = pattern("claim")
# The arm names the measurement code may hold as strings: the default name of the reference arm, as a parameter default.
REFERENCE_DEFAULT = "pi-node"


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def slug(heading):
    """GitHub's anchor for a heading: lower case, punctuation dropped, spaces to hyphens."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path):
    in_fence = False
    found = set()
    for line in read(path).splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            found.add(slug(line.lstrip("#")))
    return found


class Links(unittest.TestCase):
    def test_every_relative_link_and_anchor_in_the_docs_resolves(self):
        problems = []
        for doc in DOCS:
            for target in LINK.findall(read(doc)):
                if re.match(r"[a-z]+:", target):
                    continue
                path, _, fragment = target.partition("#")
                dest = os.path.normpath(os.path.join(os.path.dirname(doc), path)) if path else doc
                if not os.path.exists(dest):
                    problems.append(f"{os.path.relpath(doc, ROOT)}: {target} does not exist")
                elif fragment and dest.endswith(".md") and fragment not in anchors(dest):
                    problems.append(f"{os.path.relpath(doc, ROOT)}: {target} has no such heading")
        self.assertEqual(problems, [])


class WhatWeMeasure(unittest.TestCase):
    def test_every_family_of_the_grade_is_on_the_page(self):
        with open(os.path.join(ROOT, "workloads", "grade.toml"), "rb") as f:
            families = [fam["id"] for fam in tomllib.load(f)["family"]]
        headings = {line.lstrip("#").strip().lower() for line in read(PAGE).splitlines() if line.startswith("#")}
        for family in families:
            words = family.replace("-", " ")
            self.assertTrue(any(words in h for h in headings), f"{family} has no heading on the page")

    def test_the_weights_table_equals_the_dimensions_of_the_code(self):
        rows = re.findall(r"^\| (F\d) \| [^|]+ \| (\d+)", read(PAGE), re.M)
        self.assertEqual({d: int(w) for d, w in rows}, {d: w for d, (_, w) in probes.DIMENSIONS.items()})

    def test_the_grade_table_equals_the_credits_of_the_code(self):
        rows = re.findall(r"^\| (identical|equivalent-presentation|equivalent-semantics|behaviour-differs) \| ([0-9.]+) \|", read(PAGE), re.M)
        self.assertEqual({CREDIT_NAMES[name]: float(credit) for name, credit in rows}, grading.CREDIT)

    def test_the_faithfulness_floor_on_the_page_is_the_floor_of_the_method(self):
        with open(os.path.join(ROOT, "workloads", "grade.toml"), "rb") as f:
            floor = tomllib.load(f)["method"]["faithfulness_floor"]
        self.assertIn(f"faithfulness floor ({floor})", read(PAGE))



def section(path, heading):
    """The text under a `## heading` up to the next `## ` heading."""
    match = re.search(r"^## " + re.escape(heading) + r"\n(.*?)(?=^## |\Z)", read(path), re.M | re.S)
    assert match, f"{os.path.relpath(path, ROOT)} has no section {heading!r}"
    return match.group(1)


class Presentation(unittest.TestCase):
    def test_no_verdict_or_marketing_word_in_the_documents_a_reader_starts_with(self):
        hits = [f"{os.path.relpath(p, ROOT)}:{n}: {m.group(0)}" for p in PRESENTED for n, line in enumerate(read(p).splitlines(), 1) for m in CLAIM_WORDS.finditer(line)]
        self.assertEqual(hits, [])

    def test_the_rerun_command_in_the_readme_and_in_running_parses(self):
        parser = cli.build_parser()
        for path in (README, RUNNING):
            commands = re.findall(r"^python3 -m buffon (rerun .+)$", read(path), re.M)
            self.assertTrue(commands, f"{os.path.basename(path)} shows no rerun command")
            for command in commands:
                args = parser.parse_args(command.replace("<cell id>", "run::overhead/print@-#cpu_ms").split())
                self.assertEqual((args.cmd, args.cell, args.site), ("rerun", "run::overhead/print@-#cpu_ms", "mine"))

    def test_the_columns_the_readme_names_are_the_columns_the_report_prints(self):
        found = re.search(r"^`(\| workload \| api \| metric \|[^`]+)`$", read(README), re.M)
        if found:
            self.assertIn(found.group(1), read(os.path.join(ROOT, "buffon", "report", "render.py")))

    def test_the_measurement_code_never_branches_on_an_arm_name(self):
        arms = [d for d in os.listdir(os.path.join(ROOT, "arms")) if os.path.isdir(os.path.join(ROOT, "arms", d))]
        self.assertGreater(len(arms), 10)
        hits = []
        for package in ("runner", "workloads", "report", "stats", "faithfulness", "mock"):
            for directory, _, files in os.walk(os.path.join(ROOT, "buffon", package)):
                for name in files:
                    if not name.endswith(".py"):
                        continue
                    path = os.path.join(directory, name)
                    for n, line in enumerate(read(path).splitlines(), 1):
                        for arm in arms:
                            if re.search(r"[\"']" + re.escape(arm) + r"[\"']", line) and not (arm == REFERENCE_DEFAULT and "reference" in line):
                                hits.append(f"{os.path.relpath(path, ROOT)}:{n}: {arm}")
        self.assertEqual(hits, [])


def observations(error_for=None, cost_unavailable_for=None):
    out = []
    for case in ("a", "b", "c"):
        for arm in ("pi", "pig"):
            out.append({"arm": arm, "case": case, "model": "m", "run": 0, "passed": case != "c" or arm == "pi", "error": "provider 529" if (arm, case) == error_for else None,
                        "tokens": 10, "cost_usd": None if arm == cost_unavailable_for else 0.01, "wall_s": 2.0})
    return out


class Field(unittest.TestCase):
    def test_field_is_not_a_family_or_a_weight_of_the_grade(self):
        with open(os.path.join(ROOT, "workloads", "grade.toml"), "rb") as f:
            grade = tomllib.load(f)
        self.assertNotIn("field", [fam["id"] for fam in grade["family"]])
        for name, weights in grade["weights"].items():
            self.assertNotIn("field", weights.get("families", weights), name)

    def test_unavailable_telemetry_is_null_and_counted_not_zero_as_the_page_says(self):
        protocol = Protocol(benchmark="field-v1", arms=["pi", "pig"], cases=["a", "b", "c"], models=["m"], runs=1)
        result = paired_result(protocol, observations(cost_unavailable_for="pig"))["results"]["pig"]
        self.assertEqual(result["unavailable"]["cost_usd"], 3)
        self.assertEqual(result["unavailable"]["tokens"], 0)
        self.assertIsNotNone(result["headline"])

    def test_an_errored_sample_blocks_its_pair_and_withholds_the_headline_as_the_page_says(self):
        protocol = Protocol(benchmark="field-v1", arms=["pi", "pig"], cases=["a", "b", "c"], models=["m"], runs=1)
        result = paired_result(protocol, observations(error_for=("pig", "b")))["results"]["pig"]
        self.assertEqual(len(result["blocked"]), 1)
        self.assertIsNone(result["headline"])



def rendered_headings(samples):
    """The `## ` headings of the report.md that `buffon report` writes for a run built from `samples`, without the PROVISIONAL tag."""
    tmp = tempfile.mkdtemp()
    run = os.path.join(tmp, "run")
    rawlib.write(raw_of(samples), run)
    with open(render.render([run], os.path.join(tmp, "out"))) as f:
        return [line[3:].split(" \u2014 ")[0] for line in f.read().splitlines() if line.startswith("## ")]


def template_sections():
    """(heading pattern, conditional) per numbered section of the template, in order. `<x>` in a heading stands for any text."""
    out = []
    for item in re.findall(r"^\d+\. (.+)$", section(TEMPLATE, "Sections of a report"), re.M):
        head = re.split(r"(?<=\*\*): |(?<=\)): ", item)[0]   # the title and its condition, up to the colon that starts the description (a title may hold a colon of its own)
        for title in re.findall(r"\*\*([^*]+)\*\*", head):
            out.append((re.sub(r"<[^>]+>", ".+", title.replace("`", "")).strip(), "*when*" in item))
    return out


class ReportTemplate(unittest.TestCase):
    def soak_reliability(self):
        extra = [sample("a", "soak/stress", 0, api=None, flat=True, undecided=False, turns=9, soak_minutes=12.0, think_ms=0)]
        return series() + extra + [sample(arm, "reliability/http-429-retry", r, signature="S", invariants_ok=True) for arm in ("pi-node", "other") for r in range(3)]

    def test_every_heading_a_real_report_prints_is_a_section_of_the_template_in_the_same_order(self):
        sections = template_sections()
        self.assertGreaterEqual(len(sections), 14)
        position = -1
        for heading in rendered_headings(self.soak_reliability()):
            matches = [i for i, (pattern, _) in enumerate(sections) if re.fullmatch(pattern, heading)]
            self.assertTrue(matches, f"the report prints '## {heading}' and the template has no such section")
            self.assertGreaterEqual(matches[0], position, f"'## {heading}' is out of order in the template")
            position = matches[0]

    def test_a_section_the_template_does_not_mark_as_conditional_is_printed_by_a_plain_report(self):
        printed = rendered_headings(series())
        for pattern, conditional in template_sections():
            if not conditional:
                self.assertTrue(any(re.fullmatch(pattern, h) for h in printed), f"'{pattern}' is not conditional in the template but a plain report does not print it")

    def test_the_template_holds_no_number(self):
        text = read(TEMPLATE)
        rows = [line for line in text.splitlines() if line.startswith("| <") or line.startswith("| workload | arm | kind")]
        self.assertGreaterEqual(len(rows), 5)
        for line in rows:
            self.assertEqual(re.findall(r"\d+", re.sub(r"\+\d+ (?:ms|s)", "", line)), [], line)

    def test_every_metric_the_template_says_is_produced_exists_in_the_code(self):
        table = section(TEMPLATE, "Memory").split("### Sample times")[0]
        names = set(re.findall(r"`((?:ready_)?(?:peak_)?(?:rss|pss|mem)_mib|peak_mem_mib)`", table))
        self.assertEqual(names, {"rss_mib", "ready_rss_mib", "peak_rss_mib", "peak_mem_mib", "pss_mib", "ready_pss_mib"})
        code = "".join(read(os.path.join(d, f)) for d, _, fs in os.walk(os.path.join(ROOT, "buffon")) for f in fs if f.endswith(".py"))
        for name in names:
            self.assertIn(f'"{name}"', code, name)

class BannedWords(unittest.TestCase):
    def test_no_comparative_that_ranks_a_harness_or_a_runtime_on_the_limitations_page(self):
        self.assertEqual([m.group(0) for m in pattern("comparative").finditer(read(LIMITATIONS))], [])

    def test_contributing_names_every_banned_word_and_the_command_that_checks_them(self):
        text = section(CONTRIBUTING, "Rules the tests check")
        for name, (_, words) in BANNED.items():
            if name == "machine":
                continue   # the generic machine words are listed there too, but a private list can add to them
            for word in words:
                self.assertIn(word, text, f"{word!r} is banned by the tests and CONTRIBUTING.md does not say so")
        self.assertIn("python3 -m unittest tests.test_docs tests.test_hygiene", text)


if __name__ == "__main__":
    unittest.main()
