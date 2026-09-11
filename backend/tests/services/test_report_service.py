"""Tests for report service."""

import logging
import os
from typing import Any

from app.api.schemas.report import EntityType, ReportCreate, ReportReason
from app.api.services.report_service import ReportService
from app.db.dynamo.build_lists import BuildList, BuildListRepository
from app.db.dynamo.catalog import Part
from app.db.dynamo.moderation import ReportRepository
from app.db.dynamo.users import User, UserRepository
from tests.conftest import save_catalog


def get_unique_name(base_name: str) -> str:
    """Generate a unique name for parallel testing."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    pid = os.getpid()
    return f"{base_name}_{worker_id}_{pid}"


class TestReportService:
    """Test cases for report service."""

    def test_create_report_build_list(self, db_session: Any, test_user: User) -> None:
        """Test creating a report for a build list."""
        # Create another user and their build list

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user"),
                email=f"{get_unique_name('other_user')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list"),
                description="Test build list",
                user_id=other_user.id,
            )
        )

        # Create report
        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.SPAM, description="This is spam")
        report = service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)

        assert report.entity_type == "build_list"
        assert report.entity_id == build_list.id
        assert report.user_id == test_user.id
        assert report.reason == "spam"
        assert report.status == "pending"

    def test_create_report_part(self, db_session: Any, test_user: User) -> None:
        """Test creating a report for a global part."""
        # Create another user and their global part
        from app.db.dynamo.catalog import Category, CategoryRepository

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user2"),
                email=f"{get_unique_name('other_user2')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        # Get or create a category
        category = next(iter(CategoryRepository().list_all()), None)
        if not category:
            category = Category(
                name="test_category",
                display_name="Test Category",
                description="A test category",
                is_active=True,
                sort_order=1,
            )
            category = save_catalog(category)

        # Get or create a part_manufacturer
        from app.db.dynamo.catalog import PartManufacturer, PartManufacturerRepository

        part_manufacturer = next(iter(PartManufacturerRepository().list_all()), None)
        if not part_manufacturer:
            part_manufacturer = PartManufacturer(
                name="test_part_manufacturer",
                description="Test part_manufacturer",
                is_active=True,
            )
            part_manufacturer = save_catalog(part_manufacturer)

        part = Part(
            name=get_unique_name("test_part"),
            description="Test part",
            user_id=other_user.id,
            category_id=category.id,
            part_manufacturer_id=part_manufacturer.id,
        )
        part = save_catalog(part)

        # Create report
        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.INAPPROPRIATE_CONTENT, description="Inappropriate")
        report = service.create_report(EntityType.PART, part.id, test_user.id, report_data, logger)

        assert report.entity_type == "part"
        assert report.entity_id == part.id
        assert report.user_id == test_user.id
        assert report.reason == "inappropriate_content"
        assert report.status == "pending"

    def test_create_report_own_entity(self, db_session: Any, test_user: User) -> None:
        """Test that users cannot report their own entities."""
        # Create build list owned by test_user
        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("own_build_list"),
                description="Test",
                user_id=test_user.id,
            )
        )

        # Try to create report
        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.SPAM)

        from fastapi import HTTPException

        try:
            service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert "cannot report your own" in e.detail.lower()

    def test_create_report_duplicate(self, db_session: Any, test_user: User) -> None:
        """Test that users cannot create duplicate pending reports."""
        # Create another user and their build list

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user3"),
                email=f"{get_unique_name('other_user3')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list2"),
                description="Test",
                user_id=other_user.id,
            )
        )

        # Create first report
        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.SPAM)
        service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)

        # Try to create duplicate report
        from fastapi import HTTPException

        try:
            service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 400
            assert "already reported" in e.detail.lower()

    def test_get_reports_no_filters(self, db_session: Any, test_user: User) -> None:
        """Test getting reports with no filters."""
        # Create reports

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user4"),
                email=f"{get_unique_name('other_user4')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list3"),
                description="Test",
                user_id=other_user.id,
            )
        )

        # Create reports - create for different entities to avoid duplicate report error
        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data1 = ReportCreate(reason=ReportReason.SPAM)
        report_data2 = ReportCreate(reason=ReportReason.INAPPROPRIATE_CONTENT)
        service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data1, logger)

        # Create a second build list for the second report to avoid duplicate report error
        build_list2 = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list4"),
                description="Test 2",
                user_id=other_user.id,
            )
        )
        service.create_report(EntityType.BUILD_LIST, build_list2.id, test_user.id, report_data2, logger)

        # Get reports
        reports = service.get_reports()
        assert isinstance(reports, list)
        assert len(reports) >= 2

    def test_get_reports_with_filters(self, db_session: Any, test_user: User) -> None:
        """Test getting reports with filters."""
        # Create reports
        from app.db.dynamo.catalog import Category, CategoryRepository

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user5"),
                email=f"{get_unique_name('other_user5')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list4"),
                description="Test",
                user_id=other_user.id,
            )
        )

        # Get or create a category
        category = next(iter(CategoryRepository().list_all()), None)
        if not category:
            category = Category(
                name="test_category2",
                display_name="Test Category 2",
                description="A test category",
                is_active=True,
                sort_order=1,
            )
            category = save_catalog(category)

        # Get or create a part_manufacturer
        from app.db.dynamo.catalog import PartManufacturer, PartManufacturerRepository

        part_manufacturer = next(iter(PartManufacturerRepository().list_all()), None)
        if not part_manufacturer:
            part_manufacturer = PartManufacturer(
                name="test_part_manufacturer2",
                description="Test part_manufacturer 2",
                is_active=True,
            )
            part_manufacturer = save_catalog(part_manufacturer)

        part = Part(
            name=get_unique_name("test_part2"),
            description="Test part",
            user_id=other_user.id,
            category_id=category.id,
            part_manufacturer_id=part_manufacturer.id,
        )
        part = save_catalog(part)

        # Create reports
        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data1 = ReportCreate(reason=ReportReason.SPAM)
        report_data2 = ReportCreate(reason=ReportReason.INAPPROPRIATE_CONTENT)
        service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data1, logger)
        service.create_report(EntityType.PART, part.id, test_user.id, report_data2, logger)

        # Get reports filtered by entity type
        reports = service.get_reports(entity_type=EntityType.BUILD_LIST)
        assert isinstance(reports, list)
        assert all(r.entity_type == "build_list" for r in reports)

        # Get reports filtered by status
        reports = service.get_reports(status="pending")
        assert isinstance(reports, list)
        assert all(r.status == "pending" for r in reports)

    def test_update_report(self, db_session: Any, test_user: User) -> None:
        """Test updating a report."""
        # Create report

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user6"),
                email=f"{get_unique_name('other_user6')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list5"),
                description="Test",
                user_id=other_user.id,
            )
        )

        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.SPAM)
        report = service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)

        # Update report
        updated_report = service.update_report(
            report.id,
            "reviewed",
            admin_notes="Reviewed and dismissed",
            reviewer_id=test_user.id,
            logger=logger,
        )

        assert updated_report.status == "reviewed"
        assert updated_report.admin_notes == "Reviewed and dismissed"
        assert updated_report.reviewed_by == test_user.id
        assert updated_report.reviewed_at is not None

    def test_delete_report(self, db_session: Any, test_user: User) -> None:
        """Test deleting a report."""
        # Create report

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user7"),
                email=f"{get_unique_name('other_user7')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list6"),
                description="Test",
                user_id=other_user.id,
            )
        )

        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.SPAM)
        report = service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)

        # Delete report
        service.delete_report(report.id, logger)

        # Verify report is deleted
        result = ReportRepository().get(report.id)
        assert result is None

    def test_get_reports_with_details(self, db_session: Any, test_user: User) -> None:
        """Test getting reports with details."""
        # Create report

        other_user = UserRepository().create_user(
            User(
                username=get_unique_name("other_user8"),
                email=f"{get_unique_name('other_user8')}@example.com",
                email_verified=True,
                disabled=False,
            )
        )

        build_list = BuildListRepository().create(
            BuildList(
                name=get_unique_name("test_build_list7"),
                description="Test build list description",
                user_id=other_user.id,
            )
        )

        service = ReportService()
        logger = logging.getLogger(__name__)
        report_data = ReportCreate(reason=ReportReason.SPAM, description="Test report")
        service.create_report(EntityType.BUILD_LIST, build_list.id, test_user.id, report_data, logger)

        # Get reports with details
        reports, total_count = service.get_reports_with_details()
        assert isinstance(reports, list)
        assert total_count >= 1
        assert len(reports) >= 1

        # Check that details are included
        report_with_details = next((r for r in reports if r.entity_id == build_list.id), None)
        assert report_with_details is not None
        assert report_with_details.reporter_username == test_user.username
        assert report_with_details.entity_name == build_list.name
        assert report_with_details.entity_description == build_list.description
