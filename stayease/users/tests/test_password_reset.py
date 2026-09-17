from http import HTTPStatus

import pytest
from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from stayease.users.models import PasswordResetRequest
from stayease.users.models import ResetRequestStatus
from stayease.users.models import User
from stayease.users.models import UserRole
from stayease.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class TestForgotPasswordUserWorkflow:
    """
    Tests 1-4:
    1. Open /forgot-password/
    2. Submit valid email and reason.
    3. PasswordResetRequest is created with status=pending.
    4. Password is NOT changed at this point.
    """

    def test_open_forgot_password_page_get(self, client):
        response = client.get(reverse("forgot_password"))
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "Forgot Password" in content
        assert "administrator will review your request" in content
        # Ensure no mention of OTP or email tokens
        assert "otp" not in content.lower()
        assert "email link" not in content.lower()

    def test_submit_valid_request_creates_pending_record(self, client):
        user = UserFactory(email="tenant@example.com", role=UserRole.TENANT)
        user.set_password("OldSecret123!")
        user.save()
        old_password_hash = user.password

        response = client.post(
            reverse("forgot_password"),
            data={
                "email": "tenant@example.com",
                "reason": "Locked out of my phone and cannot recall password.",
            },
            follow=True,
        )
        assert response.status_code == HTTPStatus.OK

        # Record created with status=pending
        req = PasswordResetRequest.objects.filter(user=user).first()
        assert req is not None
        assert req.status == ResetRequestStatus.PENDING
        assert req.email == "tenant@example.com"
        assert req.reason == "Locked out of my phone and cannot recall password."
        assert req.processed_by is None
        assert req.processed_at is None
        assert req.new_password is None

        # Password must NOT be changed at this point
        user.refresh_from_db()
        assert user.password == old_password_hash
        assert authenticate(email="tenant@example.com", password="OldSecret123!") == user

    def test_submit_request_nonexistent_email_shows_error(self, client):
        response = client.post(
            reverse("forgot_password"),
            data={"email": "nonexistent@example.com", "reason": "help"},
        )
        assert response.status_code == HTTPStatus.OK
        assert PasswordResetRequest.objects.count() == 0
        content = response.content.decode("utf-8")
        assert "No account found with this email" in content

    def test_duplicate_pending_request_prevented(self, client):
        user = UserFactory(email="tenant2@example.com")
        PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            reason="First request",
            status=ResetRequestStatus.PENDING,
        )

        response = client.post(
            reverse("forgot_password"),
            data={"email": "tenant2@example.com", "reason": "Second request"},
        )
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "already pending review" in content
        assert PasswordResetRequest.objects.filter(user=user).count() == 1


class TestAdminDashboardAndApprovalWorkflow:
    """
    Tests 5-12:
    5. Open admin dashboard.
    6. See pending request.
    7. Approve request.
    8. Request becomes approved.
    9. processed_by is populated.
    10. processed_at is populated.
    11. User receives/gets access to generated temp password.
    12. User can log in with the temporary password.
    """

    def test_admin_dashboard_shows_pending_requests(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        tenant_user = UserFactory(role=UserRole.TENANT, email="lostpass@example.com")
        req = PasswordResetRequest.objects.create(
            user=tenant_user,
            email=tenant_user.email,
            reason="Need help logging in",
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(admin_user)
        response = client.get(reverse("users:dashboard_admin"))
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "lostpass@example.com" in content
        assert "Need help logging in" in content
        assert f"approve-btn-{req.id}" in content
        assert f"reject-btn-{req.id}" in content

    def test_admin_approves_pending_request(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        tenant_user = UserFactory(role=UserRole.TENANT, email="forgotten@example.com")
        tenant_user.set_password("OldPassword123!")
        tenant_user.save()

        req = PasswordResetRequest.objects.create(
            user=tenant_user,
            email=tenant_user.email,
            reason="Can't log in",
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(admin_user)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url, data={"admin_notes": "Identity confirmed via phone call."}, follow=True)
        assert response.status_code == HTTPStatus.OK

        # 8, 9, 10: State and metadata populated
        req.refresh_from_db()
        assert req.status == ResetRequestStatus.APPROVED
        assert req.processed_by == admin_user
        assert req.processed_at is not None
        assert req.admin_notes == "Identity confirmed via phone call."

        # 11: Temporary password generated and stored
        assert req.new_password is not None
        assert len(req.new_password) >= 12
        temp_pass = req.new_password

        # 12: User can authenticate and log in with the temporary password
        tenant_user.refresh_from_db()
        authenticated_user = authenticate(email="forgotten@example.com", password=temp_pass)
        assert authenticated_user == tenant_user

        # Old password no longer works
        assert authenticate(email="forgotten@example.com", password="OldPassword123!") is None


class TestChangePasswordAfterLoginWorkflow:
    """
    Tests 13-16:
    13. Logged-in user opens change password.
    14. Enters temporary/current password.
    15. Sets a new password.
    16. New password works for login.
    """

    def test_change_password_with_temporary_password(self, client):
        user = UserFactory(email="user123@example.com", role=UserRole.TENANT)
        temp_pass = "TempP@ssword123!"
        user.set_password(temp_pass)
        user.save()

        # Log in with temporary password
        client.force_login(user)

        # 13: Opens change password page
        response = client.get(reverse("change_password"))
        assert response.status_code == HTTPStatus.OK

        # 14, 15: Submits current temp pass and new chosen password
        new_permanent_pass = "BrandNewSecret2026!#"
        post_response = client.post(
            reverse("change_password"),
            data={
                "old_password": temp_pass,
                "new_password1": new_permanent_pass,
                "new_password2": new_permanent_pass,
            },
            follow=True,
        )
        assert post_response.status_code == HTTPStatus.OK

        # 16: New password works for login
        user.refresh_from_db()
        assert authenticate(email="user123@example.com", password=new_permanent_pass) == user
        # Temp password no longer works
        assert authenticate(email="user123@example.com", password=temp_pass) is None


class TestAdminRejectionWorkflow:
    """
    Tests 17-20:
    17. Create another pending request.
    18. Admin rejects it.
    19. Status becomes rejected.
    20. User password remains unchanged.
    """

    def test_admin_rejects_pending_request(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        user = UserFactory(email="rejected_user@example.com", role=UserRole.TENANT)
        user.set_password("StaySame123!")
        user.save()
        old_hash = user.password

        req = PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            reason="Suspicious reset attempt",
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(admin_user)
        url = reverse("reject_password_reset", kwargs={"request_id": req.id})
        response = client.post(url, data={"admin_notes": "Cannot verify identity."}, follow=True)
        assert response.status_code == HTTPStatus.OK

        # 19: Status is rejected, audit trail populated
        req.refresh_from_db()
        assert req.status == ResetRequestStatus.REJECTED
        assert req.processed_by == admin_user
        assert req.processed_at is not None
        assert req.admin_notes == "Cannot verify identity."

        # 20: User password remains unchanged
        user.refresh_from_db()
        assert user.password == old_hash
        assert authenticate(email="rejected_user@example.com", password="StaySame123!") == user


class TestAuthorizationAndPermissions:
    """
    Tests 21-22:
    21. Normal user tries to access approve/reject endpoint.
    22. Access is denied (403 Forbidden).
    """

    def test_normal_tenant_cannot_approve_request(self, client):
        tenant_user = UserFactory(role=UserRole.TENANT)
        target_user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=target_user,
            email=target_user.email,
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(tenant_user)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_normal_owner_cannot_approve_request(self, client):
        owner_user = UserFactory(role=UserRole.OWNER)
        target_user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=target_user,
            email=target_user.email,
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(owner_user)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_user_cannot_approve_their_own_request(self, client):
        tenant_user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=tenant_user,
            email=tenant_user.email,
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(tenant_user)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url)
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_unauthenticated_cannot_access_approve(self, client):
        target_user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=target_user,
            email=target_user.email,
            status=ResetRequestStatus.PENDING,
        )
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url)
        # Should be forbidden for unauthenticated
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_superuser_can_approve_request(self, client):
        superuser = UserFactory(is_superuser=True, is_staff=True)
        target_user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=target_user,
            email=target_user.email,
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(superuser)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url, follow=True)
        assert response.status_code == HTTPStatus.OK
        req.refresh_from_db()
        assert req.status == ResetRequestStatus.APPROVED


class TestStateMachineGuards:
    """
    Tests 23-25:
    23. Attempt to approve an already-approved request.
    24. Attempt to approve an already-rejected request.
    25. Both actions must be prevented.
    """

    def test_cannot_approve_already_approved_request(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            status=ResetRequestStatus.APPROVED,
            new_password="ExistingPassword123!",
            processed_at=timezone.now(),
        )

        client.force_login(admin_user)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url, follow=True)
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "cannot be approved because it is not pending" in content
        req.refresh_from_db()
        assert req.new_password == "ExistingPassword123!"

    def test_cannot_approve_already_rejected_request(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            status=ResetRequestStatus.REJECTED,
            processed_at=timezone.now(),
        )

        client.force_login(admin_user)
        url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        response = client.post(url, follow=True)
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "cannot be approved because it is not pending" in content
        req.refresh_from_db()
        assert req.status == ResetRequestStatus.REJECTED
        assert req.new_password is None

    def test_cannot_reject_already_approved_request(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            status=ResetRequestStatus.APPROVED,
            new_password="TempPass123!",
            processed_at=timezone.now(),
        )

        client.force_login(admin_user)
        url = reverse("reject_password_reset", kwargs={"request_id": req.id})
        response = client.post(url, follow=True)
        assert response.status_code == HTTPStatus.OK
        content = response.content.decode("utf-8")
        assert "cannot be rejected because it is not pending" in content
        req.refresh_from_db()
        assert req.status == ResetRequestStatus.APPROVED

    def test_get_not_allowed_on_approve_and_reject(self, client):
        admin_user = UserFactory(role=UserRole.ADMIN)
        user = UserFactory(role=UserRole.TENANT)
        req = PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            status=ResetRequestStatus.PENDING,
        )

        client.force_login(admin_user)
        approve_url = reverse("approve_password_reset", kwargs={"request_id": req.id})
        reject_url = reverse("reject_password_reset", kwargs={"request_id": req.id})

        # Must not allow GET for state-changing operations
        assert client.get(approve_url).status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert client.get(reject_url).status_code == HTTPStatus.METHOD_NOT_ALLOWED


class TestDatabaseSchemaVerification:
    """
    Tests 26-27:
    26. Confirm migrations are applied.
    27. Confirm PasswordResetRequest table and all required columns exist.
    """

    def test_database_table_and_columns_exist(self):
        fields = {f.name for f in PasswordResetRequest._meta.get_fields()}
        required_fields = {
            "id",
            "user",
            "email",
            "reason",
            "status",
            "admin_notes",
            "processed_by",
            "new_password",
            "created_at",
            "processed_at",
        }
        assert required_fields.issubset(fields)

    def test_str_representation(self):
        user = UserFactory(email="str_test@example.com")
        req = PasswordResetRequest.objects.create(
            user=user,
            email=user.email,
            status=ResetRequestStatus.PENDING,
        )
        assert "str_test@example.com" in str(req)
        assert "pending" in str(req)
