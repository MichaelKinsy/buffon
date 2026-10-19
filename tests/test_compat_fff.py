# SPDX-License-Identifier: Apache-2.0
"""tools/compat_fff.py: the comparison names a difference, ignores the census, and the scripted model calls each registered search tool once."""
import unittest

from tools import compat_fff


class Request:
    def __init__(self, tools, k):
        self.tools, self._k = tools, k

    def rounds(self):
        return self._k


class Compare(unittest.TestCase):
    def test_a_different_field_is_named(self):
        d = compat_fff.diff({"results": [{"result": "a"}], "census": {"children": 0}}, {"results": [{"result": "b"}], "census": {"children": 1}})
        self.assertEqual(len(d), 1)
        self.assertTrue(d[0].startswith(".results[0].result:"))

    def test_the_census_is_not_compared(self):
        self.assertEqual(compat_fff.diff({"census": {"children": 0}, "x": 1}, {"census": {"children": 11}, "x": 1}), [])

    def test_ids_and_timings_are_scrubbed(self):
        self.assertEqual(compat_fff.scrub({"toolCallId": "c1", "result": {"timestamp": 5, "text": "t"}}), {"result": {"text": "t"}})


class Script(unittest.TestCase):
    def test_every_registered_tool_is_called_once_in_order(self):
        policy = compat_fff.policy_for(compat_fff.FFF_TOOLS)
        tools = ["read", "fffind", "ffgrep", "fff-multi-grep"]
        calls = [policy(Request(tools, k)) for k in range(4)]
        self.assertEqual([c.tool_calls[0][0] for c in calls[:3]], ["ffgrep", "fffind", "fff-multi-grep"])
        self.assertEqual(calls[2].tool_calls[0][1], {"patterns": ["needle", "haystack"]})
        self.assertEqual(calls[3].text, "done")


if __name__ == "__main__":
    unittest.main()
