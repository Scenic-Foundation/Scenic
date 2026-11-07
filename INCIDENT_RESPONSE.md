# Incident Response Plan

This document describes how the Scenic maintainers respond to security or integrity incidents affecting the project, its releases, or its infrastructure.

This plan is public to support transparency and community trust. Sensitive operational details, such as private contact information, credentials, and internal coordination methods, are maintained separately.

## 1. Purpose and Scope

This plan describes how Scenic maintainers will:

- identify, triage, and respond to security or integrity incidents
- communicate with reporters and the community when appropriate
- contain, remediate, and recover from incidents
- review incidents and improve project practices afterward

This plan applies to:

- the Scenic source code and GitHub repository
- official release artifacts, including PyPI distributions and GitHub releases
- project-maintained documentation and web infrastructure
- official Scenic CI/CD workflows and related repository infrastructure

This plan does not apply to unrelated third-party forks or downstream integrations maintained outside the Scenic project. It also does not cover vulnerabilities in third-party simulators or dependencies unless Scenic itself is affected, exposes the issue in practice, or can reasonably mitigate it.

## 2. Guiding Principles

- **Protect users first.** We aim to reduce risk quickly and provide clear guidance when action is needed.
- **Communicate clearly.** We try to share accurate information without disclosing sensitive details too early.
- **Keep the process practical.** Scenic is maintained by a small team, so this plan is intended to be lightweight and realistic.
- **Improve after incidents.** When something goes wrong, we review it and use what we learn to strengthen the project.

## 3. What Counts as an Incident

An incident is any event that could affect the confidentiality, integrity, or availability of Scenic, its releases, or its project-controlled infrastructure.

Examples include:

- a reported security vulnerability in Scenic
- a compromised maintainer account, token, or CI credential
- malicious code introduced through the repository, build pipeline, or dependencies
- a compromised or tampered release artifact
- unauthorized modification of project documentation or infrastructure
- exposure of sensitive project secrets

Not every bug is a security incident. However, if a report may involve security or integrity risk, we will treat it as a potential incident until we determine otherwise.

## 4. Roles and Responsibilities

Scenic is maintained by a small team, so these responsibilities may be handled by the same people during a given incident.

- **Incident Lead:** coordinates the response, tracks status, and decides next steps
- **Maintainers:** investigate the issue, assess impact, prepare fixes, and review changes
- **Infrastructure maintainer(s):** handle CI/CD, tokens, release infrastructure, and related systems when needed
- **Communications lead:** prepares public-facing updates when needed

If no separate roles are assigned, the active maintainers will handle these responsibilities collectively.

## 5. Detection and Reporting

Potential incidents may be identified through:

- private vulnerability reports submitted as described in `SECURITY.md`
- GitHub Security Advisories and private vulnerability reporting
- GitHub notifications, issues, and pull requests
- dependency or vulnerability alerts
- reports from contributors, users, or downstream projects

Security issues should be reported privately using the process described in `SECURITY.md`, not through public issues or pull requests.

## 6. Initial Triage

When we receive a report, we will:

1. acknowledge receipt within the timeframe described in `SECURITY.md`
2. review the report and request clarification if needed
3. determine whether the issue appears to be a real security or integrity risk
4. assign an Incident Lead when appropriate
5. begin private coordination if the report is credible or confirmed

For urgent issues, especially those involving active compromise or exposed credentials, maintainers may begin containment immediately before all details are fully understood.

## 7. Severity and Prioritization

We use severity levels to help prioritize response:

- **Critical:** active compromise, malicious release, exposed credentials, or a vulnerability that seriously threatens users or project integrity
- **High:** a confirmed vulnerability with serious security impact
- **Medium:** a real vulnerability with narrower scope, more limited impact, or stronger preconditions
- **Low:** low-risk issues, defense-in-depth findings, or issues with limited practical impact

Severity may be revised as more information becomes available.

## 8. Response and Containment

Depending on the incident, maintainers may take one or more of the following actions:

- revoke or rotate affected credentials, tokens, or secrets
- disable or restrict impacted CI/CD workflows or infrastructure
- pause releases until integrity is verified
- remove, replace, or yank compromised artifacts if needed
- patch vulnerable code or dependencies
- audit recent changes, releases, and build outputs
- prepare mitigation guidance for users

For critical or high-severity incidents, we will prioritize containment first, then remediation and communication.

## 9. Remediation

After initial containment, we will work to understand the issue and fix it.

This may include:

- identifying affected components and versions
- determining whether supported releases are affected
- developing and reviewing a fix
- adding tests or checks when practical to reduce the chance of recurrence
- preparing a patched release when needed

As described in `SECURITY.md`, Scenic currently provides security updates for the latest stable 3.x release. Security fixes will normally target supported releases only.

## 10. Communication and Disclosure

We will keep the reporting party informed when appropriate and when doing so does not increase risk.

For significant incidents, we may communicate through one or more of the following:

- [GitHub Security Advisories](https://github.com/Scenic-Foundation/Scenic/security/advisories)
- GitHub release notes
- the [Scenic forum](https://forum.scenic-lang.org/)
- the [Scenic website](https://scenic-lang.org/) or project documentation
- a GitHub issue, when appropriate

Public communication will usually include, as appropriate:

- what happened
- what versions or components were affected
- what users should do
- what fix or mitigation is available

We generally follow responsible disclosure practices and prefer to publish details after a fix or mitigation is available. However, we may disclose earlier if there is evidence of active exploitation, if the issue is already public, or if earlier warning is necessary to protect users.

We will not publicly identify a reporter without their permission.

## 11. Recovery

After containment and remediation, we will:

- verify that affected systems, workflows, and releases are safe to use
- resume normal release or development activity
- publish patched releases when needed
- share mitigation or upgrade guidance with users when appropriate

## 12. Post-Incident Review

After a significant incident is resolved, we will review:

- root cause
- scope and impact
- what went well in the response
- what could be improved
- whether documentation, tests, tooling, or processes should change

When appropriate, we will update this plan, `SECURITY.md`, tests, automation, or release procedures based on what we learned.

## 13. Response Targets

These are project goals, not hard service guarantees:

- **initial acknowledgement:** within **1 week**
- **status updates for active investigations:** approximately every **14 days**, when applicable
- **critical incidents:** handled on an accelerated best-effort basis

Actual timing may vary depending on maintainer availability, complexity, and risk, but we will prioritize user safety and project integrity.

## 14. Plan Maintenance

This plan will be reviewed periodically and may be updated after significant incidents or process changes.

---

The Scenic maintainers are committed to responsible handling of security issues, clear communication, and continuous improvement.
