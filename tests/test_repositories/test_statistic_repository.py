"""Тесты для StatisticsRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date

from app.database.repositories.statistic_repository import StatisticsRepository


class TestStatisticsRepository:
    """Тесты для StatisticsRepository."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Создать репозиторий с замоканной сессией."""
        with patch("app.database.repositories.statistic_repository.BaseRepository.__init__", return_value=None):
            repo = StatisticsRepository(mock_session)
            repo.session = mock_session
            repo.logger = MagicMock()
            return repo

    # ========== get_daily_bookings_count ==========

    @pytest.mark.asyncio
    async def test_get_daily_bookings_count(self, repo):
        """Количество бронирований за день."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_daily_bookings_count(date(2026, 4, 15))

        assert result == 5

    @pytest.mark.asyncio
    async def test_get_daily_bookings_count_zero(self, repo):
        """Ноль бронирований — scalar вернул None."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_daily_bookings_count(date(2026, 4, 15))

        assert result == 0

    @pytest.mark.asyncio
    async def test_get_daily_bookings_count_error(self, repo):
        """Ошибка — возвращает 0."""
        repo._execute_query = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.get_daily_bookings_count(date(2026, 4, 15))

        assert result == 0

    # ========== get_daily_revenue ==========

    @pytest.mark.asyncio
    async def test_get_daily_revenue(self, repo):
        """Выручка за день."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 15000
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_daily_revenue(date(2026, 4, 15))

        assert result == 15000

    @pytest.mark.asyncio
    async def test_get_daily_revenue_none(self, repo):
        """Выручка отсутствует."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_daily_revenue(date(2026, 4, 15))

        assert result == 0

    # ========== get_daily_new_users ==========

    @pytest.mark.asyncio
    async def test_get_daily_new_users(self, repo):
        """Новые пользователи за день."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_daily_new_users(date(2026, 4, 15))

        assert result == 3

    # ========== get_period_bookings_count ==========

    @pytest.mark.asyncio
    async def test_get_period_bookings_count(self, repo):
        """Количество бронирований за период."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 25
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_period_bookings_count(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == 25

    # ========== get_period_revenue ==========

    @pytest.mark.asyncio
    async def test_get_period_revenue(self, repo):
        """Выручка за период."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 75000
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_period_revenue(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == 75000

    # ========== get_period_new_users ==========

    @pytest.mark.asyncio
    async def test_get_period_new_users(self, repo):
        """Новые пользователи за период."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 12
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_period_new_users(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == 12

    # ========== get_period_total_people ==========

    @pytest.mark.asyncio
    async def test_get_period_total_people(self, repo):
        """Общее количество людей за период."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 50
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_period_total_people(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == 50

    # ========== get_period_completed_excursions ==========

    @pytest.mark.asyncio
    async def test_get_period_completed_excursions(self, repo):
        """Количество завершённых экскурсий."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 10
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_period_completed_excursions(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == 10

    # ========== get_popular_excursion ==========

    @pytest.mark.asyncio
    async def test_get_popular_excursion_found(self, repo):
        """Самая популярная экскурсия найдена."""
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(side_effect=lambda i: ["Морская прогулка", 15][i])
        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        repo._execute_query = AsyncMock(return_value=mock_result)

        name, count = await repo.get_popular_excursion(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert name == "Морская прогулка"
        assert count == 15

    @pytest.mark.asyncio
    async def test_get_popular_excursion_not_found(self, repo):
        """Нет данных — возвращает значения по умолчанию."""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        repo._execute_query = AsyncMock(return_value=mock_result)

        name, count = await repo.get_popular_excursion(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert name == "Нет данных"
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_popular_excursion_error(self, repo):
        """Ошибка — возвращает значения по умолчанию."""
        repo._execute_query = AsyncMock(side_effect=Exception("DB error"))

        name, count = await repo.get_popular_excursion(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert name == "Нет данных"
        assert count == 0

    # ========== get_cancelled_stats ==========

    @pytest.mark.asyncio
    async def test_get_cancelled_stats(self, repo):
        """Статистика отказов и неявок."""
        mock_result1 = MagicMock()
        mock_result1.scalar.return_value = 5
        mock_result2 = MagicMock()
        mock_result2.scalar.return_value = 15000
        mock_result3 = MagicMock()
        mock_result3.scalar.return_value = 2

        repo.session.execute.side_effect = [mock_result1, mock_result2, mock_result3]

        result = await repo.get_cancelled_stats(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == {
            'cancelled': 5,
            'refunds_amount': 15000,
            'not_arrived': 2
        }

    @pytest.mark.asyncio
    async def test_get_cancelled_stats_zeros(self, repo):
        """Статистика с нулями."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = None

        repo.session.execute.side_effect = [mock_result, mock_result, mock_result]

        result = await repo.get_cancelled_stats(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == {
            'cancelled': 0,
            'refunds_amount': 0,
            'not_arrived': 0
        }

    @pytest.mark.asyncio
    async def test_get_cancelled_stats_error(self, repo):
        """Ошибка — возвращает нули."""
        repo.session.execute.side_effect = Exception("DB error")

        result = await repo.get_cancelled_stats(
            datetime(2026, 4, 1),
            datetime(2026, 4, 30)
        )

        assert result == {
            'cancelled': 0,
            'refunds_amount': 0,
            'not_arrived': 0
        }