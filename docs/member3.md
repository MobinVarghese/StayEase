StayEase — Member 3 Development Specification

Role

You are Member 3 — Tenant Discovery & Search Owner.

You own the tenant-facing experience for discovering available PG accommodation.

Your responsibility is to make accommodation easy to find and understand without taking ownership of booking transactions.

Primary Ownership

You own:

PG listing/discovery

Search

Filtering

Sorting where required

PG detail page

Room/bed availability presentation

Tenant-facing accommodation navigation

Discovery templates

Discovery URLs/views

Discovery tests

Dependencies

You depend on:

Member 1 for authentication and shared architecture.

Member 2 for PG/Room/Bed domain data.

Member 4 for the final booking-request entry point.

You should not directly implement Member 4's booking transaction logic.

Main User Journey

The tenant flow is:

Tenant
  ↓
Browse PGs
  ↓
Search / Filter
  ↓
PG Details
  ↓
Inspect rooms/beds
  ↓
Select available bed
  ↓
Request booking

The final booking request belongs to Member 4.

Listing Page

The listing page should present useful information without overloading the user.

A PG card may show:

Name

Location

Pricing summary

Key amenities

Availability summary

Relevant image

Link to details

Avoid exposing internal administrative information.

Search

Search should be implemented at the database/query level where practical.

Do not load the entire PG table into Python and then filter it manually.

Conceptually:

Request
  ↓
Query parameters
  ↓
Database query
  ↓
Filtered PG queryset
  ↓
Pagination
  ↓
Response

Filtering

Depending on the agreed product requirements, support filters such as:

Location

Price range

Availability

PG attributes/amenities

Other explicitly approved fields

Do not invent a large filter system without product justification.

PG Detail Page

The detail page should provide:

PG
├── Basic information
├── Location
├── Amenities
├── Rooms
│    ├── Room details
│    └── Bed availability
└── Booking entry point

Tenants should be able to understand what they are booking before proceeding.

Availability Presentation

You display availability.

Member 4 decides whether a booking can actually be committed.

This distinction is important:

Member 3:
"Bed appears available."

Member 4:
"Transaction confirms whether the bed can actually be booked."

Never treat the display as a reservation lock.

Booking Integration

The discovery page should provide a clean handoff to Member 4.

For example:

Select Bed
    ↓
Booking Request

The booking request must be validated again by Member 4.

Do not assume that a bed shown as available is still available when the request arrives.

Performance

Avoid:

N+1 queries

Loading unnecessary fields

Filtering large datasets in Python

Fetching unrelated owner/private data

Use appropriate:

select_related

prefetch_related

database filtering

pagination

indexes in coordination with Member 2

Do not add indexes blindly.

Security

Tenant-facing pages must not expose:

Owner private information

Internal IDs unnecessarily

Administrative data

Other tenants' booking information

A tenant should only see accommodation information intended for public discovery.

Scope Boundaries

You DO NOT own

PG CRUD

Room CRUD

Bed CRUD

Authentication

Booking transaction

Booking concurrency

Payment

Notifications

Admin management

You consume the inventory domain rather than owning it.

Testing Requirements

Test:

PG listing

Search

Each supported filter

Empty search results

Pagination

PG detail page

Room/bed presentation

Only appropriate listings appear

Authentication behavior where applicable

Booking handoff

Invalid/nonexistent PG IDs

Query efficiency for important views

Agent Instructions

Read Member 1 and Member 2 specifications first.

Use the existing inventory models.

Do not duplicate PG/Room/Bed models.

Keep filtering in the database.

Do not implement reservation locking.

Do not trust displayed availability.

Keep tenant views separate from owner management.

Add tests for every filter and important edge case.

Avoid unnecessary frontend complexity.

Keep commits scoped to discovery.

Definition of Done

Listing page complete

Search complete

Required filters complete

PG details complete

Room/bed availability visible

Booking handoff integrated

Query performance reviewed

Security reviewed

Tests pass

No duplicated inventory or booking logic
