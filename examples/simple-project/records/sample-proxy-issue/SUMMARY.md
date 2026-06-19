# Issue Summary: Sample Proxy Issue

## Type

issue

## Status

resolved

## Problem

A fictional local agent could not reach a local service because proxy routing captured traffic that should have stayed local.

## Context

This record demonstrates how to preserve a solved troubleshooting path without storing real hosts, IP addresses, credentials, or private network details.

## Symptoms

- Local service URL timed out from the agent.
- Browser access worked intermittently.
- Repeated restarts did not fix the issue.

## Root cause

The proxy configuration routed local service traffic through the wrong interface. The confirmed root cause is fictional and generic.

## Resolution

Add a local bypass rule for the service range or hostname, then restart the proxy process and retest the service from the agent.

## Verification

- Local service health endpoint returned success.
- Agent command-line check reached the service without proxy errors.
- Re-running the old failing request succeeded.

## Do not repeat

- Do not reinstall the agent before checking proxy routing.
- Do not delete the project workspace because a network request failed.
- Do not store real IP addresses, account names, tokens, or private service URLs in public issue records.

## Related records

- `records/sample-web-dashboard/SUMMARY.md`

## Last reviewed

2026-01-01
