# Changelog

## Unreleased

### Added

- Added optional AgentCore Memory infrastructure, including memory resources, a semantic strategy, runtime environment variables, IAM permissions, and Terraform outputs.
- Added reusable Python memory helpers for storing durable memory events, writing directly queryable semantic records, retrieving similar records, and using content-hashed idempotency tokens.
- Added a short memory wiki covering when to use memory, why it helps, what to store, and how to verify it.
- Added example GitHub Actions workflows for pull request CI, main-branch runtime deployment, and manual rollback to a previous ECR image tag. These live outside `.github/workflows` so CI/CD is not enabled in the template repository by default.
- Added optional Terraform support for a GitHub Actions OIDC deploy role, including reuse of an existing account-level GitHub OIDC provider.
- Documented memory usage, optional CI/CD setup, rollback flow, and optional remote Terraform state configuration.

### Changed

- Expanded the blueprint architecture and project structure docs to include memory and CI/CD components.
