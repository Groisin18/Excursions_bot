"""
Клиент для работы с API возвратов YooKassa
"""
import os
import base64
from typing import Dict, Optional, Tuple

import aiohttp
from dotenv import load_dotenv

from app.utils.logging_config import get_logger

load_dotenv()

logger = get_logger(__name__)


class YooKassaRefundClient:
    """Клиент для работы с возвратами YooKassa"""

    def __init__(self):
        # Получаем учетные данные из отдельных переменных
        self.shop_id = os.getenv('YOOKASSA_SHOP_ID', '')
        self.secret_key = os.getenv('YOOKASSA_SECRET_KEY', '')

        if not self.shop_id or not self.secret_key:
            logger.error("YooKassa credentials отсутствуют! Возвраты не будут работать.")

        self.api_url = "https://api.yookassa.ru/v3"

    def _get_auth_header(self) -> str:
        """Получить заголовок авторизации Basic"""
        auth_string = f"{self.shop_id}:{self.secret_key}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        return f"Basic {encoded}"

    def _get_headers(self, idempotence_key: str = None) -> Dict:
        """Получить заголовки для запроса к YooKassa"""
        headers = {
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json"
        }
        if idempotence_key:
            headers["Idempotence-Key"] = idempotence_key
        return headers

    async def create_refund(
        self,
        payment_id: str,
        amount: int,
        idempotence_key: str,
        reason: str = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Создать возврат в YooKassa

        Args:
            payment_id: ID платежа в YooKassa
            amount: Сумма возврата в КОПЕЙКАХ
            idempotence_key: Ключ идемпотентности
            reason: Причина возврата (опционально)
        """
        if not self.shop_id or not self.secret_key:
            error_msg = "YooKassa credentials не настроены"
            logger.error(error_msg)
            return False, None, error_msg

        url = f"{self.api_url}/refunds"

        # amount приходит в копейках, делим на 100 чтобы получить рубли
        amount_rub = amount / 100
        payload = {
            "amount": {
                "value": f"{amount_rub:.2f}",
                "currency": "RUB"
            },
            "payment_id": payment_id
        }

        if reason:
            payload["description"] = reason

        headers = self._get_headers(idempotence_key)

        logger.info(f"Создание возврата: payment_id={payment_id}, amount={amount_rub} руб.")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Возврат успешно создан: {data.get('id')}, статус: {data.get('status')}")
                        return True, data, None
                    else:
                        error_msg = f"Ошибка YooKassa API: {response.status} - {response_text}"
                        logger.error(error_msg)
                        return False, None, error_msg

        except aiohttp.ClientError as e:
            error_msg = f"Сетевая ошибка при создании возврата: {e}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при создании возврата: {e}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg

    async def get_refund(self, refund_id: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Получить информацию о возврате из YooKassa

        Args:
            refund_id: ID возврата в YooKassa

        Returns:
            Tuple[bool, Optional[Dict], Optional[str]]:
                - success: успех операции
                - response_data: данные ответа YooKassa
                - error_message: сообщение об ошибке
        """
        if not self.shop_id or not self.secret_key:
            error_msg = "YooKassa credentials не настроены"
            logger.error(error_msg)
            return False, None, error_msg

        url = f"{self.api_url}/refunds/{refund_id}"
        headers = self._get_headers()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    response_text = await response.text()

                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"Получен статус возврата {refund_id}: {data.get('status')}")
                        return True, data, None
                    else:
                        error_msg = f"Ошибка получения возврата: {response.status} - {response_text}"
                        logger.error(error_msg)
                        return False, None, error_msg

        except aiohttp.ClientError as e:
            error_msg = f"Сетевая ошибка при получении возврата: {e}"
            logger.error(error_msg)
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка при получении возврата: {e}"
            logger.error(error_msg, exc_info=True)
            return False, None, error_msg


# Создаем синглтон клиента
yookassa_refund_client = YooKassaRefundClient()