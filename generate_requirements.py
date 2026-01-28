import pkg_resources
import subprocess

# Get all installed distributions
installed = list(pkg_resources.working_set)

# Build a mapping: package -> set of packages that require it
required_by = {pkg.key: set() for pkg in installed}
for pkg in installed:
    for dep in pkg.requires():
        dep_name = dep.key
        if dep_name in required_by:
            required_by[dep_name].add(pkg.key)

# Keep only packages that are required by something OR that are top-level (installed explicitly)
top_level_packages = {pkg.key for pkg in pkg_resources.working_set}
clean_packages = [pkg.key for pkg in installed if required_by[pkg.key] or pkg.key in top_level_packages]

# Get versions and format for requirements.txt
lines = []
for pkg in installed:
    if pkg.key in clean_packages:
        lines.append(f"{pkg.project_name}=={pkg.version}")

# Write to requirements.txt
with open("requirements.txt", "w") as f:
    f.write("\n".join(sorted(lines)))

print("Clean requirements.txt generated with packages actually used.")
