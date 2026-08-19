# StayEase — Migration Rules and Schema Change Guide

## 1. Purpose

This document defines the rules every team member must follow when creating,
modifying, or resolving Django migrations.

Migrations are **team-level artifacts** — they directly affect every developer's
local database and the production database.

Treat them with the same care you would treat a production database script.

---

## 2. Shared Schema Baseline

The initial shared schema is established by Member 1 and merged into `main`.

This baseline includes:

| App | Models | Initial migration |
|-----|--------|-------------------|
| `stayease.users` | `User` (with `role` field) | `0001_initial`, `0002_user_role` |
| `stayease.properties` | `PG`, `Room`, `Bed` | `0001_initial` |
| `stayease.bookings` | `Booking` | `0001_initial` |
| `stayease.notifications` | `Notification` | `0001_initial` |
| `stayease.payments` | `Payment` | `0001_initial` |

**Do not recreate, rename, replace, or duplicate these models.**

If your feature requires a schema change, follow the process below.

---

## 3. Before Creating a Migration

### Step 1 — Inspect Existing Migrations

```bash
python manage.py showmigrations
```

Understand which migrations already exist and which have been applied.

### Step 2 — Inspect Existing Usages

Before modifying any model, search the entire codebase for usages:

```bash
grep -R "ModelName" .
grep -R "field_name" .
```

Determine which members depend on the model/field you want to change.

### Step 3 — Make the Smallest Compatible Change

- Adding a new field? Use `null=True` or `default=...` so existing data is not broken.
- Renaming a field? **Do not rename.** Add the new field, migrate data, then deprecate the old one in a coordinated step.
- Removing a field? Verify no other member references it first.
- Changing a field type? Verify all existing data and consumers are compatible.

---

## 4. Creating a Migration

### Step 1 — Generate

```bash
python manage.py makemigrations <app_name>
```

Always specify the app name to avoid accidentally generating migrations for
other apps.

### Step 2 — Review the generated migration file

Open the generated migration file and inspect it.

Ask:

- Does it do what I intend?
- Does it have unexpected side effects?
- Does it delete or rename anything unintentionally?
- Are the dependencies correct?

### Step 3 — Test the migration

```bash
python manage.py migrate
```

Then run the test suite to verify nothing is broken.

### Step 4 — Commit the migration

Commit the migration file alongside the model change in a focused commit:

```
feat(<app>): add <field> to <Model>
```

---

## 5. Rules for Schema Changes in Your Domain

### You Own the App

If you are the designated owner of the app (e.g., Member 2 owns `properties`):

1. You may add fields, indexes, and constraints within your app.
2. You must ensure backward compatibility with consumers.
3. You must communicate changes that affect other members' integration.

### You Do NOT Own the App

If you need a change in another member's app:

1. **Do not modify their models directly.**
2. Document the required change clearly.
3. Coordinate with the app owner.
4. If the owner is unavailable and the change is critical, make the **smallest
   compatible addition** (never rename/remove) and document it as a
   cross-boundary change in your PR description.

---

## 6. Resolving Migration Conflicts

When two members create migrations for the same app on different branches,
Django will detect a conflict when the branches are merged.

### Symptom

```
CommandError: Conflicting migrations detected;
multiple leaf nodes in the migration graph: ...
```

### Resolution Process

#### Option A — Merge Migration (Preferred)

Run:

```bash
python manage.py makemigrations --merge
```

This creates a merge migration that combines the two branches. Review the
generated merge migration to ensure it does not introduce conflicts.

#### Option B — Manual Resolution

If the two migrations modify the same field/model in incompatible ways:

1. Identify which migration should take precedence.
2. Adjust the losing migration to depend on the winning one.
3. Update the losing migration's operations to be compatible.
4. Test thoroughly.

### After Resolving

1. Run `python manage.py migrate` to verify the resolution.
2. Run `python manage.py makemigrations --check` to confirm no pending changes.
3. Run the full test suite.
4. Commit the merge migration with a clear message:

```
fix(<app>): resolve migration conflict between <branch-a> and <branch-b>
```

---

## 7. Migration Safety Checklist

Before committing any migration:

- [ ] `makemigrations --check` reports no pending changes.
- [ ] `migrate` applies cleanly.
- [ ] The migration does not delete or rename existing fields without coordination.
- [ ] The migration does not modify another member's app without documentation.
- [ ] Tests pass.
- [ ] The migration file is committed alongside the model change.
- [ ] No data-destructive operations exist without explicit team agreement.

---

## 8. Shared Enums — Single Source of Truth

The following enums are defined centrally and must not be duplicated:

| Enum | Location | Values |
|------|----------|--------|
| `UserRole` | `stayease/users/models.py` | `TENANT`, `OWNER`, `ADMIN` |
| `BookingStatus` | `stayease/bookings/models.py` | `PENDING`, `APPROVED`, `PAYMENT_PENDING`, `REJECTED`, `CONFIRMED` |
| `PaymentStatus` | `stayease/payments/models.py` | `PENDING`, `SUCCESS`, `FAILED` |

To use these enums in your code:

```python
from stayease.users.models import UserRole
from stayease.bookings.models import BookingStatus
from stayease.payments.models import PaymentStatus
```

**Never hard-code status strings.** Always reference the enum.

---

## 9. Adding a New App

If a new Django app is needed:

1. Create the app under `stayease/<app_name>/`.
2. Add it to `LOCAL_APPS` in `config/settings/base.py`.
3. Create the initial migration.
4. Register models in `admin.py`.
5. Create the `migrations/__init__.py`.
6. Document the app ownership.

---

## 10. Cross-App Foreign Keys

When referencing a model from another app, use string references:

```python
# Good — uses string reference
models.ForeignKey("bookings.Booking", on_delete=models.CASCADE)

# Good — uses settings.AUTH_USER_MODEL
models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
```

This avoids circular import issues and ensures Django resolves the reference
at migration time.

---

## 11. Emergency Reference

### Useful Commands

```bash
# Show all migration status
python manage.py showmigrations

# Check for pending migrations
python manage.py makemigrations --check

# Generate migrations for a specific app
python manage.py makemigrations <app_name>

# Apply all migrations
python manage.py migrate

# Apply migrations for a specific app
python manage.py migrate <app_name>

# Create a merge migration
python manage.py makemigrations --merge

# View the SQL a migration would generate
python manage.py sqlmigrate <app_name> <migration_number>
```
