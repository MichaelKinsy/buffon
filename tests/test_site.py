# SPDX-License-Identifier: Apache-2.0
import os
import tempfile
import unittest

from buffon import site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIGEST = "reg.example/buffon@sha256:" + "a" * 64


class CpuLists(unittest.TestCase):
    def test_parse_and_format_round_trip(self):
        self.assertEqual(site.parse_cpus("8-11,14"), [8, 9, 10, 11, 14])
        self.assertEqual(site.format_cpus([8, 9, 10, 11, 14]), "8-11,14")
        self.assertEqual(site.parse_cpus(""), [])
        self.assertEqual(site.parse_cpus([3, 1, 1]), [1, 3])

    def test_malformed_lists_are_errors(self):
        for bad in ("a", "5-3", "1-", "1,,x"):
            with self.assertRaises(site.SiteError, msg=bad):
                site.parse_cpus(bad)


class Profile(unittest.TestCase):
    def test_default_is_unpinned_local(self):
        s = site.load(None, env={})
        self.assertEqual((s.backend, s.hardware, s.local.cpus, s.local.pinning), ("local", "shared", [], "preferred"))

    def test_environment_overrides_the_file(self):
        s = site.from_dict({"local": {"cpus": "1-2"}}, env={"BUFFON_CPUS": "4-5", "BUFFON_MOCK_CPUS": "6", "BUFFON_CACHE_DIR": "/c"})
        self.assertEqual((s.local.cpus, s.local.mock_cpus, s.local.cache_dir), ([4, 5], [6], "/c"))

    def test_unknown_keys_and_sections_are_errors(self):
        with self.assertRaisesRegex(site.SiteError, "unknown key 'cpu'"):
            site.from_dict({"local": {"cpu": "1"}})
        with self.assertRaisesRegex(site.SiteError, "unknown section"):
            site.from_dict({"cluster": {}})

    def test_placeholders_are_refused(self):
        with self.assertRaisesRegex(site.SiteError, "placeholder"):
            site.from_dict({"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "<namespace>", "image": DIGEST}})

    def test_required_pinning_needs_cpus_and_cpus_must_not_overlap_the_mock(self):
        with self.assertRaisesRegex(site.SiteError, "needs `cpus`"):
            site.from_dict({"local": {"pinning": "required"}}, env={})
        with self.assertRaisesRegex(site.SiteError, "overlap on 2"):
            site.from_dict({"local": {"cpus": "1-2", "mock_cpus": "2"}}, env={})
        with self.assertRaisesRegex(site.SiteError, "contradicts"):
            site.from_dict({"local": {"cpus": "1", "pinning": "none"}}, env={})

    def test_kubernetes_needs_namespace_and_a_digest_pinned_image(self):
        base = {"site": {"backend": "kubernetes"}}
        with self.assertRaisesRegex(site.SiteError, "namespace is required"):
            site.from_dict(dict(base, kubernetes={"image": DIGEST}), env={})
        with self.assertRaisesRegex(site.SiteError, "not pinned by digest"):
            site.from_dict(dict(base, kubernetes={"namespace": "n", "image": "reg.example/buffon:latest"}), env={})
        with self.assertRaisesRegex(site.SiteError, "needs image"):
            site.from_dict(dict(base, kubernetes={"namespace": "n"}), env={})
        with self.assertRaisesRegex(site.SiteError, "base_image"):
            site.from_dict(dict(base, kubernetes={"namespace": "n", "bundle": True}), env={})
        ok = site.from_dict(dict(base, kubernetes={"namespace": "n", "image": DIGEST, "cpus": 4}), env={"BUFFON_K8S_MEMORY": "32Gi", "BUFFON_K8S_CPUS": "6"})
        self.assertEqual((ok.kube.cpus, ok.kube.memory, ok.kube.image), (6, "32Gi", DIGEST))

    def test_secret_env_names_secrets_and_never_holds_one(self):
        base = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "image": DIGEST}}
        ref = {"name": "API_KEY", "secret": "buffon-keys", "key": "api.key"}
        loaded = site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], secret_env=[ref])), env={})
        self.assertEqual(loaded.kube.secret_env, [ref])
        self.assertEqual(loaded.describe()["kubernetes"]["secret_env"], ["API_KEY"])   # run.json names the variable, not the Secret
        self.assertEqual(site.from_dict(base, env={}).kube.secret_env, [])
        bad = [
            (dict(ref, value="s3cret"), "a secret value never goes in a profile"),
            ({"name": "API_KEY", "secret": "buffon-keys"}, "needs key"),
            (dict(ref, secret=""), "needs secret"),
            (dict(ref, key=7), "needs key"),
            (dict(ref, name="1API"), "not an environment variable name"),
            (dict(ref, secret="Buffon_Keys"), "not a Kubernetes Secret name"),
            (dict(ref, key="a/b"), "not a key of a Secret"),
            (dict(ref, secret="<secret name>"), "placeholder"),
        ]
        for entry, message in bad:
            with self.assertRaisesRegex(site.SiteError, message, msg=entry):
                site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], secret_env=[entry])), env={})
        with self.assertRaisesRegex(site.SiteError, "API_KEY more than once"):
            site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], secret_env=[ref, dict(ref, secret="other")])), env={})
        with self.assertRaisesRegex(site.SiteError, "list of tables"):
            site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], secret_env=["API_KEY"])), env={})

    def test_max_cv_is_a_coefficient_of_variation(self):
        base = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "image": DIGEST}}
        default = site.from_dict(base, env={})
        self.assertEqual((default.kube.max_cv, default.describe()["kubernetes"]["max_cv"]), (0.05, 0.05))
        self.assertEqual(site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], max_cv=0.03)), env={}).kube.max_cv, 0.03)
        for bad in (0, 1, 1.5, 0.0):
            with self.assertRaisesRegex(site.SiteError, "max_cv", msg=bad):
                site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], max_cv=bad)), env={})
        with self.assertRaisesRegex(site.SiteError, "non-negative number"):
            site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], max_cv="0.03")), env={})

    def test_kubernetes_overrides_are_parsed_for_their_type(self):
        base = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "image": DIGEST}}
        env = {"BUFFON_K8S_MAX_CV": "0.03", "BUFFON_K8S_NODE_SELECTOR": '{"pool": "bench"}', "BUFFON_K8S_SECRET_ENV": '[{"name": "API_KEY", "secret": "buffon-keys", "key": "api"}]',
               "BUFFON_K8S_IMAGE_PULL_SECRETS": '["pull"]', "BUFFON_K8S_TOLERATIONS": '[{"key": "dedicated", "operator": "Exists"}]'}
        k = site.from_dict(base, env=env).kube
        self.assertEqual((k.max_cv, k.node_selector, k.secret_env[0]["name"], k.image_pull_secrets, k.tolerations[0]["key"]), (0.03, {"pool": "bench"}, "API_KEY", ["pull"], "dedicated"))
        for name, value, message in (("BUFFON_K8S_MAX_CV", "low", "BUFFON_K8S_MAX_CV"), ("BUFFON_K8S_MAX_CV", "2", "max_cv"), ("BUFFON_K8S_NODE_SELECTOR", "pool=bench", "BUFFON_K8S_NODE_SELECTOR"),
                                     ("BUFFON_K8S_NODE_SELECTOR", '["pool"]', "must be a table"), ("BUFFON_K8S_SECRET_ENV", '[{"name": "K", "secret": "s", "key": "k", "value": "x"}]', "never goes in a profile"),
                                     ("BUFFON_K8S_IMAGE_PULL_SECRETS", '"pull"', "list of strings"), ("BUFFON_K8S_CPUS", "0", "positive integer")):
            with self.assertRaisesRegex(site.SiteError, message, msg=(name, value)):
                site.from_dict(base, env={name: value})

    def test_a_placeholder_inside_a_table_is_refused(self):
        base = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "image": DIGEST}}
        for kube in ({"node_selector": {"<label key>": "bench"}}, {"node_selector": {"pool": "<label value>"}}, {"tolerations": [{"key": "<taint key>", "operator": "Exists"}]}):
            with self.assertRaisesRegex(site.SiteError, "placeholder", msg=kube):
                site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], **kube)), env={})

    def test_nodes_and_spread_choose_several_nodes(self):
        base = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "image": DIGEST}}

        def kube(**k):
            return site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], **k)), env={})

        default = kube()
        self.assertEqual((default.kube.nodes, default.kube.spread), ([], 0))
        self.assertEqual(kube(nodes=["a", "b.pool"], spread=1).describe()["kubernetes"]["nodes"], ["a", "b.pool"])
        self.assertEqual(kube(spread=4).kube.spread, 4)
        self.assertEqual(site.from_dict(base, env={"BUFFON_K8S_SPREAD": "3", "BUFFON_K8S_NODES": '["a", "b", "c"]'}).kube.spread, 3)
        for bad, message in (({"node": "a", "nodes": ["b"]}, "Set one of them"), ({"node": "a", "spread": 2}, "Set one of them"), ({"nodes": ["a", "a"]}, "more than once"),
                             ({"nodes": ["Node_A"]}, "not a node name"), ({"nodes": ["a", "b"], "spread": 3}, "more than the 2 nodes"), ({"spread": -1}, "non-negative integer")):
            with self.assertRaisesRegex(site.SiteError, message, msg=bad):
                kube(**bad)

    def test_the_node_architecture_is_amd64_or_arm64(self):
        from buffon.backend import bundle
        self.assertEqual(set(site.ARCHES), set(bundle.ARCHES))   # every architecture a site may name is one a bundle can be built for
        base = {"site": {"backend": "kubernetes"}, "kubernetes": {"namespace": "n", "bundle": True, "base_image": DIGEST}}
        default = site.from_dict(base, env={})
        self.assertEqual(default.kube.arch, "amd64")
        self.assertEqual(default.describe()["kubernetes"]["arch"], "amd64")
        self.assertEqual(site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], arch="arm64")), env={}).kube.arch, "arm64")
        self.assertEqual(site.from_dict(base, env={"BUFFON_K8S_ARCH": "arm64"}).kube.arch, "arm64")
        for bad in ("x86_64", "x64", "aarch64", "AMD64", ""):
            with self.assertRaisesRegex(site.SiteError, "arch", msg=bad):
                site.from_dict(dict(base, kubernetes=dict(base["kubernetes"], arch=bad)), env={})
        with self.assertRaisesRegex(site.SiteError, "arch"):
            site.from_dict(base, env={"BUFFON_K8S_ARCH": "riscv64"})

    def test_bad_types(self):
        for data in ({"local": {"allow_frequency_scaling": "yes"}}, {"kubernetes": {"cpus": 0}}, {"kubernetes": {"arch": 64}}, {"kubernetes": {"memory": "lots"}}, {"site": {"hardware": "fast"}}, {"site": {"backend": "ssh"}}):
            with self.assertRaises(site.SiteError, msg=data):
                site.from_dict(data, env={})

    def test_examples_load_or_fail_only_on_their_placeholders(self):
        loaded = site.load(os.path.join(ROOT, "sites", "example-local.toml"), env={})
        self.assertEqual(loaded.local.cpus, [2, 3, 4, 5])
        with self.assertRaisesRegex(site.SiteError, "placeholder"):
            site.load(os.path.join(ROOT, "sites", "example-kubernetes.toml"), env={})

    def test_the_cluster_bundle_template_names_the_kubeconfig_by_path_and_refuses_its_placeholders(self):
        path = os.path.join(ROOT, "sites", "example-cluster-bundle.toml")
        with self.assertRaisesRegex(site.SiteError, "placeholder"):
            site.load(path, env={})
        with open(path) as f:
            text = f.read()
        self.assertIn('kubeconfig = "~/.kube/<your kubeconfig file>"', text)
        self.assertNotIn("token", text.lower())
        self.assertNotIn("client-certificate", text)

    def test_the_clock_claim_is_hypervisor_or_nothing(self):
        self.assertEqual(site.from_dict({"local": {"clock_claim": "hypervisor"}}, env={}).local.clock_claim, "hypervisor")
        self.assertEqual(site.from_dict({}, env={}).local.clock_claim, "")
        with self.assertRaises(site.SiteError):
            site.from_dict({"local": {"clock_claim": "fixed"}}, env={})

    def test_the_macos_example_pins_nothing_and_names_no_cpus(self):
        loaded = site.load(os.path.join(ROOT, "sites", "example-macos.toml"), env={})
        self.assertEqual((loaded.local.pinning, loaded.local.cpus, loaded.local.mock_cpus), ("none", [], []))
        with self.assertRaisesRegex(site.SiteError, "contradicts"):
            site.from_dict({"local": {"pinning": "none", "cpus": "2-3"}}, env={})

    def test_name_resolves_under_sites_dir(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "mine.toml"), "w") as f:
                f.write('[site]\nhardware = "dedicated"\n')
            self.assertEqual(site.load("mine", base_dir=d, env={}).hardware, "dedicated")
            with self.assertRaisesRegex(site.SiteError, "not found"):
                site.load("absent", base_dir=d, env={})

    def test_the_committed_schema_matches_the_code(self):
        with open(os.path.join(ROOT, "sites", "SCHEMA.md")) as f:
            self.assertEqual(f.read(), site.schema_markdown())


if __name__ == "__main__":
    unittest.main()
