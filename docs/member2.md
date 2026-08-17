# StayEase — Member 2

## Role

PG / Property Management — PG, Room & Bed Management

---

# 1. Purpose

Member 2 is responsible for the complete property-management domain of StayEase.

This module allows PG owners to create and manage the accommodation properties they list on StayEase.

The property hierarchy is:

Owner
  ↓
PG
  ↓
Room
  ↓
Bed

The Bed is the lowest-level accommodation unit and is the unit that tenants ultimately request for booking.

Member 2 is responsible for making this hierarchy available to the rest of the application through properly designed Django models, views, forms, templates, validation, authorization, and tests.

---

# 2. Required Documentation

Before making any code changes, read:

1. `docs/development-guide.md`
2. `docs/member2.md`
3. `docs/architecture.md`
4. `docs/business-logic.md`
5. `docs/domain-model.md`
6. `docs/team-contribution.md`

Also read:

7. `docs/booking-workflow.md`

The booking workflow is important because the Bed entity is used by the booking system.

---

# 3. Primary Responsibility

Member 2 owns:

- PG model and property-management logic.
- PG creation.
- PG editing.
- PG viewing.
- PG management by owners.
- Room model and management.
- Bed model and management.
- Owner property dashboard.
- Property ownership authorization.
- Property-management forms.
- Property-management templates.
- Property-management tests.

Member 2 does NOT own authentication itself.

Authentication and the core User system belong to Member 1.

---

# 4. Domain Hierarchy

The domain hierarchy must remain:

Owner
  ↓
PG
  ↓
Room
  ↓
Bed

This means:

- A PG belongs to an Owner.
- A Room belongs to a PG.
- A Bed belongs to a Room.

Do not create duplicate ownership relationships unless explicitly approved by the team.

---

# 5. PG Entity

A PG represents a physical paying-guest accommodation property listed on StayEase.

A PG must have an owner.

Conceptually:

Owner 1 ─────── N PGs

One owner may manage multiple PG properties.

Example:

Owner: Rahul

    Green View PG
    Sunrise Residency
    City Stay PG

Each PG must remain associated with the owner who manages it.

---

# 6. PG Information

The PG should contain the information agreed upon in the domain model.

Potential information includes:

- PG name.
- Description.
- Address.
- Location.
- Contact information.
- Property status.
- Other approved property information.

Do not introduce unnecessary fields simply because they may be useful.

If a new business requirement requires a new field, discuss it with Member 1 before changing the shared domain model.

---

# 7. PG Creation

An authenticated Owner should be able to create a PG.

Expected flow:

Owner
  ↓
Owner Dashboard
  ↓
Create PG
  ↓
Enter PG information
  ↓
Validate input
  ↓
Create PG
  ↓
PG belongs to authenticated Owner

The owner relationship must be assigned by the backend.

Do not allow the client to choose another user's ID and become the owner of the PG.

---

# 8. PG Management

An Owner should be able to manage their own PGs.

Required functionality:

- List own PGs.
- View PG details.
- Create PG.
- Edit PG.
- Deactivate/remove PG where supported by the agreed business rules.

Example:

Owner A owns:

Green View PG

Owner A can:

- View it.
- Edit it.
- Manage its rooms.
- Manage its beds.

Owner B cannot modify it.

---

# 9. Ownership Authorization

Ownership authorization is a critical requirement.

Never rely only on the UI.

For example, hiding:

ext
[Edit PG]

from Owner B is not sufficient.

The backend must reject an unauthorized request.

Conceptually:

Authenticated User
       ↓
Is this user the PG owner?
       ↓
      YES → allow
       ↓
       NO → deny

The same principle applies to:

PGs.
Rooms.
Beds.

An owner must only manage resources belonging to their own PG.

10. Room Entity

A Room represents an individual room inside a PG.

Relationship:

PG 1 ─────── N Rooms

A Room must belong to exactly one PG.

Example:

Green View PG

Room 101
Room 102
Room 203

A room should not exist independently of a PG.

11. Room Information

The exact fields must follow domain-model.md.

Potential fields include:

Room number.
Room type.
Capacity.
Rent.
Description.
Status.

Do not add major fields without discussing them with the team.

12. Room Management

An Owner should be able to:

Add a room to their PG.
View rooms in their PG.
Edit a room.
Deactivate/remove a room where appropriate.

Expected flow:

Owner
↓
My PG
↓
Manage Rooms
↓
Add Room
↓
Room belongs to selected PG

The backend must verify that the selected PG belongs to the authenticated owner.

13. Bed Entity

A Bed represents an individually bookable accommodation unit.

Relationship:

Room 1 ─────── N Beds

Example:

Room 203

Bed A
Bed B
Bed C

The Bed is important because the booking system works at the bed level.

The booking module owned by Member 4 will eventually reference this Bed.

14. Bed Management

An Owner should be able to:

Add a bed to a room.
View beds.
Edit bed information.
Manage bed availability according to the approved domain model.

Expected hierarchy:

Owner
↓
PG
↓
Room
↓
Bed

The backend must verify the complete ownership chain.

For example:

Owner A
↓
Green View PG
↓
Room 203
↓
Bed B

Owner B must not be able to modify Bed B.

15. Bed Availability

The property-management module may maintain the property/bed information required to determine availability.

However, Member 2 must NOT implement booking availability logic independently.

The booking system owned by Member 4 is responsible for authoritative booking validation and concurrency.

Important distinction:

Member 2:

Manages the bed.
Provides bed information.
Provides property-level availability information where required.

Member 4:

Determines whether the bed can actually be booked.
Handles booking conflicts.
Handles concurrent requests.

Do not duplicate booking logic inside Member 2's module.

16. Owner Dashboard

Create the owner-side property management experience.

Conceptual workflow:

Owner Login
↓
Owner Dashboard
↓
My PGs
↓
Select PG
↓
Manage Rooms
↓
Manage Beds

The dashboard should make it clear which PGs belong to the authenticated owner.

17. Property Visibility

The project needs to distinguish between property management and tenant discovery.

Member 2 owns property creation and management.

Member 3 owns the tenant-facing discovery/search experience.

Therefore:

Member 2:

Creates and maintains PG data.

Member 3:

Displays/searches PG data for tenants.

Do not duplicate the tenant search system inside the property-management module.

18. Dependencies
Depends on Member 1

Member 2 depends on:

User model.
Authentication.
Owner role.
Authorization.

Do not create a separate user/owner authentication system.

Used by Member 3

Member 3 depends on:

PG.
Room.
Bed.

Therefore property models must provide clean relationships for tenant-facing discovery.

Used by Member 4

Member 4 depends on:

PG.
Room.
Bed.

The booking relationship will eventually be:

Tenant
↓
Booking
↓
Bed
↓
Room
↓
PG
↓
Owner

Do not make breaking changes to these relationships without coordinating with Member 4 and Member 1.

19. Database Changes

If PG, Room, or Bed models are created or modified:

Run:

python manage.py makemigrations

Review the generated migration.

Then test:

python manage.py migrate

Migration files must be committed to Git.

Do not modify an already merged migration.

Create a new migration for subsequent schema changes.

20. Forms and Validation

Forms must validate user input.

Examples:

Required PG fields must be present.
Room information must be valid.
Bed identifiers must be valid according to the agreed rules.
Invalid data should produce useful validation errors.

Do not rely only on HTML/browser validation.

Important business validation must occur on the server.

21. Views

Views should:

Authenticate users where required.
Verify ownership.
Validate input.
Call the appropriate business logic.
Return appropriate responses/templates.

Do not put large amounts of unrelated business logic directly into templates.

22. Templates

Use the existing Django template architecture.

Follow existing project conventions.

Use:

Template inheritance.
Reusable templates/components where appropriate.
Existing static assets.
Existing styling conventions.

Do not introduce React or another frontend framework.

23. Testing Requirements

Member 2 must create automated tests for the property-management functionality.

PG tests

Test:

Owner can create a PG.
PG is associated with the authenticated owner.
Owner can view their PG.
Owner can edit their PG.
Owner cannot edit another owner's PG.
Unauthorized users cannot access owner-only functionality.
Room tests

Test:

Owner can create a room.
Room belongs to the correct PG.
Owner can edit their room.
Owner cannot modify a room belonging to another owner.
Room cannot be associated incorrectly.
Bed tests

Test:

Owner can create a bed.
Bed belongs to the correct room.
Owner can edit their bed.
Owner cannot modify another owner's bed.
Invalid relationships are rejected.
24. Security Requirements

Never trust IDs supplied by the client.

For example, do not assume:

/pg/123/edit/

is safe simply because the user is authenticated.

The backend must verify:

Current User
     ↓
Owns PG 123?
     ↓
YES → allow
NO → deny

The same applies to nested resources:

/pg/123/room/45/bed/2/

Verify the complete ownership relationship.

25. Agent Instructions

If using a coding agent, start with:

I am Member 2 of the StayEase project. Read docs/development-guide.md and docs/member2.md before making any changes.

Then instruct the agent to:

Inspect the existing repository.
Inspect the existing User model and authentication implementation.
Inspect existing PG, Room, and Bed code if present.
Inspect existing migrations.
Understand the existing architecture before modifying it.
Implement only Member 2's responsibilities.
Follow the domain relationships defined by domain-model.md.
Enforce ownership authorization on the backend.
Add automated tests.
Create migrations when necessary.
Run relevant tests.
Report all changed files.
Report migrations created.
Report any dependencies on other members.
Do not redesign authentication, search, booking, notifications, or payment.
26. What the Agent Must NOT Do

The agent must not independently:

Replace the User model.
Replace authentication.
Implement search.
Implement booking approval.
Implement booking concurrency.
Implement notifications.
Implement payment.
Introduce React.
Introduce a REST API.
Add unnecessary dependencies.
Change the overall architecture.
Modify another member's module unnecessarily.
27. Expected User Workflow

The completed property-management module should support:

Owner
  ↓
Login
  ↓
Owner Dashboard
  ↓
My PGs
  ↓
Create PG
  ↓
View PG
  ↓
Manage Rooms
  ↓
Create Room
  ↓
Manage Beds
  ↓
Create Bed
28. Definition of Done

Member 2's module is ready for integration when:

PG management works.
Room management works.
Bed management works.
Ownership authorization works.
Unauthorized access is rejected.
Models follow the approved domain model.
Required migrations are created.
Automated tests are present.
Tests pass.
The module works inside Docker Compose.
Property data is usable by Member 3's search module.
Bed data is usable by Member 4's booking module.
No unrelated functionality has been introduced.
