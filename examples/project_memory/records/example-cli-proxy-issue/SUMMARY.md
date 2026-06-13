# Issue Summary: Example CLI Proxy Issue

## Type

issue

## Status

resolved

## Problem

A fictional CLI tool sometimes failed to connect because it did not inherit proxy environment variables.

## Context

This example demonstrates how to record solved troubleshooting work without exposing private device names, accounts, or real network details.

## Symptoms

- CLI command reported a connection error.
- Browser access still worked.
- Terminal and editor-integrated terminal behaved differently.

## Root cause

The editor-integrated terminal did not inherit the same proxy environment variables as the standalone terminal.

## Resolution

Set the required proxy variables in the shell startup file or editor terminal environment configuration.

## Verification

The CLI command succeeded from both the standalone terminal and editor-integrated terminal.

## Do not repeat

- Do not assume browser connectivity proves CLI connectivity.
- Do not hard-code private proxy addresses in public documentation.
- Do not store tokens or service credentials in issue records.

## Related records

- None

## Last reviewed

2026-01-01
