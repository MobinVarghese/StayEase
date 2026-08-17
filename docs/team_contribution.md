# StayEase — Team Contribution and Collaboration

## 1. Team Structure

The project is developed by a team of five members.

The work is divided by functional responsibility while maintaining a shared understanding of the overall system.

---

## 2. Member 1 — Team Leader / Architecture / Authentication

### Responsibilities

- Overall project architecture.
- Django project structure.
- Authentication and authorization.
- User roles.
- Integration between modules.
- Code review.
- Git workflow coordination.
- CI/CD coordination.
- Final integration and deployment preparation.

### Main areas

- User model.
- Authentication.
- Tenant/Owner access control.
- Shared application architecture.

---

## 3. Member 2 — PG and Property Management

### Responsibilities

- PG management.
- Room management.
- Bed management.
- Owner dashboard related to properties.
- PG creation and editing.
- Room and bed availability management.

### Main areas

Owner
  ↓
PG
  ↓
Room
  ↓
Bed

---

## 4. Member 3 — Search and PG Discovery

### Responsibilities

- PG listing page.
- Search functionality.
- Filtering.
- PG details page.
- Room and availability display.
- Tenant-facing discovery interface.

### Main areas

Tenant
  ↓
Search
  ↓
PG listing
  ↓
PG details
  ↓
Room and bed availability

---

## 5. Member 4 — Booking Management

### Responsibilities

- Booking model.
- Booking request workflow.
- Booking status management.
- Owner approval/rejection.
- Tenant booking history.
- Owner booking management.
- Availability validation.
- Prevention of conflicting bookings.
- Booking-related tests.

### Main areas

Tenant
  ↓
Booking Request
  ↓
PENDING
  ↓
APPROVED / REJECTED
  ↓
CONFIRMED

---

## 6. Member 5 — Notifications / Payment / Administration

### Responsibilities

### Notifications

- Owner booking notifications.
- Tenant booking notifications.
- Read/unread notification state.

### Payment

- Dummy payment workflow.
- Payment status.
- Booking confirmation after successful payment.

### Administration

- Admin management interfaces.
- User and platform monitoring.

---

## 7. Collaboration Workflow

The team uses Git and GitHub for collaborative development.

The main branch contains integrated project code.

Each developer works on a feature branch.

Example:

main
 |
 +-- feature/authentication
 +-- feature/property-management
 +-- feature/search
 +-- feature/booking
 +-- feature/notifications

---

## 8. Pull Request Workflow

The development workflow is:

Create feature branch
        ↓
Implement feature
        ↓
Run tests
        ↓
Commit changes
        ↓
Push branch
        ↓
Create Pull Request
        ↓
Code review
        ↓
CI checks
        ↓
Merge into main

---

## 9. Shared Database Schema

The developers do not use one shared PostgreSQL database during normal development.

Each developer has their own local PostgreSQL database.

However, all developers use the same database schema through Django migrations.

Migration files are committed to Git.

When a developer pulls new migration files, the migrations are applied to their local PostgreSQL database.

Therefore:

Same code
+
Same migrations
+
Same database structure

while actual development data can differ between developers.

---

## 10. Working with Dependencies

Some modules depend on other modules.

For example:

Booking depends on:

- User.
- PG.
- Room.
- Bed.

Notifications depend on:

- User.
- Booking.

Payment depends on:

- Booking.

To support parallel development, the team first agrees on the domain models and their interfaces.

Developers can then work independently using test factories and development data.

Core model changes are communicated to the team and integrated early.

---

## 11. Testing

Each feature should include appropriate tests.

Examples:

Authentication:
- Login works.
- Unauthorized users cannot access protected pages.

Property management:
- Owner can create a PG.
- Owner can add rooms and beds.
- Owner cannot modify another owner's PG.

Booking:
- Tenant can request an available bed.
- Owner can approve/reject a request.
- An unavailable bed cannot be booked.
- Concurrent requests cannot create conflicting confirmed bookings.

Notifications:
- Owner receives booking notification.
- Tenant receives approval/rejection notification.

---

## 12. Team Communication

The team communicates model changes, dependencies, and integration issues before making changes that affect shared functionality.

The team performs regular integration and testing rather than waiting until the end of development.

---

## 13. Development Principle

The team follows an incremental development approach.

Features are developed, tested, reviewed, and integrated in small increments rather than keeping large changes isolated for a long period.