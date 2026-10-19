from buffon.arms.prepare_opencode import native_binary

# sha256 of bin/opencode in each platform package of opencode-ai 1.19.0 (opencode-linux-x64, opencode-darwin-arm64, ...; the non-baseline x64 builds, which need AVX2).
NATIVE = {
    "linux-x64": "135ac3f86c43f2a22328a3554fec5f0bc57d71576077902661bc38dac34871fd",
    "linux-arm64": "1e392db1d558a9eebaef618d4da3927f8b61fbcbd9a19513ed77f911142415df",
    "darwin-x64": "87875bda5a6156c4cff482e3799b10e65dd3cebb890d3de33adacbbeae5ef042",
    "darwin-arm64": "476151a6c8b56e084d223d71a9312479e3b95547f8d8649b3489577059f9c5b4",
}


def prepare(ws, arm, base):
    native_binary(ws, arm, "opencode-{platform}", NATIVE)
