# Fix Python 3.11 References in NumPy Builds

## Problem Summary
The pull request aims to fix CI failures where NumPy builds fail with Python 3.11, since NumPy 2.5.2 requires Python >= 3.12. The current changes already removed Python 3.11 from the NumPy matrix and fixed the mirror action script path, but builds may still be failing. The goal is to ensure that all references to Python 3.11 are removed and NumPy builds work correctly with Python 3.12+.

## Approach
1. Search for all Python version references, specifically 3.11, in build configurations
2. Ensure Python >= 3.12 is specified for NumPy builds
3. Fix any remaining BuildBackendException or build failures
4. Verify builds work correctly with updated configuration

## Steps
1. **Search for Python 3.11 references in build configurations**
   - Read `.github/workflows` and CI configuration files
   - Search for patterns matching `3.11`, `python.*3`, or Python version strings
   - Use grep/search to identify old references
   - Expected: No Python 3.11 references found

2. **Verify NumPy backend configuration**
   - Check that `meson-python` backend requires Python >= 3.12
   - Ensure NumPy-related build matrix uses Python 3.12+
   - Use `diagnostics` to test NumPy build with Python 3.12

3. **Fix remaining Python 3.11 references**
   - If any 3.11 references found, remove them
   - Update version-specific logic to enforce Python >= 3.12
   - Ensure all targets use correct Python versions

4. **Test build success**
   - Run NumPy build check (python 3.12) on debian-armv7l
   - Verify no BuildBackendException occurs
   - Confirm all CI checks pass

## Testing
- Python 3.11 is not referenced anywhere in build configs
- NumPy builds work with Python 3.12+ (no BuildBackendException)
- Build checks pass for debian-armv7l target

## Risks/Unknowns
- Build configurations may not be uniform across all CI files
- Some targets may still have hardcoded Python 3.11 (need thorough check)
- `meson-python` backend may have additional Python version constraints
- Build failures may be environment-specific (only visible in CI)
- CI environment may still reference Python 3.11 in container images or tools

## Files to modify
- `.github/workflows/...` (CI configuration files)
- Any `*.txt` or `*.cfg` that defines Python versions for NumPy builds
- Any `meson-python` or `meson` configuration files

## Expected Outcomes
- Python 3.11 completely removed from NumPy build matrices
- NumPy builds work correctly with Python 3.12+
- Build checks pass without BuildBackendException errors