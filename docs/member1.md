StayEase — Member 1 Development Specification

Role

You are Member 1 — Architecture, Authentication & Integration Owner.

Your responsibility is to build and protect the application's shared foundation. You are not the owner of every feature; your job is to make sure all feature modules can be developed independently while following consistent architecture, authentication, authorization, data contracts, error handling, testing, and integration rules.

Primary Ownership

You own:

Project architecture and shared conventions

User authentication

User roles and authorization foundation

Shared application configuration

Common utilities/services where genuinely cross-cutting

Integration contracts between members

Cross-module integration

Repository-level development standards

CI/test integration support

Final architectural consistency

Project Context

StayEase is a PG/room/bed discovery and booking platform.

Primary roles:

Tenant

Owner

Admin

Accommodation hierarchy:

Owner
  └── PG
       └── Room
            └── Bed

Booking lifecycle:

PENDING
   ├──> REJECTED
   └──> APPROVED
          └──> PAYMENT_PENDING
                  └──> CONFIRMED

The project is a Django application using PostgreSQL, Docker, uv and GitHub/CI.

Dependencies

You depend on:

Project requirements and agreed architecture.

Other members depend on you for:

User identity

Role checks

Authentication

Shared conventions

Stable interfaces

Integration rules

Member 2 depends on your authentication/authorization foundation for owner access.

Member 3 depends on tenant identity and shared project conventions.

Member 4 depends on authenticated tenant/owner identity and authorization.

Member 5 depends on authentication, authorization and the booking contracts.

Exact Responsibilities

1. Establish application architecture

Define:

Django app/module boundaries

Naming conventions

Model ownership

Service-layer conventions

URL conventions

Template conventions

Test conventions

Configuration conventions

Environment-variable handling

Do not create a monolithic app simply because integration is easier.

Each domain should have a clear owner.

2. Authentication

Implement:

Registration

Login

Logout

Password handling using Django's secure authentication mechanisms

Session management

Authentication-required routes

Appropriate redirect behavior

Basic account/profile identity required by the rest of the system

Never store plaintext passwords.

Do not create a second authentication system inside another member's module.

3. Role-based authorization

The system must distinguish:

TENANT
OWNER
ADMIN

Authorization must be enforced server-side.

A tenant must not access owner management endpoints.

An owner must not manage another owner's PG.

A normal user must not access admin functionality.

Do not rely on hiding buttons in HTML as authorization.

4. Shared ownership rules

Provide a consistent way for domain modules to answer questions such as:

Is the current user authenticated?
Is the current user an owner?
Does this PG belong to this owner?
Is this user an admin?

Prefer reusable decorators, mixins, permissions or service-level checks rather than duplicating slightly different logic across modules.

5. Shared error-handling conventions

Establish consistent behavior for:

Unauthorized access

Forbidden access

Missing resources

Invalid form data

Invalid state transitions

Do not allow different modules to invent incompatible response behavior.

6. Integration ownership

You are responsible for integrating the team's branches/features.

Integration does not mean rewriting another member's domain logic without discussion.

Before merging:

Run tests

Check migrations

Check URL collisions

Check template collisions

Check model dependencies

Check authorization

Check imports

Check environment configuration

7. Documentation

Maintain or update:

Architecture documentation

Domain ownership

Shared conventions

Integration notes

Setup instructions where needed

Scope Boundaries

You MAY modify

Project configuration

Authentication module

Shared user/role foundation

Shared utilities

Shared templates/layouts

Root URL configuration

CI configuration where necessary

Documentation

Integration wiring

You SHOULD NOT own

PG CRUD

Room CRUD

Bed CRUD

Search/filter implementation

Booking business logic

Booking concurrency logic

Dummy payment implementation

Notification business logic

Admin-specific domain workflows

Those belong to other members.

Required Engineering Principles

Single source of truth

Do not duplicate user roles or booking state definitions.

Server-side security

Every sensitive operation must be authorized on the server.

Explicit boundaries

A module should expose a clear interface rather than allowing other modules to reach into its internals.

Small commits

Prefer focused commits such as:

feat(auth): add owner registration
fix(auth): prevent unauthorized owner dashboard access
test(auth): cover role authorization

Avoid giant commits containing unrelated changes.

Testing Requirements

You must provide tests for:

Registration

Login

Logout

Invalid credentials

Authentication-required routes

Tenant authorization

Owner authorization

Admin authorization

Cross-owner access prevention

Unauthorized access

Role assignment rules

Also verify that the authentication foundation does not break other modules.

Integration Checklist

Before declaring your work complete:

Authentication works

Roles are represented consistently

Server-side authorization exists

Cross-owner access is prevented

Shared conventions are documented

Tests pass

No plaintext passwords exist

Environment secrets are not committed

Root URLs are coherent

Other members can integrate without duplicating authentication

CI passes

Agent Instructions

If an AI coding agent is assigned this document:

Read the repository before modifying it.

Identify existing Django apps and conventions.

Do not replace existing working architecture unnecessarily.

Search before creating duplicate utilities/models.

Respect ownership boundaries.

Do not implement another member's feature merely because it is convenient.

Write tests with the feature.

Keep migrations deterministic.

Never commit secrets.

Explain architectural changes in the PR.

If another member's code is required, define the dependency rather than silently taking ownership.

Definition of Done

Member 1 is complete when the team has a stable authentication and authorization foundation, documented architecture, consistent cross-module conventions, passing tests, and a clean integration path for Members 2–5.
