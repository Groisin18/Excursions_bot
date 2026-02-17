"""
Скрипт для запуска тестов с HTML отчетом и текстовым выводом.
Поддерживает выбор конкретных тестовых файлов через аргументы командной строки.
"""
"""
Примеры использования скрипта:

1. ВСЕ ТЕСТЫ:
   python tests/run_tests.py
   python tests/run_tests.py --all

2. КОНКРЕТНЫЕ ФАЙЛЫ:
   python tests/run_tests.py test_validation.py
   python tests/run_tests.py test_validation.py test_datetime_utils.py
   python tests/run_tests.py test_middleware.py

3. ПО ШАБЛОНУ:
   python tests/run_tests.py test_*.py
   python tests/run_tests.py *validation*.py

4. СПИСОК ВСЕХ ТЕСТОВ:
   python tests/run_tests.py --list

5. БЕЗ ОТЧЕТОВ:
   python tests/run_tests.py test_validation.py --no-html --no-txt

6. ТОЛЬКО HTML ОТЧЕТ:
   python tests/run_tests.py test_validation.py --no-txt

7. ТОЛЬКО ТЕКСТОВЫЙ ОТЧЕТ:
   python tests/run_tests.py test_validation.py --no-html
"""

import subprocess
from pathlib import Path
import datetime
import sys
import re
import argparse


def parse_arguments():
    """Парсинг аргументов командной строки."""
    parser = argparse.ArgumentParser(
        description='Запуск тестов с выбором конкретных файлов или всех тестов.'
    )

    parser.add_argument(
        'test_files',
        nargs='*',  # 0 или более аргументов
        help='Имена тестовых файлов для запуска (например: test_validation.py test_datetime_utils.py)'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Запустить все тесты (по умолчанию, если не указаны файлы)'
    )

    parser.add_argument(
        '--list',
        action='store_true',
        help='Показать список всех доступных тестовых файлов и выйти'
    )

    parser.add_argument(
        '--no-html',
        action='store_true',
        help='Не создавать HTML отчет'
    )

    parser.add_argument(
        '--no-txt',
        action='store_true',
        help='Не создавать текстовый отчет'
    )

    return parser.parse_args()


def find_all_test_files():
    """Находит все тестовые файлы в папке tests и всех подпапках."""
    test_files = []
    tests_path = Path("tests")

    for test_file in tests_path.rglob("test_*.py"):
        if test_file.name != "__init__.py":
            test_files.append(str(test_file))

    return test_files


def list_test_files():
    """Выводит список всех доступных тестовых файлов."""
    test_files = find_all_test_files()

    if not test_files:
        print("Тестовые файлы не найдены.")
        return

    print("=" * 50)
    print("ДОСТУПНЫЕ ТЕСТОВЫЕ ФАЙЛЫ")
    print("=" * 50)

    for i, test_file in enumerate(sorted(test_files), 1):
        file_path = Path(test_file)
        print(f"{i:2}. {file_path.name}")
        print(f"    {test_file}")

    print(f"\nВсего файлов: {len(test_files)}")
    print("\nПримеры использования:")
    print("  python run_tests.py                        # Все тесты")
    print("  python run_tests.py --all                  # Все тесты")
    print("  python run_tests.py test_validation.py     # Один файл")
    print("  python run_tests.py test_*.py              # По шаблону")
    print("  python run_tests.py --list                 # Список файлов")

    return test_files


def resolve_test_files(args):
    """Определяет, какие тестовые файлы запускать."""
    if args.list:
        list_test_files()
        return None

    if args.test_files:
        resolved_files = []
        tests_path = Path("tests")

        for pattern in args.test_files:
            if Path(pattern).exists():
                resolved_files.append(pattern)
            else:
                for file_path in tests_path.rglob(pattern):
                    if file_path.name != "__init__.py":
                        resolved_files.append(str(file_path))
                for file_path in tests_path.rglob(f"*{pattern}*"):
                    if file_path.name != "__init__.py" and file_path.suffix == ".py":
                        if str(file_path) not in resolved_files:
                            resolved_files.append(str(file_path))

        return list(set(resolved_files))
    return find_all_test_files()


def run_tests(test_files, create_html=True, create_txt=True):
    """Запуск тестов и создание отчетов."""
    if not test_files:
        print("Ошибка: не найдены тестовые файлы для запуска.")
        return 1

    # Создаем директорию для отчетов
    reports_dir = Path("tests/reports")
    reports_dir.mkdir(exist_ok=True)

    # Генерируем timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 50)
    print("ЗАПУСК ТЕСТОВ")
    print("=" * 50)

    # Показываем файлы для тестирования
    print("\nТестовые файлы:")
    for i, test_file in enumerate(test_files, 1):
        file_path = Path(test_file)
        print(f"  {i}. {file_path.name}")

    # Команда для запуска тестов
    cmd = ["pytest", "-v", *test_files]

    if create_html:
        html_report = reports_dir / f"test_report_{timestamp}.html"
        cmd.extend([f"--html={html_report}", "--self-contained-html"])

    print(f"\nЗапуск тестов...")
    print("-" * 50)

    try:
        # Запускаем тесты с правильной кодировкой для Windows
        if sys.platform == "win32":
            encoding = 'cp1251'
        else:
            encoding = 'utf-8'

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding=encoding
        )

        # Сохраняем полный вывод в TXT файл
        if create_txt:
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
                    f.write(result.stdout)

                if result.stderr:
                    f.write("\n\n" + "=" * 60 + "\n")
                    f.write("ОШИБКИ:\n")
                    f.write("-" * 60 + "\n")
                    f.write(result.stderr)

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
        print("\n" + "=" * 50)
        print("СОЗДАННЫЕ ФАЙЛЫ:")
        print("=" * 50)

        if create_html:
            print(f"HTML отчет: test_report_{timestamp}.html")

        if create_txt:
            print(f"Текстовый отчет: test_output_{timestamp}.txt")

        if create_html or create_txt:
            print(f"\nПапка: {reports_dir.absolute()}")

        print("=" * 50)

        return result.returncode

    except FileNotFoundError:
        print("Ошибка: pytest не найден. Установите pytest: pip install pytest")
        return 1
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return 1


def main():
    """Основная функция."""
    args = parse_arguments()

    if args.list:
        list_test_files()
        return 0

    test_files = resolve_test_files(args)

    if test_files is None:
        return 0  # Просто показали список файлов

    if not test_files:
        print("Ошибка: не найдены тестовые файлы (test_*.py) в папке tests/")
        return 1

    return run_tests(
        test_files,
        create_html=not args.no_html,
        create_txt=not args.no_txt
    )


if __name__ == "__main__":
    sys.exit(main())