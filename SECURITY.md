# Security Policy

## Reporting a vulnerability

Report suspected vulnerabilities privately to **founder@kazenai.com**.

Do **not** open a public GitHub issue for unreleased security details, credentials,
or customer data.

Please include:

- affected repository and version/tag when known;
- a minimal reproduction without secrets or customer content;
- impact assessment if you have one.

You should receive an acknowledgement within a few business days.

## Scope

This repository contains hermetic and optional hosted demos for KazenAI Control.
It is not a production service. Hosted FinOps/Lens environments are separate
products with separate terms.

## Capture defaults

Demo paths that use the SDK inherit metadata-default capture: request/response
bodies are omitted unless an example explicitly documents otherwise. Never commit
API keys, session cookies, or real tenant identifiers.
