# Changelog

## Unreleased

### Added

- General cloud agent workspace with shell, file reading, file writing, and directory listing tools.
- Python, Bash, Git, Node.js, npm, and curl in the ARM64 runtime container.
- Managed AgentCore session storage and file-backed Strands conversation history, resumed using the same session ID.
- CLI support for session continuation, file listing, text-file downloads, AWS profiles, and JSON output.
- Configurable Bedrock model through `MODEL_ID` and Terraform's `model_id` variable.
- Example GitHub Actions workflows for CI, deployment, and rollback, plus an optional OIDC deployment role and remote-state configuration.

### Changed

- Reframed the template around a small, extensible cloud agent workspace and documented its execution and storage limits.
- Required AWS Terraform provider 6.46 or newer within major version 6 for managed session storage.
- Ensured runtime IAM policies are created before the runtime starts, and removed deprecated region data-source usage.
- Simplified first-deploy ECR bootstrapping and used a fresh image tag for each local build.
- Kept runtime dependencies fixed at startup and ran workspace tools sequentially.

### Removed

- Demonstration weather, calculator, and inventory tools.
- AgentCore Memory infrastructure, permissions, configuration, Python helpers, tests, and documentation.
- Incomplete VPC networking toggle; the starter uses public networking with IAM-authenticated invocation.
- Automatic tracing setup and its extra dependencies; runtime logs work without account-wide tracing configuration.
