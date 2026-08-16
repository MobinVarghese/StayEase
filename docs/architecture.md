# StayEase — System Architecture

## 1. Overview

StayEase follows a Django-based server-rendered web architecture.

The initial frontend is implemented using Django templates rather than a separate React application.

The main technologies are:

- Django
- Django Templates
- PostgreSQL
- Docker
- Docker Compose
- uv
- Git
- GitHub
- GitHub Actions

---

## 2. High-Level Architecture

The application follows:

Browser
   |
   v
Django
   |
   v
PostgreSQL

The browser sends HTTP requests to the Django application.

Django handles:

- URL routing.
- Authentication.
- Business logic.
- Database operations.
- Template rendering.

Django retrieves or modifies data in PostgreSQL and returns HTML responses to the browser.

---

## 3. Frontend

The initial project uses Django Templates for the frontend.

This means Django renders HTML on the server.

Example:

Browser
   |
   | GET /pgs/
   v
Django View
   |
   | Query PostgreSQL
   v
PG data
   |
   | Render template
   v
HTML response
   |
   v
Browser

A separate React frontend and REST API are not part of the initial project scope.

---

## 4. Backend

Django is responsible for:

- Authentication.
- Authorization.
- PG management.
- Room management.
- Bed management.
- Search.
- Booking.
- Notifications.
- Payment workflow.
- Administrative functionality.

---

## 5. Database

PostgreSQL is the primary database.

It stores persistent business data such as:

- Users.
- PGs.
- Rooms.
- Beds.
- Bookings.
- Notifications.
- Payments.

PostgreSQL is the authoritative source of truth for the application's business data.

---

## 6. Docker

Docker provides a consistent development environment.

The local Docker Compose configuration defines services such as:

- Django.
- PostgreSQL.

Each developer runs their own local containers and local PostgreSQL database.

The actual development database data is not shared through Git.

---

## 7. Docker Compose

Docker Compose defines how the local services work together.

Conceptually:

Django container
       |
       | database connection
       v
PostgreSQL container

The Django service depends on PostgreSQL.

The project directory is mounted into the Django container during local development so that source-code changes are available inside the container.

---

## 8. PostgreSQL Persistence

The local PostgreSQL service uses a Docker volume.

The volume stores PostgreSQL database data independently from the PostgreSQL container.

Therefore, removing and recreating the PostgreSQL container does not necessarily remove the local database data as long as the volume is retained.

---

## 9. Migrations

Django migrations are used to version-control database schema changes.

When a developer changes a Django model:

models.py
    |
    | makemigrations
    v
migration file
    |
    | Git
    v
GitHub

Other developers can pull the migration and run:

python manage.py migrate

to apply the schema change to their own PostgreSQL database.

The migration files are committed to Git.

Actual database data is not committed to Git.

---

## 10. Dependency Management

uv is used for Python dependency management.

The project contains:

- pyproject.toml
- uv.lock

pyproject.toml describes project dependencies.

uv.lock records resolved dependency versions so that the project can reproduce a consistent dependency environment.

---

## 11. Git Collaboration

Each developer works on a feature branch.

Example:

main
 |
 +-- feature/authentication
 +-- feature/property-management
 +-- feature/search
 +-- feature/booking
 +-- feature/notifications

Developers:

1. Create a feature branch.
2. Implement their feature.
3. Run tests.
4. Commit changes.
5. Push the branch.
6. Create a pull request.
7. Review the changes.
8. Merge into main.

---

## 12. Continuous Integration

GitHub Actions is used for automated checks.

A pull request can trigger:

- Dependency installation.
- Code quality checks.
- Automated tests.
- Django checks.

The purpose is to detect problems before changes are merged into the main branch.

---

## 13. Production Architecture

The production deployment will separate the application layer from the persistent database layer.

Conceptually:

Users
  |
  v
Django application
  |
  v
PostgreSQL
  |
  v
Persistent database storage

Django application containers should be replaceable without losing the application's persistent business data.

PostgreSQL is responsible for persistent application state.

For production, a managed PostgreSQL service may be used rather than relying on a PostgreSQL container as the primary production database.

---

## 14. Stateful vs Stateless

PostgreSQL is stateful because it stores persistent application state.

Django application containers should be treated as largely stateless.

For example:

A Django container can be stopped and replaced.

The PostgreSQL database remains available with the same users, PGs, rooms, beds, and bookings.

The new Django container connects to the same database.

---

## 15. Architecture Goals

The architecture is designed to provide:

- Clear separation of concerns.
- Reproducible development environments.
- Version-controlled database schema.
- Collaborative Git workflow.
- Automated testing.
- Persistent business data.
- Ability to scale the Django application independently from the database.