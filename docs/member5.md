StayEase — Member 5 Development Specification

Role

You are Member 5 — Notifications, Dummy Payment & Admin Owner.

You own the user-facing consequences of booking events and the administrative workflows required by the platform.

Your work consumes the booking system rather than reimplementing it.

Primary Ownership

You own:

Notification system

Dummy payment flow

Payment status handling

Booking-related user notifications

Admin dashboard/workflows

Administrative moderation

Tests for these areas

Integration with Member 4's booking events

Dependencies

You depend on:

Member 1 for authentication and admin authorization.

Member 2 for accommodation relationships where admin views need them.

Member 4 for booking lifecycle/state changes.

Member 4 must not need to know how your notifications are rendered.

Notification System

Notifications should communicate important events such as:

Booking requested
Booking approved
Booking rejected
Payment required
Payment successful
Booking confirmed

The exact list should follow the product requirements.

Notification Data

A notification should have enough information to:

Identify recipient

Identify event/message

Track read/unread state

Store creation time

Link to relevant application resource where useful

Do not expose private information to the wrong recipient.

Notification Rules

Example:

Tenant requests booking
        ↓
Owner receives notification

Owner approves
        ↓
Tenant receives notification

Owner rejects
        ↓
Tenant receives notification

Payment succeeds
        ↓
Tenant receives confirmation

Notifications should be triggered from booking events/state transitions, not by scraping HTML or duplicating booking logic.

Notification Read State

Provide a simple mechanism for:

Viewing notifications

Marking as read

Showing unread count where the UI requires it

Avoid building unnecessary real-time infrastructure unless explicitly required.

Dummy Payment

This is intentionally a dummy payment system for the academic project.

It should demonstrate:

Approved booking
      ↓
Payment Pending
      ↓
Dummy payment page
      ↓
Simulated success/failure
      ↓
Booking confirmation

There is no real payment gateway.

Do not collect or store real card numbers, CVVs, UPI credentials or other sensitive payment credentials.

Payment Authorization

Only the correct tenant should be able to pay for their own eligible booking.

Do not allow:

Tenant A
   ↓
modify Tenant B's payment

The server must verify:

Authenticated user

Booking ownership

Booking state

Payment eligibility

Duplicate Payment Prevention

Prevent a user from repeatedly "paying" an already confirmed booking.

Conceptually:

PAYMENT_PENDING → CONFIRMED

is valid.

CONFIRMED → CONFIRMED

should not create another payment result or duplicate confirmation.

Payment Failure

If the dummy payment supports failure:

PAYMENT_PENDING
      ↓
   FAILED

should follow the agreed state design.

Do not invent new states that conflict with Member 4's booking state machine. Coordinate before changing the shared model.

Admin Responsibilities

The admin area should provide appropriate platform-level oversight, such as:

User management

PG/listing moderation

Booking oversight

Report/review of problematic content if included

Basic platform statistics where required

Admin operations must be protected server-side.

Administrative Boundaries

Admin should not require bypassing model-level business rules arbitrarily.

If an administrative override is genuinely required, make it explicit and auditable.

Do not build unrestricted:

delete everything
change any user's data

actions without authorization and validation.

Integration with Member 4

Member 4 owns booking state.

Member 5 consumes the booking lifecycle.

Conceptually:

BookingRequested
       ↓
Notification

BookingApproved
       ↓
Notification
       ↓
PaymentPending

PaymentSuccess
       ↓
BookingConfirmed
       ↓
Notification

Avoid circular dependencies.

Authorization Matrix

Action                         Tenant   Owner   Admin
-------------------------------------------------------
View own notifications          ✓       ✓       ✓
Mark own notification read      ✓       ✓       ✓
Pay own approved booking        ✓       ✗       -
View own payment                ✓       ✗       -
Admin moderation                ✗       ✗       ✓
Platform-level oversight        ✗       ✗       ✓

Scope Boundaries

You DO NOT own

Authentication implementation

PG/Room/Bed CRUD

Search/filtering

Booking concurrency

Booking state-machine ownership

You may integrate with these modules but must not duplicate their logic.

Testing Requirements

Notifications

Test:

Correct recipient

Correct event

Read/unread state

Unauthorized access

Notification isolation

Payment

Test:

Eligible booking can enter dummy payment

Wrong tenant is rejected

Non-approved booking is rejected

Successful dummy payment confirms through the agreed contract

Duplicate payment is prevented

Invalid payment requests are rejected

Admin

Test:

Admin access

Non-admin rejection

User/listing moderation authorization

Appropriate data visibility

Invalid administrative operations

Security Requirements

Never:

Store real payment credentials

Trust payment status sent by the browser

Allow users to edit another user's notification

Allow arbitrary booking confirmation from a client request

Expose admin endpoints without authorization

A request such as:

POST /payment/success

must not simply trust:

booking_status=confirmed

from the client.

The server must verify the booking and transition it through the approved application logic.

Agent Instructions

Read Member 1's authorization rules.

Read Member 4's booking state machine.

Do not create a competing booking model.

Treat booking state as owned by Member 4.

Use clear interfaces/events for integration.

Keep dummy payment intentionally simple.

Never store real payment credentials.

Test authorization aggressively.

Avoid circular imports/dependencies.

Document any shared-model change before implementing it.

Definition of Done

Notification model/service complete

Booking notifications integrated

Read/unread behavior complete

Dummy payment flow complete

Payment authorization complete

Duplicate payment prevented

Booking confirmation integration complete

Admin authorization complete

Required admin workflows complete

Tests pass

No real payment credentials are collected

No booking logic is duplicated

Integration with Member 4 is clean and documented
