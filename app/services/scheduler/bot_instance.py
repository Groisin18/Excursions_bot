# app/services/scheduler/bot_instance.py
"""Глобальный экземпляр бота для задач планировщика."""

_bot_instance = None

async def set_bot_instance(bot):
    global _bot_instance
    _bot_instance = bot

def get_bot_instance():
    return _bot_instance