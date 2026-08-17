StayEase — Member 4 Development Specification

Role

You are Member 4 — Booking, Availability & Concurrency Owner.

You own the most transaction-sensitive domain in StayEase.

Your responsibility is to ensure that a bed can be requested, approved/rejected and confirmed without violating booking invariants, including when multiple users attempt to book the same bed concurrently.

Primary Ownership

You own:

Booking model

Booking request creation

Booking state machine

Booking validation

Owner approval/rejection

Booking confirmation

Transaction handling

Concurrency control

Booking history

Booking-related service logic

Booking tests

Integration with notifications/payment contracts

Dependencies

You depend on:

Member 1 for authentication/authorization.

Member 2 for PG/Room/Bed inventory.

Member 3 for the tenant-facing booking entry point.

Member 5 depends on your booking states/events for:

Notifications

Dummy payment

Booking State Machine

The agreed lifecycle is:

PENDING
   ├──> REJECTED
   └──> APPROVED
          │
          ▼
   PAYMENT_PENDING
          │
          ▼
      CONFIRMED

Do not allow arbitrary state changes.

For example:

CONFIRMED → PENDING

must not happen through a normal user operation.

Booking Data

A booking should associate:

Tenant

Bed

Relevant property/room context through relationships

Status

Created timestamp

Updated timestamp

Approval information where required

Payment state/reference where required by the agreed design

Booking period/occupancy information if the product requires it

Do not duplicate PG/Room/Bed information unnecessarily if it can be derived through relationships.

Booking Request

A tenant submits a request for a specific bed.

Server-side validation must verify:

User is authenticated

User is allowed to create a booking

Bed exists

Bed is active

PG/room/bed relationships are valid

The request does not violate current booking rules

The tenant does not already have an incompatible active booking

The same bed cannot have conflicting active bookings

Never rely on the UI's availability display.

Owner Approval

Only the owner of the relevant PG can approve/reject the request.

The system must verify ownership server-side.

Owner A must not be able to approve Owner B's booking.

The approval operation must validate that the booking is still eligible for approval.

Concurrency

This is a critical requirement.

Naive logic:

check bed
if available:
    create booking

is unsafe because two requests may execute the check before either creates the booking.

Use Django/database transaction mechanisms appropriate for PostgreSQL.

The implementation should establish a clear invariant such as:

At most one conflicting active/confirmed booking exists for a bed.

Use database constraints and/or row locking/transactional logic where appropriate.

Do not depend exclusively on Python-level checks.

Transaction Boundary

A critical booking operation should be treated as one logical transaction.

Conceptually:

BEGIN
  ↓
Lock/check relevant inventory
  ↓
Validate booking invariant
  ↓
Create/update booking
  ↓
Commit

If any required operation fails, the transaction should not leave partially updated state.

Duplicate Requests

Prevent obvious duplicate requests such as:

Tenant
  ↓
requests same bed repeatedly

The exact behavior should follow the agreed product rules, but duplicate active requests should not be created accidentally.

Booking History

Tenants should be able to see their booking history/status.

Owners should be able to see requests associated with their PGs.

Users must not see another user's private booking data.

Authorization Matrix

Action                    Tenant   Owner   Admin
------------------------------------------------
Create booking              ✓       ✗       -
View own booking            ✓       ✗       -
Approve booking             ✗       ✓       -
Reject booking              ✗       ✓       -
View owner requests        ✗       Own     ✓
Administrative override    ✗       ✗       ✓

The exact admin capabilities should follow the admin design.

Integration with Member 5

Member 4 should expose a clear concept of booking events/state changes.

Examples:

BookingRequested
BookingApproved
BookingRejected
PaymentPending
BookingConfirmed

Do not tightly couple the booking module to notification implementation.

Member 5 should consume a stable interface/service/event contract.

Scope Boundaries

You DO NOT own

User authentication

PG CRUD

Room CRUD

Bed CRUD

Search/filter UI

Notification rendering

Payment provider implementation

General admin dashboard

You own the booking domain and its correctness.

Testing Requirements

Concurrency tests are mandatory.

Test at minimum:

Valid booking request

Invalid booking request

Unauthorized booking

Owner approval

Wrong-owner approval rejection

Owner rejection

Invalid state transitions

Duplicate request prevention

Already-booked bed

Transaction rollback behavior

Concurrent booking attempts

Booking history isolation

Important scenario:

Two tenants
     │
     ├── request same bed ──┐
     │                      │
     └── request same bed ──┘
                            ↓
                    Only valid winner
                    is allowed to proceed

Agent Instructions

Read Member 1 authentication rules.

Read Member 2's inventory model before designing booking relations.

Read the booking state machine before writing code.

Do not use UI availability as authority.

Put critical operations inside appropriate database transactions.

Use database-level guarantees where appropriate.

Do not silently change booking states.

Add concurrency tests.

Keep notification/payment implementation outside the booking domain.

Explain transaction and locking decisions in the PR.

Definition of Done

Booking model complete

State machine enforced

Tenant request flow complete

Owner approval/rejection complete

Authorization complete

Duplicate/conflicting bookings prevented

Transaction boundaries reviewed

Concurrency protection implemented

Database constraints reviewed

Booking history complete

Tests including concurrency pass

Stable integration contract exists for Member 5
