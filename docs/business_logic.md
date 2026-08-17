# StayEase — Business Logic

## 1. Project Overview

StayEase is a web-based PG accommodation discovery and booking platform.

The system connects two primary users:

- Tenants looking for PG accommodation.
- PG Owners who list and manage their properties.

An Administrator is responsible for managing and monitoring the platform.

The main purpose of StayEase is to provide a centralized platform where tenants can discover PG accommodations, view room and bed availability, submit booking requests, and receive booking decisions from PG owners.

PG owners can manage their properties, rooms, beds, and booking requests through the platform.

---

## 2. Actors

### Tenant

A tenant is a user looking for PG accommodation.

A tenant can:

- Register and log in.
- Search and browse PGs.
- View PG details.
- View rooms and bed availability.
- Request a booking for an available bed.
- View booking status.
- Receive notifications.
- Make a dummy payment after booking approval.
- View booking history.

---

### PG Owner

An owner manages one or more PG properties.

An owner can:

- Register and log in.
- Create and manage PG listings.
- Add rooms to a PG.
- Add beds to rooms.
- Define room and bed availability.
- View booking requests.
- Approve or reject booking requests.
- View current and previous bookings.
- Receive notifications.

---

### Administrator

The administrator manages the platform.

The administrator can:

- Manage users.
- Monitor PG listings.
- Monitor bookings.
- Manage reported/problematic content if implemented.
- View platform-level information.

---

## 3. Core Business Flow

The primary StayEase workflow is:

Tenant searches for a PG
        ↓
Tenant views PG details
        ↓
Tenant views rooms and available beds
        ↓
Tenant requests a booking
        ↓
Booking enters PENDING state
        ↓
Owner receives notification
        ↓
Owner reviews request
        ↓
Owner approves or rejects
        ↓
If rejected → Tenant is notified
        ↓
If approved → Tenant is notified
        ↓
Tenant performs dummy payment
        ↓
Booking becomes CONFIRMED

---

## 4. PG Management

A PG Owner can create a PG listing.

A PG contains multiple rooms.

A room contains one or more beds.

The hierarchy is:

Owner
  ↓
PG
  ↓
Room
  ↓
Bed

Example:

Green View PG
    ├── Room 101
    │     ├── Bed A
    │     ├── Bed B
    │     └── Bed C
    │
    └── Room 102
          ├── Bed A
          └── Bed B

The availability of individual beds is important because the platform is intended to support bed-level booking.

---

## 5. Booking Logic

A tenant does not immediately receive a confirmed booking when they press "Request Booking".

Instead, a booking request is created with:

status = PENDING

The owner receives the request and can:

- Approve the request.
- Reject the request.

If the owner rejects the request:

PENDING → REJECTED

The tenant receives a notification.

If the owner approves the request:

PENDING → APPROVED

The tenant is notified and can proceed to the dummy payment process.

After approval:

APPROVED → PAYMENT PENDING

After successful dummy payment:

PAYMENT PENDING → CONFIRMED

---

## 6. Double Booking Prevention

A bed must not be assigned to two confirmed bookings for overlapping periods.

For example:

Tenant A ──┐
           ├── requests Bed B
Tenant B ──┘

If both requests occur at approximately the same time, the system must ensure that the same bed cannot be confirmed for both tenants.

The booking process will therefore perform availability validation and use appropriate database transaction/concurrency controls.

---

## 7. Notifications

Notifications are generated for important booking events.

Examples:

### Owner notification

"When Tenant A requested Bed B in Room 203."

### Tenant notification

"Your booking request has been approved."

### Tenant notification

"Your booking request has been rejected."

Notifications allow users to know the current status of important actions without continuously checking the booking page.

---

## 8. Dummy Payment

The project will use a dummy payment workflow for demonstration purposes.

The purpose is to demonstrate the business flow rather than process real financial transactions.

The expected flow is:

Booking Approved
      ↓
Payment Page
      ↓
Dummy Payment
      ↓
Payment Success
      ↓
Booking Confirmed

No real money or production payment gateway is required for the project scope.

---

## 9. Responsibility for Availability

PG owners are responsible for maintaining the accuracy of their own listings.

This includes:

- Adding rooms.
- Adding beds.
- Updating availability.
- Updating room information.
- Managing booking requests.

StayEase provides the management system but does not automatically synchronize availability with external PG listing websites.

If an owner lists the same PG on another platform, maintaining consistency between those external listings and StayEase remains the owner's responsibility.

---

## 10. Project Boundary

### Included

- User authentication.
- Tenant functionality.
- Owner functionality.
- PG management.
- Room management.
- Bed management.
- PG search and discovery.
- Availability display.
- Booking requests.
- Owner approval/rejection.
- Booking status management.
- Notifications.
- Dummy payment.
- Booking history.
- Administrative management.

### Not Included in the Initial Version

- Real payment gateway integration.
- Automatic synchronization with other PG websites.
- Native Android/iOS application.
- Automatic verification of PG ownership.
- Real-time GPS tracking.
- Automatic legal verification.
- External marketplace synchronization.

These features may be considered future enhancements.