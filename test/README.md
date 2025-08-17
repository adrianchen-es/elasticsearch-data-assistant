Test fixtures policy

This repository's test fixtures may contain intentionally fake API keys, tokens,
internal IPs, and other sensitive-like strings used solely for unit/integration
tests. These are non-production values and are allowed under the CI security
scans for auditability when one of the following is true:

- `test/README.md` (this file) exists describing the policy, or
- Individual test fixture files that contain fake secrets include the token
  `placeholder` (case-insensitive) somewhere in the file.

Maintainers: when you add fixtures that include fake keys, mark them clearly by
including the token `placeholder` or update this README with the rationale.
