# SPDX-License-Identifier: Apache-2.0
"""Install step of the OpenCode arms (arms/opencode*/prepare.py call this).

OpenCode's npm package is a stub: `bin/opencode.exe` is a script that exits with "postinstall script was not run", and the compiled executable lives in a per-platform
optional dependency (`opencode-<platform>`, `@opencode/cli-<platform>`) that the package's postinstall copies over the stub. Buffon installs with `npm ci --ignore-scripts`
(buffon/arms/install.py), so nothing runs that script; this step points the arm at the platform package's executable instead, after comparing its sha256 with the one the
manifest's `prepare.py` pins. The platform package itself is pinned by integrity in the arm's package-lock.json."""
import os

from . import manifest
from .install import InstallError


def native_binary(ws, arm, package, expect):
    """Set arm.binary to the compiled executable of `package` (a name template with {platform}) for this platform; `expect` is {platform: sha256}."""
    want = expect.get(ws.platform)
    if not want:
        raise InstallError(f"{arm.id}: no pinned OpenCode executable for {ws.platform}")
    name = package.format(platform=ws.platform)
    exe = os.path.join(arm.install_dir, "node_modules", *name.split("/"), "bin", "opencode")
    if not os.path.isfile(exe):
        raise InstallError(f"{arm.id}: {name} is not installed under node_modules (npm skipped its optional dependency for {ws.platform})")
    digest = manifest.sha256_file(exe)
    if digest != want:
        raise InstallError(f"{arm.id}: the executable in {name} has sha256 {digest}, the manifest pins {want}")
    arm.binary = exe
    arm.record.update(native_package=name, native_executable_sha256=digest)
