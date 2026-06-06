# Learning Log

## Day 01 - Portfolio Foundation

Date: 2026-06-03

Today we turned the Smart OPD project into the beginning of a recruiter-facing portfolio repository.

### What Changed

- Added GitHub Actions CI for backend smoke tests and frontend production builds.
- Added backend smoke tests for the queue engine bootstrap and patient registration flow.
- Added a ten-day portfolio roadmap so the repo shows intentional progress.
- Started this learning log so the project history can be explained in interviews.

### Concepts To Understand

- CI means continuous integration. It automatically checks that important parts of the project still work after each push.
- A smoke test is a small test that verifies the system can perform a core workflow without breaking.
- Recruiters and engineers often judge projects by evidence: tests, docs, commits, structure, and the ability to explain tradeoffs.

### Interview Explanation

This project is a hospital OPD queue management system. The backend models doctors, patients, departments, token order, wait-time estimates, and notification scheduling. The first quality improvement was to add automated checks so future changes can be made with more confidence.

## Day 02 - Flask API Contract Tests

Date: 2026-06-06

Today we moved one level closer to production-style confidence by testing the Flask API through HTTP endpoints.

### What Changed

- Added API contract tests for `/api/health` and `/api/bootstrap`.
- Added an auth test proving admin routes reject anonymous requests and accept a valid admin token.
- Added an OTP-backed patient registration workflow test that sends an OTP, verifies it, registers a patient, and tracks the created record.
- Renamed the backend CI job so GitHub shows both unit and API coverage.

### Concepts To Understand

- A unit test checks a small piece of logic directly. The Day 1 queue tests are close to this style.
- An API contract test checks the behavior another client depends on: status codes, JSON fields, authentication, and workflow shape.
- Authentication tests matter because a recruiter or reviewer wants to see that protected backend routes are not public by accident.
- Test setup should isolate state. These API tests reset the in-memory queue and OTP service before every test so one test cannot secretly depend on another.

### Interview Explanation

After adding queue-engine smoke tests, I added Flask API tests to prove the backend works through real HTTP routes. The most important workflow test covers OTP verification, patient registration, and patient tracking, which is a realistic path through the Smart OPD system.
