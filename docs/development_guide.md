# StayEase Development Guide

You don't want an agent to spend 30 minutes trying to fix Docker/PostgreSQL on a teammate's laptop when its actual job is to implement the feature. The agent should distinguish between **code correctness** and **environment availability**.


## Add this to the AI Agent Master Prompt

````markdown
# Development Priority — Code First, Environment Second

Your primary responsibility is to DEVELOP CORRECT CODE.

Do not allow local infrastructure problems to unnecessarily block implementation.

Before development, inspect the available environment:

~~~bash
docker info
docker compose version
uv --version
~~~

Use the available environment when it is convenient, but do not spend significant time troubleshooting the developer's machine.

---

## If Docker Is Available

Use the project's Docker Compose environment when useful:

```bash
docker compose up -d
```

You may run the Django application, PostgreSQL, Redis, and relevant tests through Docker.

However, Docker availability must never change the architectural design of the implementation.

---

## If Docker Is NOT Available

Do NOT stop development.

Do NOT spend time attempting to:

* Install Docker
* Repair Docker
* Configure Docker
* Troubleshoot Docker Engine
* Troubleshoot Docker Desktop
* Configure PostgreSQL manually
* Configure Redis manually
* Replace PostgreSQL with SQLite
* Modify project configuration just to make the local machine work

Instead:

**Continue implementing the assigned feature.**

Focus on:

* Understanding the existing architecture
* Writing the required models
* Writing views
* Writing services
* Writing forms
* Writing serializers
* Writing templates
* Writing validation
* Writing business logic
* Writing tests
* Reviewing existing code
* Maintaining clean interfaces
* Maintaining ownership boundaries
* Updating documentation when necessary

---

# Code Development Has Priority

The inability to run the application locally is an ENVIRONMENT LIMITATION, not automatically a CODE LIMITATION.

For example:

```text
Docker unavailable
      ↓
PostgreSQL unavailable
      ↓
Cannot run integration tests
      ↓
BUT
      ↓
Can still implement the feature
      ↓
Can still inspect existing code
      ↓
Can still write tests
      ↓
Can still perform static reasoning/review
```

Do not confuse:

```text
"Cannot execute this code locally"
```

with:

```text
"This code cannot be implemented."
```

---

# Do Not Fake Successful Testing

If infrastructure is unavailable, NEVER claim that a test passed when it could not actually be executed.

Instead clearly state:

```text
Implementation completed.

Local integration testing could not be executed because
Docker/PostgreSQL was unavailable.

The implementation was verified through code inspection,
available tests/static checks, and consistency with the
project architecture.
```

Be precise about what was and was not verified.

---

# Avoid Environment Debugging Loops

If a command fails because of infrastructure, classify the failure.

### Code failure

Example:

```text
ImportError caused by incorrect project code.
```

Investigate and fix it.

### Dependency/configuration failure

Example:

```text
The project dependency is missing from the configured environment.
```

Determine whether the repository configuration is wrong.

### Infrastructure failure

Example:

```text
Docker Engine is not running.
PostgreSQL container cannot start.
Redis is unavailable.
```

Do NOT turn this into the primary task.

Record the limitation and continue development.

---

# Time-Bounded Environment Troubleshooting

Only perform minimal environment troubleshooting required to determine whether the failure is caused by the code.

Do not repeatedly retry the same infrastructure command.

For example:

```bash
docker info
```

If Docker is unavailable, recognize the limitation and continue.

Do not spend the development session attempting to repair Docker unless the user explicitly asks you to troubleshoot Docker.

---

# Implementation Must Remain Production-Correct

Even when infrastructure is unavailable, write code against the REAL project architecture.

For example, if StayEase uses PostgreSQL:

Use the actual PostgreSQL-compatible Django models and queries.

Do NOT write:

```text
SQLite-specific workaround
```

merely because PostgreSQL cannot currently be reached.



The implementation must target the project's intended production architecture.

---

# Testing Strategy When Infrastructure Is Unavailable

Separate tests into:

## Tests that can run without infrastructure

Run these where possible:

* Pure Python unit tests
* Validation tests
* Utility tests
* Business-logic tests that don't require the database
* Static checks
* Formatting
* Linting
* Type checking

## Tests requiring infrastructure

Identify these clearly:

* Database integration tests
* PostgreSQL-specific behavior
* Full Django integration tests
* End-to-end tests

If infrastructure is unavailable, do not waste time trying to force these tests to run.

Mark them as:

```text
NOT RUN — PostgreSQL/Docker unavailable
```

They can be executed later when the developer has the proper environment.

---

# Definition of Done

A feature is considered implementation-complete when:

1. The code has been correctly implemented.
2. The architecture is respected.
3. Ownership boundaries are respected.
4. Relevant tests have been written.
5. Available tests/checks have been executed.
6. Infrastructure-dependent tests are identified when unavailable.
7. No environment workaround has compromised the intended architecture.
8. The working tree contains only intended changes.

Infrastructure availability affects the TESTING STATUS.

It does NOT automatically determine whether the CODE can be implemented.

---

# Most Important Rule

**Do not let infrastructure troubleshooting derail feature development.**

Your priority order is:

1. Understand the codebase.
2. Understand the assigned task.
3. Design the solution.
4. Implement the code.
5. Write tests.
6. Run whatever verification is available.
7. Identify unavailable verification caused by infrastructure.
8. Report the limitation clearly.

Do not reverse this order by spending most of the session trying to make the developer's laptop environment work.

````

### The core philosophy you want the agents to follow

Think of it as:

```text
             TASK
              │
              ▼
       Understand code
              │
              ▼
       Design solution
              │
              ▼
        Write code
              │
              ▼
        Write tests
              │
              ▼
      ┌───────┴────────┐
      │                │
 Infrastructure     Available
 unavailable       infrastructure
      │                │
      ▼                ▼
Continue coding     Run tests
      │                │
      └───────┬────────┘
              ▼
       Report honestly
````

The critical rule is **"infrastructure unavailable ≠ development unavailable."**

For your five-agent StayEase setup, this is especially useful because an agent working on, say, the **search UI/service layer** shouldn't become blocked because PostgreSQL isn't running. It should build the feature correctly against the existing models/contracts and leave the database integration test for when the environment is available.

## 1. Purpose

This document defines the common development rules for the StayEase project.

Every team member and every coding agent working on StayEase must follow these guidelines.

Before implementing any feature, read:

1. `docs/development_guide.md`
2. `docs/team_contribution.md`
3. The relevant domain documentation:
   - `docs/business_logic.md`
   - `docs/domain_model.md`
   - `docs/booking_workflow.md`
   - `docs/architecture.md`

The member-specific document defines the responsibility and boundaries of that member's work.

---

---


## Development Environment Detection

Before implementing anything, inspect the available development environment.

Run:

docker info
docker compose version
uv --version
python --version

If Docker Engine and Docker Compose are available, prefer Docker-First development. Run Django, PostgreSQL using the project's Docker Compose configuration.

If Docker is unavailable but uv is available, use the local Python environment for Django where possible. Do not replace PostgreSQL with alternative technologies merely because infrastructure is unavailable.

Always use the repository's pyproject.toml, uv.lock, Dockerfile, compose.yaml, and development_guide.md as the source of truth.

Never modify dependency or database architecture solely to accommodate a developer's local environment.

## 2. Project Overview

StayEase is a web-based PG accommodation discovery and booking platform.

The system connects:

- Tenants
- PG Owners
- Administrators

The main workflow is:

Tenant
  ↓
Search PG
  ↓
View room and bed availability
  ↓
Request booking
  ↓
Owner reviews request
  ↓
Approve / Reject
  ↓
If approved → Dummy Payment
  ↓
Booking Confirmed

---

## 3. Technology Stack

The current project uses:

- Python
- Django
- Django Templates
- PostgreSQL
- Docker
- Docker Compose
- uv
- Git
- GitHub
- GitHub Actions

The frontend is initially implemented using Django server-rendered templates.

A separate React frontend is NOT part of the current project scope.

Do not introduce React or a separate REST API unless the team explicitly decides to change the architecture.

---

## 4. Architecture

The current architecture is:

Browser
   ↓
Django
   ↓
PostgreSQL

Django is responsible for:

- HTTP request handling
- URL routing
- Authentication
- Authorization
- Business logic
- Database access
- Template rendering

PostgreSQL is the primary source of truth for persistent business data.

---

# 5. Core Domain

The main entities are:

- User
- PG
- Room
- Bed
- Booking
- Notification
- Payment

The primary relationship hierarchy is:

Owner
  ↓
PG
  ↓
Room
  ↓
Bed

Booking connects:

Tenant
  ↓
Booking
  ↓
Bed

Notifications and payments are associated with booking-related events.

Do not create alternative relationships without checking the domain documentation first.

---

# 6. Business Rules

The following rules must be preserved.

## Users

Users have roles:

- Tenant
- Owner
- Admin

Users should only have access to functionality allowed by their role.

---

## PG Ownership

A PG belongs to an owner.

An owner can manage their own PGs.

An owner must not be able to modify another owner's PG.

---

## Room Ownership

A room belongs to a PG.

A room cannot exist independently of its PG.

---

## Bed Ownership

A bed belongs to a room.

The bed is the primary bookable unit.

---

## Booking

A booking belongs to:

- A tenant
- A bed

A tenant requests an available bed.

A booking initially enters:

`PENDING`

The owner can:

`PENDING → APPROVED`

or:

`PENDING → REJECTED`

After approval:

`APPROVED → PAYMENT PENDING`

After successful dummy payment:

`PAYMENT PENDING → CONFIRMED`

---

## Double Booking

A bed must not have conflicting active bookings.

Concurrent booking requests must be handled safely.

Do not rely only on frontend availability checks.

The backend and database must enforce the necessary rules.

---

## Payment

Payment is currently a dummy payment workflow.

No real money is processed.

Payment is only available after booking approval.

Successful payment results in booking confirmation.

---
# StayEase Development Environment

## Development Philosophy

StayEase uses:

- `uv` for Python dependency and virtual environment management.
- Docker Compose for infrastructure services.
- PostgreSQL as the development and production database.
- Django migrations for database schema synchronization.

Docker is the preferred way to run PostgreSQL and django server.

Docker is not required for every development task. If Docker is unavailable, developers may continue working on application code, tests that do not require infrastructure, templates, services, validation, and other isolated functionality.

Developers must NOT replace PostgreSQL with SQLite merely because Docker is unavailable.

---

# 1. Prerequisites

Every developer should have:

- Git
- Python
- uv

Recommended:

- Docker Engine / Docker Desktop
- Docker Compose

Verify:

```bash
git --version
python --version
uv --version
docker --version
docker compose version
# 7. Database Rules

PostgreSQL is the primary application database.

Do not store persistent business data in:

- Python variables
- application memory
- local JSON files
- frontend state
- Docker container filesystem

Persistent business data belongs in PostgreSQL.

---

# 8. Django Models and Migrations
Never assume Docker is available. Never assume packages are globally installed. Use the project's pyproject.toml and uv environment. Never modify dependency versions merely to fix a local environment problem. If a required infrastructure service is unavailable, report the missing service and use the documented development configuration rather than inventing a replacement.

When changing Django models:

1. Modify the model.
2. Run `makemigrations`.
3. Review the generated migration.
4. Test the migration.
5. Commit the migration file.

Example:

~~~bash
python manage.py makemigrations
~~~

For detailed migration rules, conflict resolution, shared enums, and
cross-boundary schema change process, see:

**[docs/migration_rules.md](migration_rules.md)**

This document is mandatory reading before creating or modifying any migration.