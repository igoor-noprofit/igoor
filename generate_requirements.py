import re

import pkg_resources

# A "plain pin" is an auto-refreshable "package==version" line. Everything
# else (environment markers like "; sys_platform == 'win32'", comments,
# ranged pins like ">=...") carries hand-maintained multi-platform
# information and must survive regeneration verbatim.
PLAIN_PIN = re.compile(r"^[A-Za-z0-9_.\-]+==[A-Za-z0-9.!+]+$")
NAME_RE = re.compile(r"^\s*([A-Za-z0-9_.\-]+)")


def _package_name(line):
    match = NAME_RE.match(line)
    return match.group(1).lower().replace("_", "-") if match else None


preserved = []
pinned_names = set()
try:
    with open("requirements.txt", "r", encoding="utf-8") as f:
        for line in f.read().splitlines():
            stripped = line.strip()
            if not stripped or PLAIN_PIN.match(stripped):
                continue
            preserved.append(stripped)
            name = _package_name(stripped)
            if name:
                pinned_names.add(name)
except FileNotFoundError:
    pass

installed = list(pkg_resources.working_set)

lines = [
    f"{pkg.project_name}=={pkg.version}"
    for pkg in installed
    if _package_name(pkg.project_name) not in pinned_names
]
lines.extend(preserved)

with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(sorted(lines)) + "\n")

print(
    f"requirements.txt regenerated: {len(lines) - len(preserved)} refreshed pins, "
    f"{len(preserved)} hand-edited lines preserved verbatim."
)
