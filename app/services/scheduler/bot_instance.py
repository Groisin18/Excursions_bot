"""Глобальный экземпляр бота для задач планировщика."""

from typing import Optional
from aiogram import Bot

_bot_instance: Optional[Bot] = None


def set_bot_instance(bot: Bot) -> None:
    """Установить глобальный экземпляр бота (синхронная функция)"""
    global _bot_instance
    _bot_instance = bot


def get_bot_instance() -> Optional[Bot]:
    """Получить глобальный экземпляр бота"""
    return _bot_instance