# Day 01 - Foundation Notes

## Goal

Make the existing Smart OPD repository look and behave more like a professional engineering project.

## Why This Matters

A strong GitHub project should answer four recruiter questions quickly:

- What problem does this project solve?
- Can the developer structure a real system?
- Can the developer test and maintain their code?
- Can the developer explain the engineering decisions?

## What To Learn Today

### 1. Repository Hygiene

Good repo hygiene means the project has a clear structure, a useful README, tests, CI, and documentation that helps another developer understand the system quickly.

### 2. Smoke Testing

Smoke tests do not test every small detail. They test whether the most important workflow still works. In this project, the first smoke tests check that demo data can load, bootstrap data can be built, and a patient can be registered with a queue token and notification plan.

### 3. CI/CD

CI catches broken code before recruiters or collaborators see it. For this project, CI runs backend tests and builds the frontend on every push to `main` and every pull request.

## Day 02 Preview

Next we will add API-level tests for the Flask backend. That will prove the application can respond correctly through real HTTP endpoints, not only internal Python methods.
