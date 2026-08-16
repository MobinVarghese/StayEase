# StayEase — Booking Workflow

## 1. Objective

The booking system allows a tenant to request an available bed in a PG.

The owner reviews the request and decides whether to approve or reject it.

If approved, the tenant can complete the dummy payment process.

---

## 2. Booking Lifecycle

The primary lifecycle is:

PENDING
   |
   +------> REJECTED
   |
   +------> APPROVED
                |
                v
        PAYMENT PENDING
                |
                v
             CONFIRMED

---

## 3. Step-by-Step Workflow

### Step 1 — Tenant searches for a PG

The tenant searches or browses available PG listings.

---

### Step 2 — Tenant views PG

The tenant can view:

- PG name.
- Description.
- Location.
- Rooms.
- Room information.
- Rent.
- Bed availability.

---

### Step 3 — Tenant selects an available bed

The tenant selects an available bed and chooses:

"Request Booking"

---

### Step 4 — System validates availability

The backend checks whether the selected bed is still available.

This validation is important because another tenant may have requested the same bed.

---

### Step 5 — Booking request is created

If the bed is available:

Booking
status = PENDING

The booking request is stored in PostgreSQL.

---

### Step 6 — Owner is notified

The owner receives a notification that a tenant has requested the bed.

Example:

"Rahul requested Bed B in Room 203."

---

### Step 7 — Owner reviews the request

The owner can:

[Approve]

or

[Reject]

---

## 4. Rejection Flow

If the owner rejects the request:

Booking
status = REJECTED

The tenant receives a notification.

Example:

"Your booking request for Green View PG has been rejected."

The booking process ends.

---

## 5. Approval Flow

If the owner approves:

Booking
status = APPROVED

The tenant receives a notification.

Example:

"Your booking request has been approved."

The tenant can now proceed to the dummy payment page.

---

## 6. Dummy Payment

The tenant submits the dummy payment.

If successful:

Payment
status = SUCCESS

Booking
status = CONFIRMED

The tenant receives confirmation.

---

## 7. Concurrent Booking Requests

Consider:

Bed B is available.

At approximately the same time:

Tenant A → Request Bed B
Tenant B → Request Bed B

The system must not allow both tenants to obtain the same bed.

The backend must perform the availability check and booking operation atomically using database transaction/concurrency controls.

Expected result:

Tenant A → Booking accepted
Tenant B → Booking rejected because the bed is no longer available

The exact winner depends on which transaction successfully obtains the required database lock/constraint.

---

## 8. Booking History

A tenant should be able to view previous bookings.

Example:

Booking #101
Green View PG
Bed B
CONFIRMED

Booking #102
Sunrise PG
Bed C
REJECTED

---

## 9. Owner Booking Management

An owner should be able to view:

- Pending requests.
- Approved bookings.
- Rejected requests.
- Confirmed bookings.

The owner should only be able to manage bookings associated with their own PG properties.