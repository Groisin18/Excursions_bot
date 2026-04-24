"""Тесты для роутера статистики администратора."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta


# ========== ТЕСТЫ: dashboard_handler ==========

@pytest.mark.asyncio
async def test_dashboard_handler_success(telegram_message_mock):
    """Тест успешного отображения дашборда."""
    from app.routers.admin.statistic import dashboard_handler

    telegram_message_mock.text = "/dashboard"

    mock_stats = AsyncMock()
    mock_stats.get_daily_stats.return_value = {
        'total_bookings': 1, 'total_revenue': 15000, 'new_users': 3
    }
    mock_stats.get_active_excursions_count.return_value = 4
    mock_stats.get_urgent_bookings_info.return_value = 7
    mock_stats.get_captains_without_slots.return_value = 5

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await dashboard_handler(telegram_message_mock)

    telegram_message_mock.answer.assert_called_once()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "ДАШБОРД АДМИНИСТРАТОРА" in call_args
    assert "ТРЕБУЕТ ВНИМАНИЯ" in call_args
    assert "Рекомендации" in call_args
    assert "Мало бронирований сегодня" in call_args
    assert "Много неоплаченных бронирований" in call_args
    assert "Много свободных капитанов" in call_args


@pytest.mark.asyncio
async def test_dashboard_handler_no_alerts(telegram_message_mock):
    """Тест дашборда без срочных задач."""
    from app.routers.admin.statistic import dashboard_handler

    telegram_message_mock.text = "/dashboard"

    mock_stats = AsyncMock()
    mock_stats.get_daily_stats.return_value = {
        'total_bookings': 10, 'total_revenue': 50000, 'new_users': 5
    }
    mock_stats.get_active_excursions_count.return_value = 6
    mock_stats.get_urgent_bookings_info.return_value = 0
    mock_stats.get_captains_without_slots.return_value = 0

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await dashboard_handler(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "ТРЕБУЕТ ВНИМАНИЯ" not in call_args
    assert "Рекомендации" not in call_args


@pytest.mark.asyncio
async def test_dashboard_handler_no_bookings_today(telegram_message_mock):
    """Тест дашборда с нулевыми бронированиями (совет)."""
    from app.routers.admin.statistic import dashboard_handler

    telegram_message_mock.text = "/dashboard"

    mock_stats = AsyncMock()
    mock_stats.get_daily_stats.return_value = {
        'total_bookings': 0, 'total_revenue': 0, 'new_users': 1
    }
    mock_stats.get_active_excursions_count.return_value = 2
    mock_stats.get_urgent_bookings_info.return_value = 0
    mock_stats.get_captains_without_slots.return_value = 0

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await dashboard_handler(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Мало бронирований сегодня" in call_args


@pytest.mark.asyncio
async def test_dashboard_handler_many_urgent(telegram_message_mock):
    """Тест дашборда с большим количеством неоплаченных."""
    from app.routers.admin.statistic import dashboard_handler

    telegram_message_mock.text = "/dashboard"

    mock_stats = AsyncMock()
    mock_stats.get_daily_stats.return_value = {
        'total_bookings': 2, 'total_revenue': 5000, 'new_users': 1
    }
    mock_stats.get_active_excursions_count.return_value = 3
    mock_stats.get_urgent_bookings_info.return_value = 7
    mock_stats.get_captains_without_slots.return_value = 5

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await dashboard_handler(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Много неоплаченных бронирований" in call_args
    assert "Много свободных капитанов" in call_args
    assert "Мало бронирований сегодня" in call_args


@pytest.mark.asyncio
async def test_dashboard_handler_db_error(telegram_message_mock):
    """Тест ошибки получения данных дашборда."""
    from app.routers.admin.statistic import dashboard_handler

    telegram_message_mock.text = "/dashboard"

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", side_effect=Exception("DB error")):
            await dashboard_handler(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Ошибка" in call_args


# ========== ТЕСТЫ: statistics_today ==========

@pytest.mark.asyncio
async def test_statistics_today_success(telegram_message_mock):
    """Тест успешного отображения статистики за сегодня."""
    from app.routers.admin.statistic import statistics_today

    telegram_message_mock.text = "Сегодня"

    mock_stats = AsyncMock()
    mock_stats.get_daily_stats.return_value = {
        'total_bookings': 5, 'total_revenue': 15000, 'new_users': 3
    }
    mock_stats.get_daily_excursions_stats.return_value = [
        MagicMock(name="Экскурсия 1", total_bookings=3, total_people=5)
    ]
    mock_stats.get_daily_captains_stats.return_value = [
        MagicMock(full_name="Иван", total_bookings=2)
    ]

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_today(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "СТАТИСТИКА ЗА СЕГОДНЯ" in call_args
    assert "Новые бронирования: 5" in call_args
    assert "Выручка: 15000" in call_args
    assert "Экскурсия 1" in call_args
    assert "Иван" in call_args


@pytest.mark.asyncio
async def test_statistics_today_empty(telegram_message_mock):
    """Тест статистики за сегодня без данных."""
    from app.routers.admin.statistic import statistics_today

    telegram_message_mock.text = "Сегодня"

    mock_stats = AsyncMock()
    mock_stats.get_daily_stats.return_value = {
        'total_bookings': 0, 'total_revenue': 0, 'new_users': 0
    }
    mock_stats.get_daily_excursions_stats.return_value = []
    mock_stats.get_daily_captains_stats.return_value = []

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_today(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Статистика за сегодня отсутствует" in call_args


@pytest.mark.asyncio
async def test_statistics_today_error(telegram_message_mock):
    """Тест ошибки при получении статистики за сегодня."""
    from app.routers.admin.statistic import statistics_today

    telegram_message_mock.text = "Сегодня"

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", side_effect=Exception("DB error")):
            await statistics_today(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Ошибка" in call_args


# ========== ТЕСТЫ: statistics_period_start ==========

@pytest.mark.asyncio
async def test_statistics_period_start(telegram_message_mock, mock_state):
    """Тест начала выбора периода."""
    from app.routers.admin.statistic import statistics_period_start

    telegram_message_mock.text = "За период"

    await statistics_period_start(telegram_message_mock, mock_state)

    mock_state.set_state.assert_called_once()
    telegram_message_mock.answer.assert_called_once()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Введите период" in call_args


# ========== ТЕСТЫ: statistics_period_process ==========

@pytest.mark.asyncio
async def test_statistics_period_process_success(telegram_message_mock, mock_state):
    """Тест успешной обработки периода."""
    from app.routers.admin.statistic import statistics_period_process

    telegram_message_mock.text = "01.04.2026-30.04.2026"

    mock_stats = AsyncMock()
    mock_stats.generate_period_report.return_value = "Отчет за период"

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_period_process(telegram_message_mock, mock_state)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Отчет за период" in call_args
    mock_state.clear.assert_called_once()


@pytest.mark.asyncio
async def test_statistics_period_process_reversed_dates(telegram_message_mock, mock_state):
    """Тест когда дата начала позже даты окончания."""
    from app.routers.admin.statistic import statistics_period_process

    telegram_message_mock.text = "30.04.2026-01.04.2026"

    await statistics_period_process(telegram_message_mock, mock_state)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Дата начала не может быть позже" in call_args
    mock_state.clear.assert_not_called()


@pytest.mark.asyncio
async def test_statistics_period_process_invalid_format(telegram_message_mock, mock_state):
    """Тест неверного формата периода."""
    from app.routers.admin.statistic import statistics_period_process

    telegram_message_mock.text = "invalid format"

    await statistics_period_process(telegram_message_mock, mock_state)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Ошибка формата" in call_args


@pytest.mark.asyncio
async def test_statistics_period_process_db_error(telegram_message_mock, mock_state):
    """Тест ошибки при обработке периода."""
    from app.routers.admin.statistic import statistics_period_process

    telegram_message_mock.text = "01.04.2026-30.04.2026"

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mock_stats = AsyncMock()
    mock_stats.generate_period_report.side_effect = Exception("DB error")

    with patch("app.routers.admin.statistic.async_session", return_value=mock_session):
        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_period_process(telegram_message_mock, mock_state)

    telegram_message_mock.answer.assert_called()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "ошибка" in call_args.lower()
    mock_state.clear.assert_called_once()


# ========== ТЕСТЫ: cancel_statistics_period ==========

@pytest.mark.asyncio
async def test_cancel_statistics_period(telegram_message_mock, mock_state):
    """Тест отмены выбора периода."""
    from app.routers.admin.statistic import cancel_statistics_period

    telegram_message_mock.text = "Отмена"

    await cancel_statistics_period(telegram_message_mock, mock_state)

    mock_state.clear.assert_called_once()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "отменен" in call_args


# ========== ТЕСТЫ: statistics_current_month ==========

@pytest.mark.asyncio
async def test_statistics_current_month_success(telegram_message_mock):
    """Тест статистики за текущий месяц."""
    from app.routers.admin.statistic import statistics_current_month

    telegram_message_mock.text = "За текущий месяц"

    mock_stats = AsyncMock()
    mock_stats.generate_period_report.return_value = "Отчет за текущий месяц"

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_current_month(telegram_message_mock)

    telegram_message_mock.answer.assert_called_once()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Отчет за текущий месяц" in call_args


@pytest.mark.asyncio
async def test_statistics_current_month_error(telegram_message_mock):
    """Тест ошибки статистики за текущий месяц."""
    from app.routers.admin.statistic import statistics_current_month

    telegram_message_mock.text = "За текущий месяц"

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mock_stats = AsyncMock()
    mock_stats.generate_period_report.side_effect = Exception("DB error")

    with patch("app.routers.admin.statistic.async_session", return_value=mock_session):
        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_current_month(telegram_message_mock)

    telegram_message_mock.answer.assert_called()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Ошибка" in call_args


# ========== ТЕСТЫ: statistics_by_captains ==========

@pytest.mark.asyncio
async def test_statistics_by_captains_success(telegram_message_mock):
    """Тест статистики по капитанам."""
    from app.routers.admin.statistic import statistics_by_captains

    telegram_message_mock.text = "По капитанам (за месяц)"

    mock_captain = MagicMock()
    mock_captain.full_name = "Иванов Иван"

    mock_stats = AsyncMock()
    mock_stats.get_captains_with_stats.return_value = [{
        'captain': mock_captain,
        'stats': {
            'period_start': datetime.now().replace(day=1),
            'period_end': datetime.now(),
            'total_slots': 5,
            'conducted_slots': 3,
            'not_conducted_slots': 2,
            'total_people': 12,
            'total_revenue': 36000
        }
    }]

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_by_captains(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Иванов Иван" in call_args
    assert "Рейсов всего: 5" in call_args
    assert "Проведено: 3" in call_args
    assert "Не проведено (никто не пришел): 2" in call_args
    assert "Людей: 12" in call_args
    assert "Выручка: 36000" in call_args


@pytest.mark.asyncio
async def test_statistics_by_captains_empty(telegram_message_mock):
    """Тест статистики по капитанам без данных."""
    from app.routers.admin.statistic import statistics_by_captains

    telegram_message_mock.text = "По капитанам (за месяц)"

    mock_stats = AsyncMock()
    mock_stats.get_captains_with_stats.return_value = []

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_by_captains(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Нет данных" in call_args


# ========== ТЕСТЫ: statistics_by_excursions ==========

@pytest.mark.asyncio
async def test_statistics_by_excursions_success(telegram_message_mock):
    """Тест показа списка экскурсий для статистики."""
    from app.routers.admin.statistic import statistics_by_excursions

    telegram_message_mock.text = "По экскурсиям"

    mock_excursion = MagicMock()
    mock_excursion.id = 1
    mock_excursion.name = "Морская прогулка"
    mock_excursion.is_active = True

    mock_excursion_repo = AsyncMock()
    mock_excursion_repo.get_all.return_value = [mock_excursion]

    mock_stats = AsyncMock()
    mock_stats.stats_repo = AsyncMock()
    mock_stats.stats_repo.get_popular_excursion.return_value = ("Морская прогулка", 10)

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.ExcursionRepository", return_value=mock_excursion_repo):
            with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
                await statistics_by_excursions(telegram_message_mock)

    telegram_message_mock.answer.assert_called_once()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Самая популярная" in call_args
    assert "Морская прогулка" in call_args
    assert "10 бронирований" in call_args

@pytest.mark.asyncio
async def test_statistics_by_excursions_empty(telegram_message_mock):
    """Тест когда нет доступных экскурсий."""
    from app.routers.admin.statistic import statistics_by_excursions

    telegram_message_mock.text = "По экскурсиям"

    mock_excursion_repo = AsyncMock()
    mock_excursion_repo.get_all.return_value = []

    mock_stats = AsyncMock()
    mock_stats.stats_repo = AsyncMock()
    mock_stats.stats_repo.get_popular_excursion.return_value = ("Нет данных", 0)

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.ExcursionRepository", return_value=mock_excursion_repo):
            with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
                await statistics_by_excursions(telegram_message_mock)

    telegram_message_mock.answer.assert_called_once()
    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Нет доступных экскурсий" in call_args

# ========== ТЕСТЫ: excursion_stats_callback ==========

@pytest.mark.asyncio
async def test_excursion_stats_callback_success(mock_callback_query):
    """Тест детальной статистики по экскурсии."""
    from app.routers.admin.statistic import excursion_stats_callback

    mock_callback_query.data = "excursion_stats:5"

    mock_excursion = MagicMock()
    mock_excursion.name = "Морская прогулка"

    mock_stats = AsyncMock()
    mock_stats.get_single_excursion_stats.return_value = {
        'total_bookings': 10, 'total_people': 15, 'total_revenue': 50000
    }

    mock_excursion_repo = AsyncMock()
    mock_excursion_repo.get_by_id.return_value = mock_excursion

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            with patch("app.routers.admin.statistic.ExcursionRepository", return_value=mock_excursion_repo):
                await excursion_stats_callback(mock_callback_query)

    mock_callback_query.answer.assert_called_once()
    call_args = mock_callback_query.message.edit_text.call_args[0][0]
    assert "Морская прогулка" in call_args
    assert "10" in call_args
    assert "15" in call_args
    assert "50000" in call_args


@pytest.mark.asyncio
async def test_excursion_stats_callback_not_found(mock_callback_query):
    """Тест когда экскурсия не найдена."""
    from app.routers.admin.statistic import excursion_stats_callback

    mock_callback_query.data = "excursion_stats:999"

    mock_stats = AsyncMock()
    mock_stats.get_single_excursion_stats.return_value = {
        'total_bookings': 0, 'total_people': 0, 'total_revenue': 0
    }

    mock_excursion_repo = AsyncMock()
    mock_excursion_repo.get_by_id.return_value = None

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            with patch("app.routers.admin.statistic.ExcursionRepository", return_value=mock_excursion_repo):
                await excursion_stats_callback(mock_callback_query)

    call_args = mock_callback_query.message.edit_text.call_args[0][0]
    assert "Экскурсия #999" in call_args


# ========== ТЕСТЫ: statistics_cancellations ==========

@pytest.mark.asyncio
async def test_statistics_cancellations_success(telegram_message_mock):
    """Тест статистики отказов и неявок."""
    from app.routers.admin.statistic import statistics_cancellations

    telegram_message_mock.text = "Отказы и неявки"

    mock_stats = AsyncMock()
    mock_stats.get_cancelled_stats.return_value = {
        'cancelled': 5, 'refunds_amount': 15000, 'not_arrived': 2
    }

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
            await statistics_cancellations(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Отменённые бронирования: 5" in call_args
    assert "Сумма возвратов: 15000" in call_args
    assert "Неявки (не пришли): 2" in call_args


@pytest.mark.asyncio
async def test_statistics_cancellations_error(telegram_message_mock):
    """Тест ошибки статистики отказов."""
    from app.routers.admin.statistic import statistics_cancellations

    telegram_message_mock.text = "Отказы и неявки"

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.StatisticsManager", side_effect=Exception("DB error")):
            await statistics_cancellations(telegram_message_mock)

    call_args = telegram_message_mock.answer.call_args[0][0]
    assert "Ошибка" in call_args


# ========== ТЕСТЫ: back_to_statistics_callback ==========

@pytest.mark.asyncio
async def test_back_to_statistics_callback(mock_callback_query):
    """Тест возврата к списку экскурсий."""
    from app.routers.admin.statistic import back_to_statistics_callback

    mock_callback_query.data = "back_to_statistics"

    mock_excursion = MagicMock()
    mock_excursion.id = 1
    mock_excursion.name = "Морская прогулка"
    mock_excursion.is_active = True

    mock_excursion_repo = AsyncMock()
    mock_excursion_repo.get_all.return_value = [mock_excursion]

    mock_stats = AsyncMock()
    mock_stats.stats_repo = AsyncMock()
    mock_stats.stats_repo.get_popular_excursion.return_value = ("Морская прогулка", 10)

    with patch("app.routers.admin.statistic.async_session") as mock_session:
        mock_session.return_value.__aenter__.return_value = mock_session
        mock_session.return_value.__aexit__ = AsyncMock()

        with patch("app.routers.admin.statistic.ExcursionRepository", return_value=mock_excursion_repo):
            with patch("app.routers.admin.statistic.StatisticsManager", return_value=mock_stats):
                await back_to_statistics_callback(mock_callback_query)

    mock_callback_query.answer.assert_called_once()