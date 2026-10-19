# SPDX-License-Identifier: Apache-2.0
"""tools/boundary_profile.py reads the focused CPU from `go tool pprof -top`, not the whole-profile total that the same line also prints."""
import unittest

from tools import boundary_profile

TOP = """File: pig
Type: cpu
Duration: 25.07s, Total samples = 29.62s (118.14%)
Active filters:
   focus=coding/extension/host/subprocess\\.|extensions/sdk/json\\.
Showing nodes accounting for 16.39s, 55.33% of 29.62s total
      flat  flat%   sum%        cum   cum%
     2.85s  9.62%  9.62%      2.85s  9.62%  runtime.memmove
"""


class Accounted(unittest.TestCase):
    def test_the_focused_cpu_is_the_shown_nodes_not_the_profile_total(self):
        self.assertAlmostEqual(boundary_profile.accounted_s(TOP), 16.39)

    def test_units_and_a_missing_line(self):
        self.assertAlmostEqual(boundary_profile.accounted_s("Showing nodes accounting for 850ms, 3% of 28s total"), 0.85)
        self.assertAlmostEqual(boundary_profile.accounted_s("Showing nodes accounting for 1.5mins, 90% of 1.6mins total"), 90.0)
        self.assertEqual(boundary_profile.accounted_s("no profile"), 0.0)


class Regions(unittest.TestCase):
    def test_the_boundary_is_the_host_dispatch_and_the_sdk_package_not_pig_s_general_json(self):
        import re
        b = re.compile(boundary_profile.BOUNDARY)
        self.assertTrue(b.search("github.com/MichaelKinsy/PiG/coding/extension/host/subprocess.(*Host).dispatch"))
        self.assertTrue(b.search("github.com/MichaelKinsy/PiG/extensions/sdk.(*Extension).Run"))
        self.assertIsNone(b.search("github.com/MichaelKinsy/PiG/extensions/sdk/json.Unmarshal"))   # DecodeSessionEntry, agent messages and the RPC output call it too

    def test_a_part_is_counted_under_the_boundary_and_the_rest_of_the_json_apart(self):
        argv = boundary_profile.pprof_argv("/go/bin", "pig", "p.pprof", boundary_profile.BOUNDARY, show=boundary_profile.JSON)
        self.assertEqual(argv[argv.index("-focus") + 1], boundary_profile.BOUNDARY)
        self.assertEqual(argv[argv.index("-show") + 1], boundary_profile.JSON)
        argv = boundary_profile.pprof_argv("/go/bin", "pig", "p.pprof", boundary_profile.JSON, ignore=boundary_profile.BOUNDARY)
        self.assertEqual((argv[argv.index("-focus") + 1], argv[argv.index("-ignore") + 1]), (boundary_profile.JSON, boundary_profile.BOUNDARY))


if __name__ == "__main__":
    unittest.main()
