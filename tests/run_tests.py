#!/usr/bin/env python3
"""
Скрипт для запуска тестов с HTML отчетом и текстовым выводом.
Минимальный вывод в консоль.
"""

import subprocess
from pathlib import Path
import datetime
import sys


def run_tests():
    """Запуск тестов и создание отчетов."""

    # Создаем директорию для отчетов
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True)

    # Генерируем timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Находим все тестовые файлы
    test_files = []
    tests_path = Path("tests")

    for test_file in tests_path.glob("test_*.py"):
        if test_file.name != "__init__.py":
            test_files.append(str(test_file))

    if not test_files:
        print("Ошибка: не найдены тестовые файлы (test_*.py) в папке tests/")
        return 1

    print("=" * 50)
    print("ЗАПУСК ТЕСТОВ")
    print("=" * 50)

    # Показываем файлы для тестирования
    print("\nТестовые файлы:")
    for i, test_file in enumerate(test_files, 1):
        print(f"  {i}. {Path(test_file).name}")

    # Команда для запуска тестов
    cmd = [
        "pytest",
        *test_files,
        "-v",
        f"--html={reports_dir}/test_report_{timestamp}.html",
        "--self-contained-html"
    ]

    print(f"\nЗапуск тестов...")
    print("-" * 50)

    try:
        # Запускаем тесты с правильной кодировкой для Windows
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='cp1251'  # Кодировка Windows
        )

        # Сохраняем полный вывод в TXT файл
        txt_report_path = reports_dir / f"test_output_{timestamp}.txt"
        with open(txt_report_path, "w", encoding="utf-8") as f:
            f.write(f"ТЕСТОВЫЙ ОТЧЕТ - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Тестовые файлы: {len(test_files)}\n")
            for tf in test_files:
                f.write(f"  • {tf}\n")
            f.write("\n" + "=" * 60 + "\n\n")

            if result.stdout:
                f.write("ВЫВОД:\n")
                f.write("-" * 60 + "\n")
                # Конвертируем в utf-8 для записи в файл
                try:
                    f.write(result.stdout)
                except UnicodeEncodeError:
                    f.write(result.stdout.encode('utf-8', errors='replace').decode('utf-8'))

            if result.stderr:
                f.write("\n\n" + "=" * 60 + "\n")
                f.write("ОШИБКИ:\n")
                f.write("-" * 60 + "\n")
                try:
                    f.write(result.stderr)
                except UnicodeEncodeError:
                    f.write(result.stderr.encode('utf-8', errors='replace').decode('utf-8'))

            f.write(f"\n\nКод возврата: {result.returncode}\n")
            f.write("=" * 60 + "\n")

        # Анализируем вывод для краткой информации
        passed = 0
        failed = 0
        errors = 0
        skipped = 0

        if result.stdout:
            lines = result.stdout.split('\n')
            for line in lines:
                line_lower = line.lower()
                if 'passed' in line_lower and 'failed' not in line_lower and 'error' not in line_lower:
                    # Ищем число в строке типа "59 passed"
                    import re
                    match = re.search(r'(\d+)\s+passed', line_lower)
                    if match:
                        passed = int(match.group(1))

                if 'failed' in line_lower:
                    match = re.search(r'(\d+)\s+failed', line_lower)
                    if match:
                        failed = int(match.group(1))

                if 'error' in line_lower and 'failed' not in line_lower:
                    match = re.search(r'(\d+)\s+error', line_lower)
                    if match:
                        errors = int(match.group(1))

                if 'skipped' in line_lower:
                    match = re.search(r'(\d+)\s+skipped', line_lower)
                    if match:
                        skipped = int(match.group(1))

        # Выводим краткий результат
        print("\nРЕЗУЛЬТАТЫ:")
        print("-" * 50)

        total_tests = passed + failed + errors + skipped

        if passed > 0:
            print(f"Пройдено: {passed}")

        if failed > 0:
            print(f"Не пройдено: {failed}")

        if errors > 0:
            print(f"Ошибок: {errors}")

        if skipped > 0:
            print(f"Пропущено: {skipped}")

        if total_tests > 0:
            success_rate = (passed / total_tests) * 100
            print(f"\nУспешность: {success_rate:.1f}%")

        print(f"\nКод возврата: {result.returncode}")

        # Пути к отчетам
        html_report = reports_dir / f"test_report_{timestamp}.html"

        print("\n" + "=" * 50)
        print("СОЗДАННЫЕ ФАЙЛЫ:")
        print("=" * 50)
        print(f"HTML отчет: {html_report.name}")
        print(f"Текстовый отчет: {txt_report_path.name}")
        print(f"\nПапка: {reports_dir.absolute()}")
        print("=" * 50)

        return result.returncode

    except FileNotFoundError:
        print("Ошибка: pytest не найден. Установите pytest: pip install pytest")
        return 1
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())