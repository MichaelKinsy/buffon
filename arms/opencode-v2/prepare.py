from buffon.arms.prepare_opencode import native_binary

# sha256 of bin/opencode in each platform package of @opencode/cli 2.0.29 (@opencode/cli-linux-x64, @opencode/cli-darwin-arm64, ...; the non-baseline x64 builds, which need AVX2).
NATIVE = {
    "linux-x64": "7e23471f4ebe2313d78baacc9ac96fe9e197ce26d808de4b0fcc37efbe473dad",
    "linux-arm64": "ff63ff56191f8460cae10f789a3375348e0fe108647e6f429949060c162b2ff1",
    "darwin-x64": "b16842742bfaa2d1c68ecf787226831c998946e48a7ad9d8235cb84bcfbc4fcb",
    "darwin-arm64": "7f46ba1dad86b730903d9adf54015bb4e706fc1ab6a247affc5a635cd8a663f3",
}


def prepare(ws, arm, base):
    native_binary(ws, arm, "@opencode/cli-{platform}", NATIVE)
