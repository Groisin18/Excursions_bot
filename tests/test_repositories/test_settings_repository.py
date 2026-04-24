"""Тесты для SettingsRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.database.repositories.settings_repository import SettingsRepository


class TestSettingsRepository:
    """Тесты для SettingsRepository."""

    @pytest.fixture
    def mock_session(self):
        """Мок сессии."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Создать репозиторий с замоканной сессией."""
        with patch("app.database.repositories.settings_repository.BaseRepository.__init__", return_value=None):
            repo = SettingsRepository(mock_session)
            repo.session = mock_session
            repo.logger = MagicMock()
            return repo

    # ========== get_by_key ==========

    @pytest.mark.asyncio
    async def test_get_by_key_found(self, repo):
        """Настройка найдена."""
        mock_setting = MagicMock()
        mock_setting.key = "vat_rate"
        mock_setting.value = "20"
        repo._get_one = AsyncMock(return_value=mock_setting)

        result = await repo.get_by_key("vat_rate")

        assert result is mock_setting
        repo._get_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_by_key_not_found(self, repo):
        """Настройка не найдена."""
        repo._get_one = AsyncMock(return_value=None)

        result = await repo.get_by_key("nonexistent")

        assert result is None

    # ========== get_value ==========

    @pytest.mark.asyncio
    async def test_get_value_found(self, repo):
        """Значение получено."""
        mock_setting = MagicMock()
        mock_setting.value = "20"
        repo.get_by_key = AsyncMock(return_value=mock_setting)

        result = await repo.get_value("vat_rate")

        assert result == "20"

    @pytest.mark.asyncio
    async def test_get_value_default(self, repo):
        """Значение не найдено — возвращает default."""
        repo.get_by_key = AsyncMock(return_value=None)

        result = await repo.get_value("nonexistent", default="0")

        assert result == "0"

    @pytest.mark.asyncio
    async def test_get_value_no_default(self, repo):
        """Значение не найдено, default не указан — возвращает None."""
        repo.get_by_key = AsyncMock(return_value=None)

        result = await repo.get_value("nonexistent")

        assert result is None

    # ========== get_all ==========

    @pytest.mark.asyncio
    async def test_get_all_success(self, repo):
        """Успешное получение всех настроек."""
        s1 = MagicMock()
        s1.key = "vat_rate"
        s1.value = "20"

        s2 = MagicMock()
        s2.key = "send_receipt"
        s2.value = "true"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [s1, s2]
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_all()

        assert result == {"vat_rate": "20", "send_receipt": "true"}

    @pytest.mark.asyncio
    async def test_get_all_empty(self, repo):
        """Нет настроек — пустой словарь."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        repo._execute_query = AsyncMock(return_value=mock_result)

        result = await repo.get_all()

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_all_error(self, repo):
        """Ошибка при получении всех настроек."""
        repo._execute_query = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.get_all()

        assert result == {}

    # ========== set ==========

    @pytest.mark.asyncio
    async def test_set_create_new(self, repo):
        """Создание новой настройки."""
        repo.get_by_key = AsyncMock(return_value=None)
        repo._create = AsyncMock()

        result = await repo.set(
            key="vat_rate",
            value="20",
            description="Ставка НДС",
            updated_by=5
        )

        assert result is True
        repo._create.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_update_existing(self, repo):
        """Обновление существующей настройки."""
        mock_existing = MagicMock()
        repo.get_by_key = AsyncMock(return_value=mock_existing)
        repo._update = AsyncMock(return_value=1)

        result = await repo.set(
            key="vat_rate",
            value="22",
            description="Новая ставка"
        )

        assert result is True
        repo._update.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_update_zero_rows(self, repo):
        """Обновление затронуло 0 строк — возвращает False."""
        mock_existing = MagicMock()
        repo.get_by_key = AsyncMock(return_value=mock_existing)
        repo._update = AsyncMock(return_value=0)

        result = await repo.set(key="vat_rate", value="22")

        assert result is False

    @pytest.mark.asyncio
    async def test_set_error(self, repo):
        """Ошибка при установке настройки."""
        repo.get_by_key = AsyncMock(side_effect=Exception("DB error"))

        result = await repo.set(key="vat_rate", value="20")

        assert result is False

    # ========== get_int ==========

    @pytest.mark.asyncio
    async def test_get_int_success(self, repo):
        """Успешное получение целого числа."""
        repo.get_value = AsyncMock(return_value="42")

        result = await repo.get_int("max_people")

        assert result == 42

    @pytest.mark.asyncio
    async def test_get_int_default_on_none(self, repo):
        """Значение None — возвращает default."""
        repo.get_value = AsyncMock(return_value=None)

        result = await repo.get_int("max_people", default=10)

        assert result == 10

    @pytest.mark.asyncio
    async def test_get_int_default_on_invalid(self, repo):
        """Некорректное значение — возвращает default."""
        repo.get_value = AsyncMock(return_value="not_a_number")

        result = await repo.get_int("max_people", default=10)

        assert result == 10

    @pytest.mark.asyncio
    async def test_get_int_default_zero(self, repo):
        """Default не указан — возвращает 0."""
        repo.get_value = AsyncMock(return_value=None)

        result = await repo.get_int("nonexistent")

        assert result == 0

    # ========== get_bool ==========

    @pytest.mark.asyncio
    async def test_get_bool_true_values(self, repo):
        """Разные варианты true."""
        for value in ["true", "True", "1", "yes", "YES", "on", "ON"]:
            repo.get_value = AsyncMock(return_value=value)
            result = await repo.get_bool("test")
            assert result is True, f"Failed for value: {value}"

    @pytest.mark.asyncio
    async def test_get_bool_false_values(self, repo):
        """Разные варианты false."""
        for value in ["false", "False", "0", "no", "off", "anything_else"]:
            repo.get_value = AsyncMock(return_value=value)
            result = await repo.get_bool("test")
            assert result is False, f"Failed for value: {value}"

    @pytest.mark.asyncio
    async def test_get_bool_default_on_none(self, repo):
        """Значение None — возвращает default."""
        repo.get_value = AsyncMock(return_value=None)

        result = await repo.get_bool("nonexistent", default=True)

        assert result is True