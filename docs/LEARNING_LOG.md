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
