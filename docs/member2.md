StayEase — Member 2 Development Specification

Role

You are Member 2 — Property Inventory Owner.

You own the complete accommodation inventory domain:

Owner
  └── PG
       └── Room
            └── Bed

This is the source of truth for accommodation structure and bed inventory.

Primary Ownership

You own:

PG model

Room model

Bed model

Owner property dashboard

PG CRUD

Room CRUD

Bed CRUD

Inventory validation

Owner-to-property relationships

Availability-related inventory fields

Tests and migrations for this domain

Dependencies

You depend on:

Member 1 for authentication and owner authorization.

Members depending on you:

Member 3 uses PG/Room/Bed data for discovery.

Member 4 uses beds and their availability for booking.

Member 5 may use property/booking relationships for administrative workflows.

Domain Model

Conceptually:

User
  │
  └── Owner
       │
       └── PG
            │
            └── Room
                 │
                 └── Bed

A PG belongs to an owner.

A room belongs to a PG.

A bed belongs to a room.

The database relationships must enforce these ownership boundaries.

PG Responsibilities

A PG should contain the information necessary for discovery and booking, such as:

Owner

Name

Description

Address/location information

Pricing information where applicable

Amenities

Images/media references if included by the project

Active/listing status

Timestamps

Do not add arbitrary fields merely because they might be useful later.

Room Responsibilities

A room belongs to exactly one PG.

Room information may include:

Room number/name

Capacity

Room type

Pricing where the design requires it

Status/active state

Description if required

Validate that room capacity and bed inventory remain logically consistent.

Bed Responsibilities

A bed belongs to exactly one room.

A bed should have:

Identifier/label

Status/availability information appropriate to the booking model

Active state if needed

The exact booking ownership/state must remain compatible with Member 4's concurrency-safe booking implementation.

Do not implement a second competing booking state machine.

Owner Dashboard

Provide owner-facing workflows for:

PG

Create

View

Update

Delete/deactivate

Room

Add

View

Update

Delete/deactivate

Bed

Add

View

Update

Delete/deactivate

The UI should make the hierarchy obvious.

Example:

My PGs
  └── Green Valley PG
       ├── Room 101
       │    ├── Bed A
       │    ├── Bed B
       │    └── Bed C
       └── Room 102
            ├── Bed A
            └── Bed B

Authorization

This is mandatory.

Owner A must not be able to:

Edit Owner B's PG

Delete Owner B's room

Modify Owner B's bed

View private management data belonging to Owner B

Do not trust IDs supplied by the browser.

Always derive ownership from the authenticated user.

Availability Boundary

You own inventory-level availability data.

You do NOT own the final booking decision.

Member 4 owns:

Booking records

Booking state transitions

Transactional reservation

Concurrency

Coordinate with Member 4 before changing fields that affect booking behavior.

Database Requirements

Use proper:

Foreign keys

Constraints

Indexes where justified

Timestamps

Nullability rules

Unique constraints where appropriate

Think about database integrity rather than relying exclusively on form validation.

Validation

Validate:

Required fields

Capacity

Invalid negative/zero values

Invalid ownership relationships

Duplicate room identifiers where the domain requires uniqueness

Invalid bed relationships

Deletion/deactivation rules

Migrations

You own migrations for:

PG

Room

Bed

Keep migrations small and reviewable.

Do not casually edit old migrations that may already have been applied by other developers.

If a migration conflicts with another member's migration, coordinate rather than forcing a merge.

Testing Requirements

Test:

PG creation

PG update

PG deletion/deactivation

Room creation

Bed creation

Relationship integrity

Owner isolation

Invalid values

Duplicate constraints

Authentication requirements

Unauthorized access

Cascading/protected deletion behavior as designed

Important security test:

Owner A requests Owner B's PG
        ↓
Request must be rejected

Scope Boundaries

Do NOT implement

Authentication

Search engine/filter UI

Booking state machine

Booking concurrency

Dummy payment

Notification system

Admin workflows

You may expose the domain data required by those modules, but do not own their business logic.

Integration Contract

Member 3 should be able to query:

PG → Rooms → Beds

Member 4 should be able to identify a specific bed and safely perform booking operations.

Do not force other members to depend on owner-dashboard HTML or internal implementation details.

Agent Instructions

Read Member 1's architecture/authentication rules.

Inspect existing models before creating new ones.

Do not duplicate the user model.

Keep PG/Room/Bed ownership centralized.

Never trust URL IDs for authorization.

Keep booking logic out of inventory CRUD.

Add tests with every meaningful behavior.

Coordinate schema changes with Members 3 and 4.

Avoid premature abstraction.

Keep commits focused.

Definition of Done

PG model complete

Room model complete

Bed model complete

Relationships enforced

Owner CRUD complete

Owner authorization complete

Validation complete

Migrations complete

Tests complete

Member 3 can consume inventory data

Member 4 can safely identify bookable beds

No booking/payment/notification logic duplicated
