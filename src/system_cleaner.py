import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List

try:
    import winreg  # Only available on Windows
    WINDOWS = True
except ImportError:
    WINDOWS = False


class SelectiveFolderCleaner:
    def __init__(self, dry_run=True):
        """
        dry_run=True: показывает, что было бы удалено, ничего не трогая
        dry_run=False: реально удаляет (осторожно!)
        """
        self.dry_run = dry_run
        self.deleted_files = 0
        self.deleted_folders = 0
        self.failed_count = 0
        self.results = []

    def clean_folder(self, folder_path: str, keep_folder: Optional[str] = None,
                      keep_file: Optional[str] = None, recursive_delete=True):
        """
        Удаляет всё содержимое папки, кроме указанной подпапки и файла.
        """
        folder_path = Path(folder_path)
        if not folder_path.exists():
            print(f"❌ Папка не найдена: {folder_path}\n")
            return
        if not folder_path.is_dir():
            print(f"❌ Это не папка: {folder_path}\n")
            return

        print(f"📁 Целевая папка: {folder_path}")
        print(f"🔒 Защищённая папка: {keep_folder if keep_folder else 'НЕТ'}")
        print(f"🔒 Защищённый файл: {keep_file if keep_file else 'НЕТ'}")
        print(f"Режим: {'ПРОСМОТР (dry run)' if self.dry_run else 'РЕАЛЬНОЕ УДАЛЕНИЕ'}\n")
        print("=" * 60)

        items = list(folder_path.iterdir())
        if not items:
            print("ℹ️  Папка уже пуста\n")
            return

        for item in items:
            if item.is_file():
                if keep_file and item.name.lower() == keep_file.lower():
                    # точное сравнение полного имени файла (с расширением),
                    # чтобы "steam.exe" защищал ТОЛЬКО steam.exe, а не steam.dll и т.п.
                    print(f"🔒 Пропускаю файл (защищён): {item.name}")
                    self.results.append(f"PROTECTED FILE: {item.name}")
                else:
                    self._delete_file(item)
            elif item.is_dir():
                if keep_folder and item.name.lower() == keep_folder.lower():
                    print(f"🔒 Пропускаю папку (защищена): {item.name}")
                    self.results.append(f"PROTECTED FOLDER: {item.name}")
                else:
                    self._delete_folder(item, recursive_delete)

        self._print_summary()

    def _delete_file(self, file_path: Path):
        try:
            if self.dry_run:
                print(f"🗑️  [DRY RUN] Удалил бы файл: {file_path.name}")
                self.results.append(f"Would delete FILE: {file_path.name}")
            else:
                os.chmod(file_path, 0o777)
                file_path.unlink()
                print(f"✓ Удалён файл: {file_path.name}")
                self.results.append(f"Deleted FILE: {file_path.name}")
            self.deleted_files += 1
        except PermissionError:
            print(f"❌ Доступ запрещён: {file_path.name}")
            self.failed_count += 1
        except Exception as e:
            print(f"❌ Не удалось удалить {file_path.name}: {e}")
            self.failed_count += 1

    def _delete_folder(self, folder_path: Path, recursive=True):
        try:
            if recursive:
                if self.dry_run:
                    item_count = sum(1 for _ in folder_path.rglob('*'))
                    print(f"🗑️  [DRY RUN] Удалил бы папку и {item_count} объектов: {folder_path.name}")
                    self.results.append(f"Would delete FOLDER: {folder_path.name} ({item_count} items)")
                else:
                    for item in folder_path.rglob('*'):
                        if item.is_file():
                            os.chmod(item, 0o777)
                    shutil.rmtree(folder_path)
                    print(f"✓ Удалена папка (рекурсивно): {folder_path.name}")
                    self.results.append(f"Deleted FOLDER (recursive): {folder_path.name}")
                self.deleted_folders += 1
            else:
                if not any(folder_path.iterdir()):
                    if self.dry_run:
                        print(f"🗑️  [DRY RUN] Удалил бы пустую папку: {folder_path.name}")
                    else:
                        folder_path.rmdir()
                        print(f"✓ Удалена пустая папка: {folder_path.name}")
                    self.deleted_folders += 1
                else:
                    print(f"⚠️  Пропускаю непустую папку (recursive=False): {folder_path.name}")
        except PermissionError:
            print(f"❌ Доступ запрещён: {folder_path.name}")
            self.failed_count += 1
        except Exception as e:
            print(f"❌ Не удалось удалить папку {folder_path.name}: {e}")
            self.failed_count += 1

    def _print_summary(self):
        print("=" * 60)
        print(f"\n📊 Итог:")
        print(f"  Удалено файлов: {self.deleted_files}")
        print(f"  Удалено папок: {self.deleted_folders}")
        print(f"  Ошибок: {self.failed_count}")
        print(f"  Режим: {'DRY RUN' if self.dry_run else 'РЕАЛЬНОЕ УДАЛЕНИЕ'}\n")

    def save_results(self, output_file: str = "cleanup_results.txt"):
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 60 + "\nFOLDER CLEANUP RESULTS\n" + "=" * 60 + "\n\n")
                for result in self.results:
                    f.write(result + "\n")
                f.write("\n" + "=" * 60 + "\n")
                f.write(f"Files deleted: {self.deleted_files}\n")
                f.write(f"Folders deleted: {self.deleted_folders}\n")
                f.write(f"Failed: {self.failed_count}\n")
            print(f"✓ Результаты сохранены: {output_file}")
        except Exception as e:
            print(f"❌ Не удалось сохранить результаты: {e}")


# ============================================================
# РЕЕСТР: поиск и удаление разделов/значений с valve/dota/steam
# ============================================================
class RegistryCleaner:
    """
    Ищет в реестре Windows ключи и значения, содержащие в имени
    подстроки из match_list (по умолчанию: valve, dota, steam),
    и по подтверждению удаляет их.

    ВНИМАНИЕ:
    - Работает только на Windows (нужен модуль winreg).
    - Для HKEY_LOCAL_MACHINE нужны права администратора.
    - Удаление ключей необратимо через сам скрипт — только через
      восстановление из бэкапа .reg, который этот класс делает
      автоматически перед реальным удалением.
    - Слишком широкое совпадение (например, просто "steam") может
      задеть разделы, не относящиеся к игре/лаунчеру. Проверяйте
      dry-run отчёт перед реальным запуском.
    """

    # Разделы, которые обычно имеет смысл проверять для приложений.
    # HKEY_USERS обрабатывается отдельно в scan(), т.к. под ним лежит
    # не единая ветка, а профиль каждого пользователя по SID.
    DEFAULT_ROOTS = [
        (winreg.HKEY_CURRENT_USER, r"Software") if WINDOWS else None,
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE") if WINDOWS else None,
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node") if WINDOWS else None,
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM") if WINDOWS else None,  # <-- Добавлено
        (winreg.HKEY_CLASSES_ROOT, r"") if WINDOWS else None,
    ]

    HIVE_NAMES = {
        "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
        "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
        "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
        "HKEY_USERS": winreg.HKEY_USERS,
    } if WINDOWS else {}

    def __init__(self, match_list: Optional[List[str]] = None, dry_run=True,
                 scan_all_user_profiles=True):
        if not WINDOWS:
            raise RuntimeError("RegistryCleaner работает только на Windows.")
        self.match_list = [m.lower() for m in (match_list or ["valve", "dota", "steam"])]
        self.dry_run = dry_run
        self.scan_all_user_profiles = scan_all_user_profiles
        self.found_keys = []       # список (hive, путь_раздела) на удаление
        self.found_values = []     # список (hive, путь_раздела, имя_значения)
        self.failed = []

    def _matches(self, name: str) -> bool:
        name_l = name.lower()
        return any(m in name_l for m in self.match_list)

    def backup_matches_to_reg(self, output_file="registry_backup.reg"):
        """
        Экспортирует найденные разделы в .reg файл через reg.exe,
        чтобы их можно было восстановить двойным щелчком при необходимости.
        Делайте это ПЕРЕД реальным удалением.
        """
        if not self.found_keys:
            print("ℹ️  Сначала запустите scan(), нечего бэкапить.")
            return
        for i, (hive, key_path) in enumerate(self.found_keys):
            full_path = f"{self._hive_name(hive)}\\{key_path}" if key_path else self._hive_name(hive)
            out = f"{output_file}.{i}.reg"
            try:
                subprocess.run(["reg", "export", full_path, out, "/y"],
                                check=True, capture_output=True)
                print(f"💾 Бэкап раздела сохранён: {out}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Не удалось сделать бэкап {full_path}: {e.stderr.decode(errors='ignore')}")

    def _hive_name(self, hive):
        for name, val in self.HIVE_NAMES.items():
            if val == hive:
                return name
        return str(hive)

    def scan(self, roots=None):
        """
        Рекурсивно обходит указанные корневые разделы (или DEFAULT_ROOTS,
        плюс все профили пользователей под HKEY_USERS, если
        scan_all_user_profiles=True) и собирает все ключи/значения,
        чьё имя содержит одну из подстрок.
        """
        roots = list(roots) if roots is not None else [r for r in self.DEFAULT_ROOTS if r is not None]

        self.found_keys.clear()
        self.found_values.clear()

        for hive, base_path in roots:
            self._scan_recursive(hive, base_path)

        if self.scan_all_user_profiles:
            for sid in self._enum_user_profile_sids():
                self._scan_recursive(winreg.HKEY_USERS, sid)

        print("=" * 60)
        print(f"🔎 Найдено разделов: {len(self.found_keys)}")
        print(f"🔎 Найдено значений: {len(self.found_values)}")
        print("=" * 60)
        for hive, k in self.found_keys:
            print(f"  [KEY]   {self._hive_name(hive)}\\{k}")
        for hive, k, v in self.found_values:
            print(f"  [VALUE] {self._hive_name(hive)}\\{k}  ->  {v}")

    def _enum_user_profile_sids(self):
        """Возвращает список SID верхнего уровня под HKEY_USERS (по одному на профиль)."""
        sids = []
        try:
            key = winreg.OpenKey(winreg.HKEY_USERS, "", 0, winreg.KEY_READ)
        except OSError:
            return sids
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
                # Пропускаем служебные *_Classes ветки — они дублируют HKCR для профиля
                if not name.endswith("_Classes"):
                    sids.append(name)
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)
        return sids

    def _scan_recursive(self, hive, path):
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_READ)
        except OSError:
            return  # нет доступа или раздела не существует

        try:
            # Проверяем значения текущего раздела
            i = 0
            while True:
                try:
                    value_name, value_data, value_type = winreg.EnumValue(key, i)
                    # Проверяем имя параметра
                    if self._matches(value_name):
                        self.found_values.append((hive, path, value_name))
                    # Проверяем значение параметра (только если это строковый тип)
                    elif value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value_data, str):
                        if self._matches(value_data):
                            self.found_values.append((hive, path, value_name))
                    i += 1
                except OSError:
                    break

            # Обходим подразделы
            i = 0
            subkeys = []
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkeys.append(subkey_name)
                    i += 1
                except OSError:
                    break
        finally:
            winreg.CloseKey(key)

        for subkey_name in subkeys:
            full_path = f"{path}\\{subkey_name}" if path else subkey_name
            if self._matches(subkey_name):
                self.found_keys.append((hive, full_path))
                # Если сам раздел совпал — всё его поддерево удалится вместе
                # с ним при рекурсивном удалении, поэтому вглубь не идём.
            else:
                self._scan_recursive(hive, full_path)

    def delete_found(self):
        """
        Реально удаляет все найденные при scan() разделы (рекурсивно)
        и значения. Требует dry_run=False и явного вызова.
        """
        if self.dry_run:
            print("ℹ️  dry_run=True — ничего не удаляю. Создайте объект с dry_run=False для реального удаления.")
            return

        for hive, key_path in self.found_keys:
            try:
                self._delete_key_recursive(hive, key_path)
                print(f"✓ Удалён раздел: {self._hive_name(hive)}\\{key_path}")
            except Exception as e:
                print(f"❌ Не удалось удалить раздел {self._hive_name(hive)}\\{key_path}: {e}")
                self.failed.append(f"{self._hive_name(hive)}\\{key_path}")

        for hive, key_path, value_name in self.found_values:
            try:
                k = winreg.OpenKey(hive, key_path, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(k, value_name)
                winreg.CloseKey(k)
                print(f"✓ Удалено значение: {self._hive_name(hive)}\\{key_path} -> {value_name}")
            except Exception as e:
                print(f"❌ Не удалось удалить значение {self._hive_name(hive)}\\{key_path}->{value_name}: {e}")
                self.failed.append(f"{self._hive_name(hive)}\\{key_path}::{value_name}")

    def _delete_key_recursive(self, hive, path):
        try:
            key = winreg.OpenKey(hive, path, 0, winreg.KEY_ALL_ACCESS)
        except OSError:
            return
        subkeys = []
        i = 0
        while True:
            try:
                subkeys.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
        winreg.CloseKey(key)

        for sk in subkeys:
            self._delete_key_recursive(hive, f"{path}\\{sk}")

        winreg.DeleteKey(hive, path)


# ===== ПРИМЕР ИСПОЛЬЗОВАНИЯ =====
if __name__ == "__main__":

    # --- 1) Очистка папки Steam, кроме steamapps и steam(.exe) ---
    # print("\n### ШАГ 1: Очистка папки (предпросмотр) ###\n")
    # folder_cleaner = SelectiveFolderCleaner(dry_run=True)
    # folder_cleaner.clean_folder(
    #     folder_path=r"C:\Program Files (x86)\Steam",
    #     keep_folder="steamapps",
    #     keep_file="steam.exe",          # защитит steam.exe (сравнение без расширения)
    #     recursive_delete=True
    # )
    folder_cleaner_real = SelectiveFolderCleaner(dry_run=False)
    folder_cleaner_real.clean_folder(
        folder_path=r"C:\Program Files (x86)\Steam",
        keep_folder="steamapps",
        keep_file="steam.exe",
        recursive_delete=True
    )

    # --- 2) Поиск и (по желанию) удаление записей реестра ---
    if WINDOWS:
        # print("\n### ШАГ 2: Сканирование реестра (valve/dota/steam) ###\n")
        # print("Кусты: HKCU\\Software, HKLM\\SOFTWARE (+WOW6432Node), HKEY_CLASSES_ROOT, HKEY_USERS (все профили)\n")
        # scan_all_user_profiles=True (по умолчанию) — обойдёт HKEY_USERS для каждого SID.
        # Для HKLM и части HKEY_USERS нужны права администратора.
        reg_cleaner = RegistryCleaner(match_list=["valve", "dota", "steam"], dry_run=True)
        reg_cleaner.scan()

        # Обязательно сделайте бэкап перед реальным удалением:
        # reg_cleaner.backup_matches_to_reg("steam_registry_backup")

        # Реальное удаление — только после ручной проверки списка выше:
        reg_cleaner_real = RegistryCleaner(match_list=["valve", "dota", "steam"], dry_run=False)
        reg_cleaner_real.found_keys = reg_cleaner.found_keys
        reg_cleaner_real.found_values = reg_cleaner.found_values
        reg_cleaner_real.delete_found()
    else:
        print("\nℹ️  Модуль реестра доступен только при запуске на Windows.")