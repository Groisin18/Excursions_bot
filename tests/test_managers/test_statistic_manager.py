"""Тесты для StatisticsManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, date

from app.database.managers.statistic_manager import StatisticsManager
from app.database.models import BookingStatus


class TestStatisticsManager:
    """Тесты для StatisticsManager."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        session = AsyncMock()
        session.execute = AsyncMock()
        return session

    @pytest.fixture
    def manager(self, mock_session):
        """Создать менеджер с замоканными зависимостями."""
        with patch("app.database.managers.statistic_manager.BaseManager.__init__", return_value=None):
            manager = StatisticsManager(mock_session)
            manager.session = mock_session
            manager.logger = MagicMock()
            manager.stats_repo = AsyncMock()
            return manager

    # ========== get_daily_stats ==========

    @pytest.mark.asyncio
    async def test_get_daily_stats_success(self, manager):
        """Успешное получение дневной статистики."""
        manager.stats_repo.get_daily_bookings_count.return_value = 5
        manager.stats_repo.get_daily_revenue.return_value = 15000
        manager.stats_repo.get_daily_new_users.return_value = 3

        result = await manager.get_daily_stats(datetime.now())

        assert result['total_bookings'] == 5
        assert result['total_revenue'] == 15000
        assert result['new_users'] == 3

    @pytest.mark.asyncio
    async def test_get_daily_stats_error(self, manager):
        """Ошибка при получении дневной статистики."""
        manager.stats_repo.get_daily_bookings_count.side_effect = Exception("Error")

        result = await manager.get_daily_stats(datetime.now())

        assert result['total_bookings'] == 0
        assert result['total_revenue'] == 0
        assert result['new_users'] == 0

    # ========== get_period_stats ==========

    @pytest.mark.asyncio
    async def test_get_period_stats_success(self, manager):
        """Успешное получение статистики за период."""
        manager.stats_repo.get_period_bookings_count.return_value = 10
        manager.stats_repo.get_period_revenue.return_value = 50000
        manager.stats_repo.get_period_new_users.return_value = 7
        manager.stats_repo.get_period_completed_excursions.return_value = 3
        manager.stats_repo.get_period_total_people.return_value = 25
        manager.stats_repo.get_popular_excursion.return_value = ("Морская прогулка", 8)

        result = await manager.get_period_stats(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['total_bookings'] == 10
        assert result['total_revenue'] == 50000
        assert result['popular_excursion'] == "Морская прогулка"
        assert result['avg_check'] == 5000.0

    @pytest.mark.asyncio
    async def test_get_period_stats_avg_check_zero_bookings(self, manager):
        """Средний чек при 0 бронирований."""
        manager.stats_repo.get_period_bookings_count.return_value = 0
        manager.stats_repo.get_period_revenue.return_value = 0
        manager.stats_repo.get_period_new_users.return_value = 0
        manager.stats_repo.get_period_completed_excursions.return_value = 0
        manager.stats_repo.get_period_total_people.return_value = 0
        manager.stats_repo.get_popular_excursion.return_value = ("Нет данных", 0)

        result = await manager.get_period_stats(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['avg_check'] == 0

    @pytest.mark.asyncio
    async def test_get_period_stats_error(self, manager):
        """Ошибка при получении статистики за период."""
        manager.stats_repo.get_period_bookings_count.side_effect = Exception("Error")

        result = await manager.get_period_stats(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['total_bookings'] == 0
        assert result['popular_excursion'] == 'Нет данных'

    # ========== get_active_excursions_count ==========

    @pytest.mark.asyncio
    async def test_get_active_excursions_count(self, manager):
        """Количество активных экскурсий."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 4
        manager._execute_query = AsyncMock(return_value=mock_result)

        result = await manager.get_active_excursions_count()

        assert result == 4

    @pytest.mark.asyncio
    async def test_get_active_excursions_count_error(self, manager):
        """Ошибка при получении количества."""
        manager._execute_query = AsyncMock(side_effect=Exception("Error"))

        result = await manager.get_active_excursions_count()

        assert result == 0

    # ========== get_urgent_bookings_info ==========

    @pytest.mark.asyncio
    async def test_get_urgent_bookings_info(self, manager):
        """Срочные бронирования."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 3
        manager.session.execute.return_value = mock_result

        result = await manager.get_urgent_bookings_info()

        assert result == 3

    @pytest.mark.asyncio
    async def test_get_urgent_bookings_info_error(self, manager):
        """Ошибка при получении срочных бронирований."""
        manager.session.execute.side_effect = Exception("Error")

        result = await manager.get_urgent_bookings_info()

        assert result == 0

    # ========== get_captains_without_slots ==========

    @pytest.mark.asyncio
    async def test_get_captains_without_slots(self, manager):
        """Капитаны без слотов."""
        mock_result = MagicMock()
        mock_result.scalar.return_value = 2
        manager.session.execute.return_value = mock_result

        result = await manager.get_captains_without_slots()

        assert result == 2

    # ========== get_cancelled_stats ==========

    @pytest.mark.asyncio
    async def test_get_cancelled_stats_success(self, manager):
        """Статистика отказов."""
        manager.stats_repo.get_cancelled_stats.return_value = {
            'cancelled': 5, 'refunds_amount': 15000, 'not_arrived': 2
        }

        result = await manager.get_cancelled_stats(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['cancelled'] == 5
        assert result['not_arrived'] == 2

    @pytest.mark.asyncio
    async def test_get_cancelled_stats_error(self, manager):
        """Ошибка при получении статистики отказов."""
        manager.stats_repo.get_cancelled_stats.side_effect = Exception("Error")

        result = await manager.get_cancelled_stats(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['cancelled'] == 0

    # ========== get_single_excursion_stats ==========

    @pytest.mark.asyncio
    async def test_get_single_excursion_stats_success(self, manager):
        """Статистика по одной экскурсии."""
        mock_row = MagicMock()
        mock_row.total_bookings = 10
        mock_row.total_people = 15
        mock_row.total_revenue = 50000

        mock_result = MagicMock()
        mock_result.first.return_value = mock_row
        manager.session.execute.return_value = mock_result

        result = await manager.get_single_excursion_stats(
            1, datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['total_bookings'] == 10
        assert result['total_people'] == 15
        assert result['total_revenue'] == 50000

    @pytest.mark.asyncio
    async def test_get_single_excursion_stats_error(self, manager):
        """Ошибка при получении статистики по экскурсии."""
        manager.session.execute.side_effect = Exception("Error")

        result = await manager.get_single_excursion_stats(
            1, datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert result['total_bookings'] == 0

    # ========== generate_period_report ==========

    @pytest.mark.asyncio
    async def test_generate_period_report_success(self, manager):
        """Генерация отчёта."""
        manager.stats_repo.get_period_bookings_count.return_value = 10
        manager.stats_repo.get_period_revenue.return_value = 50000
        manager.stats_repo.get_period_new_users.return_value = 5
        manager.stats_repo.get_period_completed_excursions.return_value = 3
        manager.stats_repo.get_period_total_people.return_value = 20
        manager.stats_repo.get_popular_excursion.return_value = ("Морская прогулка", 7)

        result = await manager.generate_period_report(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert "ОТЧЕТ" in result
        assert "Морская прогулка" in result
        assert "10" in result
        assert "50000" in result

    @pytest.mark.asyncio
    async def test_generate_period_report_error(self, manager):
        """Ошибка при генерации отчёта."""
        manager.get_period_stats = AsyncMock(side_effect=Exception("Error"))

        result = await manager.generate_period_report(
            datetime(2026, 4, 1), datetime(2026, 4, 30)
        )

        assert "Ошибка" in result

    # ========== get_daily_excursions_stats ==========

    @pytest.mark.asyncio
    async def test_get_daily_excursions_stats(self, manager):
        """Статистика по экскурсиям за день."""
        mock_row = MagicMock()
        mock_query = MagicMock()
        mock_query.all.return_value = [mock_row]
        manager.session.execute.return_value = mock_query

        result = await manager.get_daily_excursions_stats(datetime.now())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_daily_excursions_stats_error(self, manager):
        """Ошибка при получении статистики по экскурсиям."""
        manager.session.execute.side_effect = Exception("Error")

        result = await manager.get_daily_excursions_stats(datetime.now())

        assert result == []

    # ========== get_daily_captains_stats ==========

    @pytest.mark.asyncio
    async def test_get_daily_captains_stats(self, manager):
        """Статистика по капитанам за день."""
        mock_row = MagicMock()
        mock_query = MagicMock()
        mock_query.all.return_value = [mock_row]
        manager.session.execute.return_value = mock_query

        result = await manager.get_daily_captains_stats(datetime.now())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_daily_captains_stats_error(self, manager):
        """Ошибка при получении статистики по капитанам."""
        manager.session.execute.side_effect = Exception("Error")

        result = await manager.get_daily_captains_stats(datetime.now())

        assert result == []

    # ========== get_captains_with_stats ==========

    @pytest.mark.asyncio
    async def test_get_captains_with_stats_no_captains(self, manager):
        """Нет капитанов."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        manager.session.execute.return_value = mock_result

        result = await manager.get_captains_with_stats()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_captains_with_stats_success(self, manager):
        """Успешное получение статистики по капитанам."""
        captain = MagicMock()
        captain.id = 1
        captain.full_name = "Иван"

        mock_captains_result = MagicMock()
        mock_captains_result.scalars.return_value.all.return_value = [captain]

        mock_total_slots = MagicMock()
        mock_total_slots.scalar.return_value = 5

        mock_row = MagicMock()
        mock_row.conducted_slots = 3
        mock_row.total_people = 12
        mock_row.total_revenue = 36000

        mock_stats_result = MagicMock()
        mock_stats_result.first.return_value = mock_row

        # Первый вызов - капитаны, второй - total_slots, третий - stats
        manager.session.execute.side_effect = [
            mock_captains_result,
            mock_total_slots,
            mock_stats_result
        ]

        result = await manager.get_captains_with_stats()

        assert len(result) == 1
        assert result[0]['stats']['total_slots'] == 5
        assert result[0]['stats']['conducted_slots'] == 3
        assert result[0]['stats']['not_conducted_slots'] == 2
        assert result[0]['stats']['total_people'] == 12
        assert result[0]['stats']['total_revenue'] == 36000