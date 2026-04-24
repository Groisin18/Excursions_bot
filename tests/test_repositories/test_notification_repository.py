"""Тесты для NotificationRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.repositories.notification_repository import NotificationRepository
from app.database.models import NotificationStatus, UserRole


class TestNotificationRepository:
    """Тесты для NotificationRepository."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Создать репозиторий с замоканной сессией."""
        with patch("app.database.repositories.notification_repository.BaseRepository.__init__", return_value=None):
            repo = NotificationRepository(mock_session)
            repo.session = mock_session
            repo.logger = MagicMock()
            return repo

    # ========== create_notification ==========

    @pytest.mark.asyncio
    async def test_create_notification_success(self, repo):
        """Успешное создание рассылки."""
        mock_notification = MagicMock()
        mock_notification.id = 1
        repo._create = AsyncMock(return_value=mock_notification)

        result = await repo.create_notification(
            message="Тестовое сообщение",
            audience_type=UserRole.client,
            created_by_id=5
        )

        assert result is mock_notification
        repo._create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_notification_error(self, repo):
        """Ошибка при создании рассылки."""
        repo._create = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(Exception, match="DB error"):
            await repo.create_notification(
                message="Тест",
                audience_type=UserRole.client,
                created_by_id=5
            )

    # ========== update_notification_stats ==========

    @pytest.mark.asyncio
    async def test_update_notification_stats_success(self, repo):
        """Успешное обновление статистики."""
        repo._update = AsyncMock(return_value=1)

        result = await repo.update_notification_stats(
            notification_id=1,
            sent_count=10,
            failed_count=2,
            total_recipients=100
        )

        assert result is True
        repo._update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_notification_stats_no_total(self, repo):
        """Обновление статистики без total_recipients."""
        repo._update = AsyncMock(return_value=1)

        result = await repo.update_notification_stats(
            notification_id=1,
            sent_count=5,
            failed_count=0
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_update_notification_stats_zero_updated(self, repo):
        """Ничего не обновлено — возвращает False."""
        repo._update = AsyncMock(return_value=0)

        result = await repo.update_notification_stats(
            notification_id=999,
            sent_count=0,
            failed_count=0
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_notification_stats_error(self, repo):
        """Ошибка при обновлении статистики."""
        repo._update = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.update_notification_stats(
            notification_id=1,
            sent_count=1,
            failed_count=0
        )

        assert result is False

    # ========== update_notification_status ==========

    @pytest.mark.asyncio
    async def test_update_notification_status_to_completed(self, repo):
        """Обновление статуса на COMPLETED — добавляет completed_at."""
        repo._update = AsyncMock(return_value=1)

        result = await repo.update_notification_status(
            notification_id=1,
            status=NotificationStatus.COMPLETED
        )

        assert result is True
        call_kwargs = repo._update.call_args[1]
        assert call_kwargs.get('completed_at') is not None

    @pytest.mark.asyncio
    async def test_update_notification_status_to_in_progress(self, repo):
        """Обновление статуса на IN_PROGRESS — без completed_at."""
        repo._update = AsyncMock(return_value=1)

        result = await repo.update_notification_status(
            notification_id=1,
            status=NotificationStatus.IN_PROGRESS
        )

        assert result is True
        call_kwargs = repo._update.call_args[1]
        assert 'completed_at' not in call_kwargs

    @pytest.mark.asyncio
    async def test_update_notification_status_not_found(self, repo):
        """Рассылка не найдена — возвращает False."""
        repo._update = AsyncMock(return_value=0)

        result = await repo.update_notification_status(
            notification_id=999,
            status=NotificationStatus.COMPLETED
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_notification_status_error(self, repo):
        """Ошибка при обновлении статуса."""
        repo._update = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.update_notification_status(
            notification_id=1,
            status=NotificationStatus.FAILED
        )

        assert result is False

    # ========== get_notification_by_id ==========

    @pytest.mark.asyncio
    async def test_get_notification_by_id_found(self, repo):
        """Рассылка найдена."""
        mock_notification = MagicMock()
        repo._get_one = AsyncMock(return_value=mock_notification)

        result = await repo.get_notification_by_id(1)

        assert result is mock_notification

    @pytest.mark.asyncio
    async def test_get_notification_by_id_not_found(self, repo):
        """Рассылка не найдена."""
        repo._get_one = AsyncMock(return_value=None)

        result = await repo.get_notification_by_id(999)

        assert result is None

    # ========== get_notifications ==========

    @pytest.mark.asyncio
    async def test_get_notifications_all(self, repo):
        """Получить все рассылки."""
        mock_notifications = [MagicMock(), MagicMock()]
        repo._get_many = AsyncMock(return_value=mock_notifications)

        result = await repo.get_notifications()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_notifications_filtered(self, repo):
        """Получить рассылки с фильтрацией."""
        mock_notifications = [MagicMock()]
        repo._get_many = AsyncMock(return_value=mock_notifications)

        result = await repo.get_notifications(
            status=NotificationStatus.PENDING,
            audience_type=UserRole.client,
            limit=10
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_notifications_error(self, repo):
        """Ошибка при получении рассылок."""
        repo._get_many = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.get_notifications()

        assert result == []

    # ========== get_pending_notifications ==========

    @pytest.mark.asyncio
    async def test_get_pending_notifications(self, repo):
        """Получить ожидающие рассылки."""
        mock_notifications = [MagicMock()]
        repo.get_notifications = AsyncMock(return_value=mock_notifications)

        result = await repo.get_pending_notifications()

        assert len(result) == 1
        repo.get_notifications.assert_called_once_with(status=NotificationStatus.PENDING)

    # ========== get_recipients_by_audience ==========

    @pytest.mark.asyncio
    async def test_get_recipients_clients(self, repo):
        """Получить получателей-клиентов."""
        mock_users = [MagicMock(), MagicMock(), MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_users
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_recipients_by_audience(UserRole.client)

        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_get_recipients_captains(self, repo):
        """Получить получателей-капитанов."""
        mock_users = [MagicMock()]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_users
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_recipients_by_audience(UserRole.captain)

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_recipients_invalid_audience(self, repo):
        """Некорректный тип аудитории — возвращает пустой список."""
        result = await repo.get_recipients_by_audience(UserRole.admin)

        assert result == []

    @pytest.mark.asyncio
    async def test_get_recipients_error(self, repo):
        """Ошибка при получении получателей."""
        repo._execute_query = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.get_recipients_by_audience(UserRole.client)

        assert result == []

    # ========== cancel_notification ==========

    @pytest.mark.asyncio
    async def test_cancel_pending_notification(self, repo):
        """Отмена ожидающей рассылки."""
        mock_notification = MagicMock()
        mock_notification.status = NotificationStatus.PENDING
        repo.get_notification_by_id = AsyncMock(return_value=mock_notification)
        repo.update_notification_status = AsyncMock(return_value=True)

        result = await repo.cancel_notification(1)

        assert result is True
        repo.update_notification_status.assert_called_once_with(1, NotificationStatus.CANCELLED)

    @pytest.mark.asyncio
    async def test_cancel_non_pending_notification(self, repo):
        """Отмена не-PENDING рассылки — возвращает False."""
        mock_notification = MagicMock()
        mock_notification.status = NotificationStatus.IN_PROGRESS
        repo.get_notification_by_id = AsyncMock(return_value=mock_notification)
        repo.update_notification_status = AsyncMock()

        result = await repo.cancel_notification(1)

        assert result is False
        repo.update_notification_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_cancel_not_found_notification(self, repo):
        """Отмена несуществующей рассылки."""
        repo.get_notification_by_id = AsyncMock(return_value=None)

        result = await repo.cancel_notification(999)

        assert result is False