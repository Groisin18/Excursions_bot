import csv
import json
from io import StringIO, BytesIO
from datetime import datetime

class ExportService:
    async def export_bookings_csv(self, start_date: datetime, end_date: datetime):
        """Экспорт бронирований в CSV"""
        bookings = await self.get_bookings_for_period(start_date, end_date)

        output = StringIO()
        writer = csv.writer(output)

        # Заголовки
        writer.writerow([
            'ID', 'Дата создания', 'Клиент', 'Телефон',
            'Экскурсия', 'Дата экскурсии', 'Кол-во человек',
            'Сумма', 'Статус'
        ])

        # Данные
        for booking in bookings:
            writer.writerow([
                booking.id,
                booking.created_at.strftime('%Y-%m-%d %H:%M'),
                f"{booking.client.name} {booking.client.surname}",
                booking.client.phone,
                booking.excursion.name,
                booking.slot.date.strftime('%Y-%m-%d'),
                booking.participants_count,
                booking.total_amount,
                booking.status
            ])

        return output.getvalue()

    async def generate_finance_report_pdf(self):
        """Генерация финансового отчета в PDF"""
        # Используйте reportlab или другую библиотеку
        pass