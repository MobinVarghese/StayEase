# StayEase — Domain Model

## 1. Overview

The StayEase domain is centered around PG accommodation and booking.

The main entities are:

- User
- PG
- Room
- Bed
- Booking
- Notification
- Payment

---

## 2. User

The User represents a person using the StayEase platform.

A user has a role that determines the functionality available to them.

Possible roles:

- TENANT
- OWNER
- ADMIN

A user can act as a tenant or owner depending on their role.

---

## 3. PG

A PG represents a paying guest accommodation property listed by an owner.

Relationship:

Owner 1 ──────── N PGs

One owner can manage multiple PG properties.

A PG contains multiple rooms.

Relationship:

PG 1 ──────── N Rooms

Example:

Owner
  |
  +-- Green View PG
  |
  +-- Sunrise PG

---

## 4. Room

A Room represents an individual room inside a PG.

A room belongs to exactly one PG.

Relationship:

PG 1 ──────── N Room

A room contains one or more beds.

Relationship:

Room 1 ──────── N Bed

A room may contain information such as:

- Room number.
- Room type.
- Capacity.
- Rent.
- Description.

---

## 5. Bed

A Bed represents an individually bookable sleeping space.

A bed belongs to exactly one room.

The bed is the primary unit that a tenant requests to book.

Example:

Room 203

    Bed A → Available
    Bed B → Occupied
    Bed C → Available

---

## 6. Booking

A Booking represents a tenant's request to reserve a bed.

A booking connects:

Tenant → Bed

Relationship:

Tenant 1 ──────── N Booking

Bed 1 ─────────── N Booking

However, business rules must prevent multiple active/overlapping bookings for the same bed.

A booking contains information such as:

- Tenant.
- Bed.
- Status.
- Request time.
- Move-in date.
- Approval information.
- Confirmation information.

---

## 7. Booking Status

The initial booking states are:

PENDING
APPROVED
PAYMENT PENDING
REJECTED
CONFIRMED

Possible flow:

PENDING
   ├── APPROVED
   │      ↓
   │  PAYMENT PENDING
   │      ↓
   │   CONFIRMED
   │
   └── REJECTED

---

## 8. Notification

A Notification represents a message generated for a user because of an important system event.

A notification can be associated with:

- Recipient.
- Booking.
- Message.
- Read/unread state.
- Creation time.

Examples:

Booking requested
Booking approved
Booking rejected
Payment completed

---

## 9. Payment

Payment represents the dummy payment associated with an approved booking.

A payment can contain:

- Booking.
- Amount.
- Status.
- Transaction reference.
- Creation time.

The payment functionality is for project demonstration and does not process real money.

---

## 10. Relationships Summary

User
  │
  ├── owns ──→ PG
  │              │
  │              └── contains ──→ Room
  │                                  │
  │                                  └── contains ──→ Bed
  │
  └── creates ──→ Booking
                     │
                     ├── references ──→ Bed
                     │
                     ├── generates ──→ Notification
                     │
                     └── has ──→ Payment

---

## 11. Important Constraints

1. A PG must belong to an owner.

2. A room must belong to a PG.

3. A bed must belong to a room.

4. A booking must belong to a tenant.

5. A booking must reference a bed.

6. A bed must not have multiple conflicting active bookings.

7. Only an owner responsible for a PG should be able to manage its rooms and beds.

8. A tenant should only be able to request bookings for beds that are available.

9. Payment should only be initiated after booking approval.

10. Booking confirmation should occur only after successful dummy payment.