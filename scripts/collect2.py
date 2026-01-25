"""
Улучшенный сборщик проекта для работы с нейросетями
Включает: анализ проекта, умное обрезание кода, карту зависимостей
"""
import re
import ast
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

class ProjectAnalyzer:
    """Анализирует проект для принятия решений о сборке"""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.stats = {
            "total_files": 0,
            "total_size": 0,
            "total_code_lines": 0,
            "python_files_count": 0,
            "file_types": defaultdict(int),
            "largest_files": [],  # По размеру файлов
            "files_most_lines": [],  # По количеству строк кода
            "entry_points": [],
            "has_requirements": False,
            "has_setup": False,
            "framework": "generic",
            "complexity_score": 0
        }

    def analyze(self) -> Dict:
        """Проводит полный анализ проекта, исключая сборщик"""
        print("🔍 Анализирую проект...")

        # Получаем путь к сборщику из вызывающего кода
        import inspect
        caller_frame = inspect.currentframe().f_back
        if caller_frame and 'self' in caller_frame.f_locals:
            collector = caller_frame.f_locals['self']
            if hasattr(collector, 'collector_path'):
                self.collector_path = collector.collector_path

        # Сканируем все файлы
        all_files = []
        total_code_lines = 0  # Счетчик строк кода (без пустых строк)

        for path in self.root_dir.rglob("*"):
            if path.is_file():
                # Пропускаем служебные директории
                if any(excl in str(path) for excl in ["__pycache__", ".git", "venv", ".venv"]):
                    continue

                # Пропускаем файлы сборщика
                if hasattr(self, 'collector_path') and path.resolve() == self.collector_path:
                    continue

                rel_path = path.relative_to(self.root_dir)
                is_python_file = path.suffix.lower() == '.py'

                file_info = {
                    "path": rel_path,
                    "full_path": path,
                    "size": path.stat().st_size,
                    "suffix": path.suffix.lower(),
                    "is_python": is_python_file,
                    "code_lines": 0
                }
                all_files.append(file_info)

                # Обновляем статистику
                self.stats["total_files"] += 1
                self.stats["total_size"] += file_info["size"]
                self.stats["file_types"][file_info["suffix"]] += 1

                # Проверяем на особые файлы
                if file_info["path"].name in ["requirements.txt", "setup.py", "pyproject.toml"]:
                    if "requirements" in file_info["path"].name:
                        self.stats["has_requirements"] = True
                    if "setup" in file_info["path"].name or "pyproject" in file_info["path"].name:
                        self.stats["has_setup"] = True

                # Подсчитываем строки кода только для Python файлов
                if is_python_file:
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            file_code_lines = 0
                            for line in f:
                                stripped_line = line.strip()
                                # Считаем только непустые строки
                                if stripped_line:
                                    file_code_lines += 1

                            file_info["code_lines"] = file_code_lines
                            total_code_lines += file_code_lines

                            # Можно также добавить информацию о пустых строках
                            file_info["empty_lines"] = file_info["lines"] - file_code_lines if "lines" in file_info else 0

                    except (UnicodeDecodeError, PermissionError, OSError):
                        # Пропускаем файлы без доступа
                        pass

        # Находим самые большие файлы (по размеру)
        all_files.sort(key=lambda x: x["size"], reverse=True)
        self.stats["largest_files"] = all_files[:10]

        # Находим файлы с наибольшим количеством строк кода
        python_files = [f for f in all_files if f["is_python"]]
        python_files.sort(key=lambda x: x.get("code_lines", 0), reverse=True)
        self.stats["files_most_lines"] = [
            {"path": str(f["path"]), "lines": f["code_lines"]}
            for f in python_files[:10]
        ]

        # Добавляем общее количество строк Python кода в статистику
        self.stats["total_code_lines"] = total_code_lines
        self.stats["python_files_count"] = len(python_files)

        # Находим точки входа
        self._find_entry_points(all_files)

        # Определяем фреймворк
        self._detect_framework(all_files)

        # Оцениваем сложность (можно использовать количество строк кода как метрику)
        self._calculate_complexity(all_files)

        # Строим дерево проекта
        self._build_project_tree()

        print(f"📊 Анализ завершен: {self.stats['total_files']} файлов, "
            f"{self.stats['total_size']/1024:.1f} KB, "
            f"{total_code_lines} строк Python кода в {self.stats['python_files_count']} файлах")
        return self.stats

    def _find_entry_points(self, files: List[Dict]) -> None:
        """Находит точки входа в проект"""
        entry_patterns = [
            ("main.py", 10),  # main.py с высоким приоритетом
            ("app.py", 9),
            ("run.py", 8),
            ("manage.py", 7),
            ("wsgi.py", 6),
            ("asgi.py", 6),
            ("__main__.py", 5),
            ("server.py", 4),
            ("start.py", 3),
        ]

        entry_files = []
        for file_info in files:
            if file_info["is_python"]:
                filename = file_info["path"].name
                for pattern, score in entry_patterns:
                    if filename == pattern:
                        # Читаем файл чтобы проверить наличие if __name__ == "__main__"
                        try:
                            content = file_info["full_path"].read_text(encoding='utf-8')
                            if 'if __name__ == "__main__"' in content or 'def main()' in content:
                                entry_files.append((file_info, score))
                        except:
                            entry_files.append((file_info, score - 1))

        # Сортируем по приоритету
        entry_files.sort(key=lambda x: x[1], reverse=True)
        self.stats["entry_points"] = [f[0]["path"] for f in entry_files[:3]]

    def _detect_framework(self, files: List[Dict]) -> None:
        """Определяет используемый фреймворк"""
        framework_signatures = {
            "django": ["manage.py", "urls.py", "settings.py", "wsgi.py"],
            "flask": ["app.py", "flask_app.py", "application.py"],
            "fastapi": ["main.py", "app.py", "fastapi"],
            "streamlit": ["app.py", "streamlit_app.py", "main.py"],
            "pytorch": ["model.py", "train.py", "dataset.py"],
            "tensorflow": ["model.py", "train.py", "tf_"],
        }

        # Проверяем по именам файлов
        file_names = [str(f["path"]).lower() for f in files]
        for framework, signatures in framework_signatures.items():
            for sig in signatures:
                if any(sig in name for name in file_names):
                    self.stats["framework"] = framework
                    return

        # Проверяем содержимое Python файлов
        for file_info in files[:20]:  # Проверяем первые 20 файлов
            if file_info["is_python"]:
                try:
                    content = file_info["full_path"].read_text(encoding='utf-8', errors='ignore')[:5000]
                    if "import django" in content or "from django" in content:
                        self.stats["framework"] = "django"
                        break
                    elif "import flask" in content or "from flask" in content:
                        self.stats["framework"] = "flask"
                        break
                    elif "import fastapi" in content or "from fastapi" in content:
                        self.stats["framework"] = "fastapi"
                        break
                except:
                    continue

    def _calculate_complexity(self, files: List[Dict]) -> None:
        """Оценивает сложность проекта"""
        score = 0

        # Баллы за количество файлов
        python_files = [f for f in files if f["is_python"]]
        score += min(len(python_files) * 0.5, 20)

        # Баллы за размер
        total_py_size = sum(f["size"] for f in python_files)
        score += min(total_py_size / 1024 * 0.1, 30)  # ~10 баллов за 100KB

        # Баллы за структуру (наличие папок)
        dirs = set(str(f["path"].parent) for f in python_files)
        score += min(len(dirs) * 2, 20)

        # Баллы за фреймворк
        framework_scores = {
            "django": 15,
            "fastapi": 10,
            "flask": 8,
            "pytorch": 12,
            "tensorflow": 12,
            "streamlit": 5,
            "generic": 0
        }
        score += framework_scores.get(self.stats["framework"], 0)

        self.stats["complexity_score"] = int(score)

    def _build_project_tree(self) -> None:
        """Строит визуальное дерево проекта"""
        tree_lines = []

        def add_to_tree(path: Path, prefix: str = "", is_last: bool = True):
            # Добавляем текущий элемент
            name = path.name if path != self.root_dir else self.root_dir.name
            if path.is_dir():
                icon = "📁 "
            elif path.suffix == '.py':
                icon = "🐍 "
            elif path.suffix in ['.txt', '.md']:
                icon = "📄 "
            else:
                icon = "📝 "

            tree_lines.append(f"{prefix}{'└── ' if is_last else '├── '}{icon}{name}")

            # Если это директория, добавляем ее содержимое
            if path.is_dir():
                try:
                    items = list(path.iterdir())
                    # Фильтруем скрытые и системные файлы
                    items = [item for item in items
                            if not any(excl in item.name for excl in
                                    ['.git', '__pycache__', '.venv', 'venv', '.idea'])]
                    items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

                    for i, item in enumerate(items):
                        add_to_tree(item,
                                prefix + ("    " if is_last else "│   "),
                                i == len(items) - 1)
                except:
                    pass

        # Запускаем построение
        add_to_tree(self.root_dir)
        self.stats["project_tree"] = tree_lines

class DependencyMapper:
    """Строит карту зависимостей между файлами"""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.dependency_graph = defaultdict(set)
        self.reverse_dependency = defaultdict(set)
        self.file_contents = {}

    def build_map(self, python_files: List[Path]) -> Dict:
        """Строит граф зависимостей"""
        print("🔗 Строю карту зависимостей...")

        # Сначала читаем все файлы
        for file_path in python_files:
            try:
                content = file_path.read_text(encoding='utf-8')
                self.file_contents[file_path] = content
            except:
                continue

        # Анализируем зависимости
        for file_path, content in self.file_contents.items():
            imports = self._extract_imports(content, file_path)
            for import_path in imports:
                if import_path:  # Только локальные импорты
                    self.dependency_graph[file_path].add(import_path)
                    self.reverse_dependency[import_path].add(file_path)

        # Находим корневые модули (те, от которых много зависит)
        root_modules = self._find_root_modules()

        return {
            "graph": {str(k): [str(v) for v in vs] for k, vs in self.dependency_graph.items()},
            "reverse": {str(k): [str(v) for v in vs] for k, vs in self.reverse_dependency.items()},
            "root_modules": root_modules,
            "cyclomatic_complexity": self._calculate_cyclomatic_complexity()
        }

    def _extract_imports(self, content: str, file_path: Path) -> Set[Path]:
        """Извлекает импорты из Python файла"""
        imports = set()

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_path = self._resolve_import(alias.name, file_path)
                        if module_path:
                            imports.add(module_path)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_path = self._resolve_import(node.module, file_path, node.level)
                        if module_path:
                            imports.add(module_path)
        except:
            # Fallback: простой regex поиск
            import_patterns = [
                r'^import\s+(\S+)',
                r'^from\s+(\S+)\s+import',
            ]
            for pattern in import_patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                for match in matches:
                    module_path = self._resolve_import(match, file_path)
                    if module_path:
                        imports.add(module_path)

        return imports

    def _resolve_import(self, module_name: str, source_file: Path, level: int = 0) -> Optional[Path]:
        """Преобразует импорт в путь к файлу"""
        # Игнорируем стандартные библиотеки и внешние пакеты
        if module_name.split('.')[0] in ['os', 'sys', 'json', 're', 'pathlib', 'typing',
                                        'collections', 'datetime', 'math', 'random']:
            return None

        # Обрабатываем относительные импорты
        if level > 0:
            parent_dir = source_file.parent
            for _ in range(level - 1):
                parent_dir = parent_dir.parent

            # Пробуем найти файл
            for suffix in ['', '.py']:
                possible_path = parent_dir / f"{module_name.replace('.', '/')}{suffix}"
                if possible_path.exists():
                    return possible_path

                # Пробуем как пакет (__init__.py)
                init_path = parent_dir / module_name.replace('.', '/') / "__init__.py"
                if init_path.exists():
                    return init_path
        else:
            # Абсолютный импорт относительно корня проекта
            for suffix in ['', '.py']:
                possible_path = self.root_dir / f"{module_name.replace('.', '/')}{suffix}"
                if possible_path.exists():
                    return possible_path

                # Пробуем как пакет
                init_path = self.root_dir / module_name.replace('.', '/') / "__init__.py"
                if init_path.exists():
                    return init_path

        return None

    def _find_root_modules(self) -> List[str]:
        """Находит корневые модули (наиболее важные)"""
        # Модули, от которых зависят многие другие
        dependency_scores = {}
        for module, dependents in self.reverse_dependency.items():
            score = len(dependents)
            # Бонус за то, что сам мало от кого зависит
            if module in self.dependency_graph:
                score -= len(self.dependency_graph[module]) * 0.5
            dependency_scores[module] = score

        # Сортируем по убыванию важности
        sorted_modules = sorted(dependency_scores.items(), key=lambda x: x[1], reverse=True)
        return [str(module) for module, _ in sorted_modules[:10]]

    def _calculate_cyclomatic_complexity(self) -> Dict:
        """Оценивает цикломатическую сложность проекта"""
        complexities = {}

        for file_path, content in self.file_contents.items():
            try:
                # Простая оценка сложности по количеству ветвлений
                if_count = content.count(' if ')
                for_count = content.count(' for ')
                while_count = content.count(' while ')
                and_count = content.count(' and ')
                or_count = content.count(' or ')

                complexity = 1 + if_count + for_count + while_count + (and_count + or_count) * 0.5
                complexities[str(file_path)] = int(complexity)
            except:
                complexities[str(file_path)] = 1

        return complexities


class SmartTruncator:
    """Умное обрезание кода с сохранением структуры"""

    def __init__(self):
        self.priority_patterns = [
            (r'^import ', 10),           # Импорты - самый высокий приоритет
            (r'^from ', 9),
            (r'^class ', 8),             # Классы
            (r'^def __init__', 7),       # Конструкторы
            (r'^def test_', 6),          # Тесты
            (r'^def ', 5),               # Остальные функции
            (r'@', 4),                   # Декораторы
            (r'^async def ', 7),         # Асинхронные функции
            (r'^    def ', 3),           # Методы классов
        ]

    def truncate(self, content: str, max_chars: int, file_type: str = "py") -> Tuple[str, Dict]:
        """Умное обрезание с сохранением важных частей"""
        if len(content) <= max_chars:
            return content, {"truncated": False, "original_size": len(content)}

        stats = {
            "truncated": True,
            "original_size": len(content),
            "truncated_size": max_chars,
            "preserved_sections": []
        }

        if file_type == "py":
            return self._truncate_python(content, max_chars, stats)
        elif file_type in ["txt", "md", "rst"]:
            return self._truncate_text(content, max_chars, stats)
        else:
            return content[:max_chars] + f"\n... [ФАЙЛ ОБРЕЗАН: {len(content):,} → {max_chars:,} символов] ...", stats

    def _truncate_python(self, content: str, max_chars: int, stats: Dict) -> Tuple[str, Dict]:
        """Умное обрезание Python кода"""
        lines = content.split('\n')
        important_lines = []
        regular_lines = []

        # Оцениваем важность каждой строки
        for i, line in enumerate(lines):
            priority = 0
            for pattern, score in self.priority_patterns:
                if re.match(pattern, line.strip()):
                    priority = score
                    break

            if priority >= 5:  # Высокоприоритетные строки
                important_lines.append((i, line, priority))
            else:
                regular_lines.append((i, line))

        # Сортируем важные строки по приоритету
        important_lines.sort(key=lambda x: x[2], reverse=True)

        # Собираем результат
        result_lines = []
        preserved_indices = set()

        # Добавляем первые 10 строк (обычно заголовок и импорты)
        for i in range(min(10, len(lines))):
            result_lines.append(lines[i])
            preserved_indices.add(i)

        # Добавляем важные строки
        for idx, line, _ in important_lines[:50]:  # Не более 50 важных строк
            if idx not in preserved_indices:
                result_lines.append(line)
                preserved_indices.add(idx)

        # Добавляем последние 10 строк (обычно точка входа)
        for i in range(max(0, len(lines) - 10), len(lines)):
            if i not in preserved_indices:
                result_lines.append(lines[i])
                preserved_indices.add(i)

        # Добавляем некоторые обычные строки для контекста
        for idx, line in regular_lines[:30]:  # 30 обычных строк для контекста
            if idx not in preserved_indices:
                result_lines.append(line)
                preserved_indices.add(idx)

        # Собираем результат
        result = '\n'.join(result_lines)

        # Если все еще слишком много, обрезаем жестко
        if len(result) > max_chars:
            result = result[:max_chars]

        # Добавляем индикатор обрезки
        truncation_msg = f"\n\n{'#'*60}\n# ФАЙЛ ОБРЕЗАН ДЛЯ ОПТИМИЗАЦИИ\n"
        truncation_msg += f"# Оригинал: {len(content):,} символов\n"
        truncation_msg += f"# Показано: {len(result):,} символов ({len(result)/len(content)*100:.1f}%)\n"
        truncation_msg += f"# Сохранено: {len(preserved_indices)} из {len(lines)} строк\n"
        truncation_msg += f"{'#'*60}\n"

        result = result[:max_chars - len(truncation_msg)] + truncation_msg

        stats["preserved_lines"] = len(preserved_indices)
        stats["total_lines"] = len(lines)
        stats["preserved_ratio"] = f"{len(preserved_indices)/len(lines)*100:.1f}%"

        return result, stats

    def _truncate_text(self, content: str, max_chars: int, stats: Dict) -> Tuple[str, Dict]:
        """Обрезание текстовых файлов с сохранением структуры"""
        # Для текстовых файлов берем начало и конец
        if len(content) <= max_chars:
            return content, stats

        # Берем первые 70% и последние 30% от доступного размера
        first_part = int(max_chars * 0.7)
        last_part = max_chars - first_part

        result = content[:first_part]
        result += f"\n\n... [пропущено {len(content) - first_part - last_part:,} символов] ...\n\n"
        result += content[-last_part:]

        return result, stats


class EnhancedProjectCollector:
    def __init__(self, root_dir=".", project_name=None):
        self.root_dir = Path(root_dir).resolve()
        self.project_name = project_name or self.root_dir.name

        # Получаем путь к самому сборщику
        self.collector_path = Path(__file__).resolve()

        # Инициализируем компоненты
        self.analyzer = ProjectAnalyzer(self.root_dir)
        self.truncator = SmartTruncator()
        self.dependency_mapper = None

        # Настройки - добавляем исключение для самого сборщика
        self.exclude_dirs = ["venv", "__pycache__", ".venv", ".git",
                            "test", "tests", "docs", "build", "dist",
                            "node_modules", ".pytest_cache", ".mypy_cache", "logs"]

        # Добавляем исключение для скриптов сборщика
        self.exclude_files = [
            "collect2.py",  # Имя текущего файла
        ]

        self.max_sizes = {
            "entry_points": 10000,
            "config_files": 7000,
            "important_modules": 5000,
            "regular_modules": 2000,
            "text_files": 2000,
            "data_files": 1000,
        }

    def collect_enhanced(self) -> str:
        """Основной метод сбора проекта"""
        print(f"🚀 Запускаю улучшенный сборщик для проекта: {self.project_name}")

        # 1. Анализируем проект
        stats = self.analyzer.analyze()

        # 2. Собираем Python файлы
        python_files = self._collect_python_files()

        # 3. Строим карту зависимостей
        self.dependency_mapper = DependencyMapper(self.root_dir)
        dependency_map = self.dependency_mapper.build_map(python_files)

        # 4. Генерируем отчет
        output_file = self._generate_report(stats, dependency_map, python_files)

        return output_file

    def _collect_python_files(self) -> List[Path]:
        """Собирает все Python файлы проекта, исключая сам сборщик"""
        python_files = []
        for path in self.root_dir.rglob("*.py"):
            # Проверяем исключаемые директории
            if any(excl in str(path) for excl in self.exclude_dirs):
                continue

            # Проверяем, не является ли файл самим сборщиком
            if self._is_collector_file(path):
                continue

            python_files.append(path)

        # Сортируем по важности (точки входа первыми)
        entry_points = self.analyzer.stats["entry_points"]
        def sort_key(path):
            rel_path = path.relative_to(self.root_dir)
            if str(rel_path) in entry_points:
                return (0, entry_points.index(str(rel_path)))
            elif "test" in str(rel_path).lower():
                return (2, str(rel_path))
            else:
                return (1, str(rel_path))

        python_files.sort(key=sort_key)
        return python_files

    def _is_collector_file(self, path: Path) -> bool:
        """Проверяет, является ли файл сборщиком"""
        # Сравниваем с путем к текущему файлу
        try:
            if path.resolve() == self.collector_path:
                return True
        except:
            pass

        # Проверяем по имени файла
        filename = path.name
        if filename in self.exclude_files:
            return True

        # Проверяем по содержимому (если файл содержит ключевые фразы сборщика)
        try:
            content = path.read_text(encoding='utf-8', errors='ignore')[:1000]
            collector_keywords = [
                "class EnhancedProjectCollector",
                "class ProjectAnalyzer",
                "class SmartTruncator",
                "сборщик проекта",
                "collect_enhanced",
                "ProjectCollector",
            ]
            if any(keyword in content for keyword in collector_keywords):
                return True
        except:
            pass

        return False

    def _generate_report(self, stats: Dict, dependency_map: Dict, python_files: List[Path]) -> str:
        """Генерирует полный отчет"""
        output_file = f"enhanced_project_report_{self.project_name}.txt"
        content = []

        # Заголовок
        content.append(f"{'='*80}")
        content.append(f"УЛУЧШЕННЫЙ ОТЧЕТ ПРОЕКТА: {self.project_name}")
        content.append(f"{'='*80}\n")

        # 1. Общая информация
        content.append(self._generate_summary_section(stats))

        # 2. Карта зависимостей
        content.append(self._generate_dependency_section(dependency_map))

        # 3. Анализ сложности
        content.append(self._generate_complexity_section(stats, dependency_map))

        # 4. Точки входа
        content.append(self._generate_entry_points_section(stats, python_files))

        # 5. Конфигурационные файлы
        content.append(self._generate_config_section())

        # 6. Ключевые модули (на основе зависимостей)
        content.append(self._generate_key_modules_section(dependency_map, python_files))

        # 7. Остальные файлы (кратко)
        content.append(self._generate_other_files_section())

        # 8. Рекомендации для анализа
        content.append(self._generate_recommendations_section(stats, dependency_map))

        # Записываем файл
        full_content = '\n'.join(content)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(full_content)

        # Выводим статистику
        self._print_final_stats(output_file, full_content, stats)

        return output_file

    def _generate_summary_section(self, stats: Dict) -> str:
        """Генерирует раздел с общей информацией"""
        section = []
        section.append(f"{'📊 ОБЩАЯ ИНФОРМАЦИЯ О ПРОЕКТЕ':^80}")
        section.append(f"{'─'*80}")

        section.append(f"📁 Название проекта: {self.project_name}")
        section.append(f"📂 Корневая директория: {self.root_dir}")
        section.append(f"📈 Объем проекта: {stats['total_size'] / 1024:.1f} KB")
        section.append(f"📄 Всего файлов: {stats['total_files']}")
        section.append(f"🐍 Python файлов: {stats['python_files_count']}")
        section.append(f"📊 Строк кода (Python): {stats['total_code_lines']:,}".replace(',', ' '))
        section.append(f"📈 Средний размер файла: {stats['total_code_lines'] / max(1, stats['python_files_count']):.1f} строк на файл")

        # Только если есть хотя бы один Python файл
        if stats['python_files_count'] > 0:
            section.append(f"📐 Плотность кода: {stats['total_code_lines'] / max(1, stats['total_size']/1024):.1f} строк/KB")

        section.append(f"🎯 Используемый фреймворк: {stats['framework'].upper()}")
        section.append(f"⚡ Оценка сложности: {stats['complexity_score']}/100")

        # Распределение по типам файлов
        section.append(f"\n📋 Распределение файлов по типам:")
        for ext, count in sorted(stats['file_types'].items(), key=lambda x: x[1], reverse=True)[:10]:
            if ext:  # Пропускаем пустые расширения
                section.append(f"  {ext or 'без расширения'}: {count} файлов")

        # Топ файлов по количеству строк кода (если есть Python файлы)
        if stats.get('files_most_lines') and len(stats['files_most_lines']) > 0:
            section.append(f"\n📈 Топ-5 файлов по количеству строк кода:")
            for i, file_info in enumerate(stats['files_most_lines'][:5], 1):
                section.append(f"  {i}. {file_info['path']}: {file_info['lines']:,} строк".replace(',', ' '))

        # Если есть дополнительные метрики
        if stats.get('average_complexity'):
            section.append(f"\n🔬 Дополнительные метрики:")
            section.append(f"  Средняя сложность: {stats['average_complexity']:.2f}")
        if stats.get('total_functions'):
            section.append(f"  Всего функций: {stats['total_functions']}")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_dependency_section(self, dependency_map: Dict) -> str:
        """Генерирует раздел с визуализацией проекта"""
        section = []
        section.append(f"{'🌳 ВИЗУАЛЬНОЕ ДЕРЕВО ПРОЕКТА':^80}")
        section.append(f"{'─'*80}")

        # Выводим дерево проекта
        project_tree = self.analyzer.stats.get("project_tree", [])
        if project_tree:
            section.append("\n📁 Структура каталогов:")
            section.extend(project_tree)
        else:
            section.append("\n⚠️  Дерево проекта не построено")

        # Оставляем корневые модули
        root_modules = dependency_map.get('root_modules', [])
        if root_modules:
            section.append(f"\n\n🎯 КОРНЕВЫЕ МОДУЛИ (самые важные):")
            for i, module in enumerate(root_modules[:10], 1):
                section.append(f"  {i:2d}. {module}")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_complexity_section(self, stats: Dict, dependency_map: Dict) -> str:
        """Генерирует раздел с анализом сложности"""
        section = []
        section.append(f"{'⚙️  АНАЛИЗ СЛОЖНОСТИ ПРОЕКТА':^80}")
        section.append(f"{'─'*80}")

        complexities = dependency_map.get('cyclomatic_complexity', {})
        if complexities:
            # Самые сложные файлы
            section.append(f"\n🔴 САМЫЕ СЛОЖНЫЕ ФАЙЛЫ:")
            sorted_complex = sorted(complexities.items(), key=lambda x: x[1], reverse=True)[:5]
            for file_path, complexity in sorted_complex:
                filename = Path(file_path).name
                section.append(f"  📄 {filename}: {complexity} баллов сложности")

        # Рекомендации на основе сложности
        score = stats['complexity_score']
        section.append(f"\n💡 ВЫВОДЫ:")
        if score < 30:
            section.append(f"  ✅ Проект простой, можно анализировать целиком")
        elif score < 60:
            section.append(f"  ⚠️  Проект средней сложности, фокусируйтесь на корневых модулях")
        else:
            section.append(f"  🔴 Проект сложный, анализируйте по частям")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_entry_points_section(self, stats: Dict, python_files: List[Path]) -> str:
        """Генерирует раздел с точками входа"""
        section = []
        section.append(f"{'🎯 ТОЧКИ ВХОДА В ПРОЕКТ':^80}")
        section.append(f"{'─'*80}")

        if stats['entry_points']:
            for entry_point in stats['entry_points'][:3]:  # Показываем до 3 точек входа
                entry_path = self.root_dir / entry_point
                if entry_path.exists():
                    try:
                        content = entry_path.read_text(encoding='utf-8')
                        truncated, trunc_stats = self.truncator.truncate(
                            content, self.max_sizes['entry_points'], "py"
                        )

                        section.append(f"\n📄 {entry_point}:")
                        section.append(f"{'─'*40}")
                        section.append(truncated)
                        section.append(f"{'─'*40}")

                        if trunc_stats.get('truncated'):
                            section.append(f"⚠️  Показано {trunc_stats['truncated_size']:,} из {trunc_stats['original_size']:,} символов")
                    except Exception as e:
                        section.append(f"\n❌ Ошибка чтения {entry_point}: {str(e)}")
        else:
            section.append(f"\n⚠️  Точки входа не обнаружены. Используются основные файлы:")
            for file_path in python_files[:2]:  # Берем первые 2 файла как точки входа
                rel_path = file_path.relative_to(self.root_dir)
                section.append(f"  📄 {rel_path}")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_config_section(self) -> str:
        """Генерирует раздел с конфигурационными файлами"""
        section = []
        section.append(f"{'⚙️  КОНФИГУРАЦИОННЫЕ ФАЙЛЫ':^80}")
        section.append(f"{'─'*80}")

        config_files = [
            "requirements.txt", "setup.py", "pyproject.toml",
            "config.py", "settings.py", ".env", "dockerfile", "docker-compose.yml",
            "README.md", "README.rst", "MANIFEST.in"
        ]

        found_configs = []
        for config_file in config_files:
            # Проверяем с разными регистрами и расширениями
            for path in self.root_dir.glob(f"**/{config_file}"):
                if any(excl in str(path) for excl in self.exclude_dirs):
                    continue
                found_configs.append(path)

        if found_configs:
            for config_path in found_configs[:5]:  # Ограничиваем 5 файлами
                rel_path = config_path.relative_to(self.root_dir)
                try:
                    content = config_path.read_text(encoding='utf-8', errors='ignore')
                    max_size = self.max_sizes.get('config_files', 2000)

                    if len(content) > max_size:
                        content = content[:max_size] + f"\n... [обрезка: {len(content):,} → {max_size:,} символов]"

                    section.append(f"\n📄 {rel_path}:")
                    section.append(f"{'─'*40}")
                    section.append(content[:500])  # Показываем первые 500 символов
                    section.append(f"{'─'*40}")
                except Exception as e:
                    section.append(f"\n📄 {rel_path}: [Файл пропущен: {str(e)}]")
        else:
            section.append(f"\n⚠️  Конфигурационные файлы не найдены")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_key_modules_section(self, dependency_map: Dict, python_files: List[Path]) -> str:
        """Генерирует раздел с ключевыми модулями на основе зависимостей"""
        section = []
        section.append(f"{'🔑 КЛЮЧЕВЫЕ МОДУЛИ (на основе зависимостей)':^80}")
        section.append(f"{'─'*80}")

        root_modules = dependency_map.get('root_modules', [])
        key_files = []

        # Преобразуем пути модулей в объекты Path
        for module in root_modules[:15]:  # Берем до 15 ключевых модулей
            try:
                module_path = Path(module)
                if module_path.exists():
                    key_files.append(module_path)
            except:
                pass

        # Добавляем точки входа, если их нет в ключевых
        entry_points = [self.root_dir / ep for ep in self.analyzer.stats['entry_points']]
        for ep in entry_points:
            if ep.exists() and ep not in key_files:
                key_files.append(ep)

        if key_files:
            section.append(f"\n🎯 Отобрано {len(key_files)} ключевых модулей:")

            for i, file_path in enumerate(key_files[:10], 1):  # Показываем первые 10
                rel_path = file_path.relative_to(self.root_dir)
                try:
                    content = file_path.read_text(encoding='utf-8')

                    # Определяем размер на основе важности
                    if file_path in entry_points:
                        max_size = self.max_sizes['important_modules']
                    else:
                        max_size = self.max_sizes['regular_modules']

                    truncated, trunc_stats = self.truncator.truncate(content, max_size, "py")

                    section.append(f"\n{i:2d}. 📄 {rel_path}")
                    section.append(f"{'─'*40}")
                    section.append(truncated)
                    section.append(f"{'─'*40}")

                    if trunc_stats.get('truncated'):
                        section.append(f"📊 Сохранено {trunc_stats.get('preserved_lines', '?')} строк ({trunc_stats.get('preserved_ratio', '?')})")

                except Exception as e:
                    section.append(f"\n{i:2d}. 📄 {rel_path}: [Ошибка чтения: {str(e)}]")

            if len(key_files) > 10:
                section.append(f"\n📋 ... и еще {len(key_files) - 10} ключевых модулей")
        else:
            section.append(f"\n⚠️  Ключевые модули не определены, показываю первые 5 Python файлов:")
            for i, file_path in enumerate(python_files[:5], 1):
                rel_path = file_path.relative_to(self.root_dir)
                section.append(f"  {i:2d}. {rel_path}")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_other_files_section(self) -> str:
        """Генерирует раздел с остальными файлами, исключая сборщик"""
        section = []
        section.append(f"{'📁 ПРОЧИЕ ФАЙЛЫ ПРОЕКТА':^80}")
        section.append(f"{'─'*80}")

        # Собираем все файлы (кроме уже показанных и сборщика)
        all_files = []
        for path in self.root_dir.rglob("*"):
            if path.is_file() and not any(excl in str(path) for excl in self.exclude_dirs):
                # Пропускаем Python файлы, они уже обработаны
                if path.suffix.lower() == '.py':
                    continue

                # Пропускаем файл сборщика
                if self._is_collector_file(path):
                    continue

                all_files.append(path)

        # Группируем по типам
        file_groups = defaultdict(list)
        for file_path in all_files[:100]:  # Ограничиваем 100 файлами
            ext = file_path.suffix.lower()
            file_groups[ext or 'без расширения'].append(file_path)

        section.append(f"\n📊 Всего прочих файлов: {len(all_files)}")
        section.append(f"📋 Группировка по типам:\n")

        for ext, files in sorted(file_groups.items()):
            if ext in ['.pyc', '.pyo', '.so', '.dll']:  # Пропускаем бинарные файлы
                continue

            section.append(f"  {ext or 'без расширения'}: {len(files)} файлов")
            for file_path in files[:3]:  # Показываем по 3 файла каждого типа
                rel_path = file_path.relative_to(self.root_dir)
                section.append(f"      📄 {rel_path}")
            if len(files) > 3:
                section.append(f"      ... и еще {len(files) - 3} файлов")

        section.append(f"\n")
        return '\n'.join(section)

    def _generate_recommendations_section(self, stats: Dict, dependency_map: Dict) -> str:
        """Генерирует рекомендации для анализа"""
        section = []
        section.append(f"{'💡 РЕКОМЕНДАЦИИ ДЛЯ АНАЛИЗА НЕЙРОСЕТЬЮ':^80}")
        section.append(f"{'─'*80}")

        framework = stats['framework']
        complexity = stats['complexity_score']

        section.append(f"\n🎯 СТРАТЕГИЯ АНАЛИЗА:")

        if framework == "django":
            section.append(f"  1. Начните с settings.py и urls.py")
            section.append(f"  2. Изучите структуру приложений в папке apps/")
            section.append(f"  3. Проверьте models.py для структуры данных")
            section.append(f"  4. Проанализируйте views.py и формы")
        elif framework == "flask":
            section.append(f"  1. Изучите app.py или application.py")
            section.append(f"  2. Проверьте структуру Blueprints")
            section.append(f"  3. Проанализируйте модели и базу данных")
        elif framework == "fastapi":
            section.append(f"  1. Начните с main.py и роутеров")
            section.append(f"  2. Изучите схемы Pydantic в schemas/")
            section.append(f"  3. Проверьте зависимости в dependencies/")
        else:
            section.append(f"  1. Начните с точек входа (см. выше)")
            section.append(f"  2. Изучите корневые модули из карты зависимостей")
            section.append(f"  3. Проанализируйте конфигурационные файлы")

        section.append(f"\n🔍 ФОКУС НА:")

        # Рекомендации на основе сложности
        if complexity > 70:
            section.append(f"  • Архитектурные паттерны")
            section.append(f"  • Взаимодействие между модулями")
            section.append(f"  • Основные абстракции")
        elif complexity > 40:
            section.append(f"  • Основной поток выполнения")
            section.append(f"  • Ключевые функции и классы")
            section.append(f"  • Конфигурация проекта")
        else:
            section.append(f"  • Полный код проекта")
            section.append(f"  • Все зависимости")
            section.append(f"  • Тесты и документация")

        # Специфичные рекомендации
        root_modules = dependency_map.get('root_modules', [])
        if root_modules:
            section.append(f"\n🎯 ПРИОРИТЕТНЫЕ МОДУЛИ:")
            for i, module in enumerate(root_modules[:5], 1):
                module_name = Path(module).name
                section.append(f"  {i}. {module_name}")

        section.append(f"\n⚠️  ОГРАНИЧЕНИЯ:")
        section.append(f"  • Python файлы обрезаны для оптимизации")
        section.append(f"  • Показаны только ключевые модули")
        section.append(f"  • Нет бинарных и скомпилированных файлов")

        section.append(f"\n{'='*80}")
        section.append(f"📅 Отчет сгенерирован: {self._get_timestamp()}")
        section.append(f"{'='*80}")

        return '\n'.join(section)

    def _get_timestamp(self) -> str:
        """Возвращает текущую дату и время"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _print_final_stats(self, output_file: str, content: str, stats: Dict) -> None:
        """Выводит финальную статистику"""
        print(f"\n{'='*60}")
        print(f"✅ УЛУЧШЕННЫЙ ОТЧЕТ СОЗДАН!")
        print(f"{'='*60}")
        print(f"📁 Проект: {self.project_name}")
        print(f"📄 Файл отчета: {output_file}")
        print(f"📊 Размер отчета: {len(content):,} символов")
        print(f"🐍 Python файлов: {stats['file_types'].get('.py', 0)}")
        print(f"🎯 Фреймворк: {stats['framework']}")
        print(f"⚡ Сложность: {stats['complexity_score']}/100")
        print(f"🔗 Корневых модулей: {len(stats.get('entry_points', []))}")
        print(f"{'='*60}")


def main():
    """Основная функция для запуска"""
    import argparse

    parser = argparse.ArgumentParser(description='Улучшенный сборщик проекта для нейросетей')
    parser.add_argument('--path', default='.', help='Путь к проекту (по умолчанию: текущая директория)')
    parser.add_argument('--name', help='Имя проекта (по умолчанию: имя папки)')
    parser.add_argument('--output', help='Имя выходного файла')

    args = parser.parse_args()

    # Создаем сборщик
    collector = EnhancedProjectCollector(root_dir=args.path, project_name=args.name)

    # Запускаем сборку
    output_file = collector.collect_enhanced()

    # Показываем полный путь
    abs_path = Path(output_file).resolve()
    print(f"\n📋 ФАЙЛ СОХРАНЕН: {abs_path}")
    print(f"\n✨ Готово! Проект собран и проанализирован.")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()