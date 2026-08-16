# StayEase Development Guide

## 1. Purpose

This document defines the common development rules for the StayEase project.

Every team member and every coding agent working on StayEase must follow these guidelines.

Before implementing any feature, read:

1. `docs/development_guide.md`
2. The appropriate `docs/memberX.md`
3. The relevant domain documentation:
   - `docs/business_logic.md`
   - `docs/domain_model.md`
   - `docs/booking_workflow.md`
   - `docs/architecture.md`

The member-specific document defines the responsibility and boundaries of that member's work.

---

# 2. Project Overview

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

# 3. Technology Stack

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

# 4. Architecture

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

When changing Django models:

1. Modify the model.
2. Run `makemigrations`.
3. Review the generated migration.
4. Test the migration.
5. Commit the migration file.

Example:

```bash
python manage.py makemigrations