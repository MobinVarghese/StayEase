# StayEase — Member 1

## Role

Team Leader — Architecture, Authentication & Integration

---

## 1. Purpose

Member 1 is responsible for the shared technical foundation of StayEase and for coordinating the integration of all modules.

Member 1 owns authentication, authorization, project architecture, integration, code review, and overall technical coordination.

Member 1 should understand the complete application even though other members own individual modules.

---

## 2. Required Reading

Before starting any implementation, read:

- `docs/development-guide.md`
- `docs/architecture.md`
- `docs/business-logic.md`
- `docs/domain-model.md`
- `docs/team-contribution.md`

For booking-related work, also read:

- `docs/booking-workflow.md`

---

## 3. Primary Responsibilities

Member 1 owns:

- Authentication
- User roles
- Authorization
- Shared user model decisions
- Project architecture
- Cross-module integration
- Code review
- Git workflow coordination
- CI coordination
- Deployment preparation

---

# 4. User System

The application has three roles:

- Tenant
- Owner
- Admin

The authentication system must establish the identity of the currently authenticated user.

Other modules depend on this identity.

---

## 5. Authorization

Access must be controlled at the backend level.

### Tenant

Can:

- Browse PGs.
- View available rooms and beds.
- Request bookings.
- View their own bookings.
- View their own notifications.
- Complete dummy payment for approved bookings.

Cannot:

- Manage PGs.
- Approve bookings.
- Access another user's private information.
- Access admin-only functionality.

### Owner

Can:

- Manage their own PGs.
- Manage rooms and beds belonging to their PGs.
- View booking requests for their PGs.
- Approve or reject relevant booking requests.

Cannot:

- Modify another owner's PG.
- Approve unrelated bookings.
- Access admin-only functionality.

### Admin

Can access platform administration functionality.

---

# 6. Authentication Scope

Implement the project's authentication foundation.

Expected functionality:

- Registration
- Login
- Logout
- Authentication state
- Role handling
- Protected views

Use the existing authentication capabilities provided by the project where appropriate instead of unnecessarily replacing them.

---

# 7. Authorization and Ownership

Authorization must be enforced by the backend.

For example:

Owner A owns:

Green View PG

Owner B must not be able to access a backend operation that modifies Green View PG simply by changing an ID in the URL.

Ownership must be checked through the authenticated user.

---

# 8. Architecture Responsibility

Maintain the agreed architecture:

```text
Browser
   ↓
Django
   ↓
PostgreSQL
