# Day 02 - Flask API Contract Tests

## Goal

Prove that the backend works through real HTTP endpoints, not only through internal Python classes.

## What Was Added

- API tests for health and bootstrap endpoints.
- Authentication coverage for protected admin routes.
- End-to-end patient flow coverage for OTP send, OTP verify, patient registration, and patient tracking.
- CI wording that better reflects the expanded backend test suite.

## Why This Matters

Backend recruiters look for evidence that you understand more than happy-path coding. API tests show that you can verify the contract used by a frontend, mobile app, or external integration.

## Key Testing Ideas

### Status Codes

Status codes are part of the API contract. For example, anonymous access to an admin endpoint should return `401`, while a valid admin token should return `200`.

### JSON Shape

Frontend code depends on response keys such as `summary`, `patients`, `doctors`, and `analytics`. Tests protect those keys from accidental breaking changes.

### Stateful Workflows

The patient registration test checks a real sequence:

1. Send an OTP.
2. Verify the OTP.
3. Register the patient.
4. Track the patient using the created ID.

This kind of test gives stronger confidence than testing each endpoint in isolation.

## Day 03 Preview

Next we will test queue edge cases: emergency priority, no-show handling, doctor delays, and consultation completion. That will show algorithmic thinking inside the domain logic.
