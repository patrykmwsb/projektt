import os
import json
import shutil
import subprocess
import sys 

# --- Importy PyQt6 ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QLabel, QLineEdit, QComboBox, QPushButton, QGroupBox, QListWidget,
    QMessageBox, QTextEdit, QDialog, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtGui import QPalette, QColor, QFont # Dodano QFont
from PyQt6.QtCore import Qt

# --- Ustalenie Ścieżki Aplikacji (dla .py i .exe) ---
if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    try:
        application_path = os.path.dirname(os.path.abspath(__file__))
    except NameError: 
         application_path = os.getcwd()

APP_DIR = application_path 

# --- Stałe Globalne ---
LOCAL_KEYS_BASE_DIR_NAME = "generated_keys_storage"
LOCAL_KEYS_STORAGE_DIR = os.path.join(APP_DIR, LOCAL_KEYS_BASE_DIR_NAME)
LOCAL_CONFIG_FILENAME = "config" # Zmieniona nazwa
LOCAL_CONFIG_FILE_PATH = os.path.join(LOCAL_KEYS_STORAGE_DIR, LOCAL_CONFIG_FILENAME)
KEYS_DB = os.path.join(APP_DIR, "keys_db.json")
CONFIG_PATH = os.path.expanduser("~/.ssh/config")

# --- Kolory dla Ciemnego Motywu (używane w QPalette) ---
DARK_COLOR = QColor(45, 45, 45)          # Ciemnoszary dla tła okna
DISABLED_COLOR = QColor(127, 127, 127)   # Szary dla nieaktywnych elementów
DARK_WIDGET_BG_COLOR = QColor(60, 60, 60) # Ciemniejszy dla tła widgetów jak Entry
LIGHT_FG_COLOR = QColor(220, 220, 220)   # Jasny dla tekstu
HIGHLIGHT_COLOR = QColor(0, 120, 215)    # Niebieski dla zaznaczenia

# --- Funkcje Pomocnicze ---
def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# --- Funkcje Logiki Aplikacji (backend - bez zmian) ---
# ... (wszystkie funkcje od ensure_db do show_local_config_file pozostają bez zmian) ...
def ensure_db():
    ensure_dir(APP_DIR) 
    if not os.path.exists(KEYS_DB):
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump({}, f) 

def update_local_config_file():
    ensure_dir(LOCAL_KEYS_STORAGE_DIR) 
    ensure_db() 
    try: 
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys_metadata = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"BŁĄD: Nie można odczytać bazy danych kluczy '{KEYS_DB}' przy aktualizacji lokalnego configa: {e}")
        return False 

    lines = [] 
    active_local_entries = 0
    for alias, data in keys_metadata.items():
        if not data.get("in_ssh_dir", False) and data.get("path") and LOCAL_KEYS_STORAGE_DIR in data.get("path"):
            local_key_path = data.get("path") 
            config_host = data.get("config_host_alias")
            if not config_host: 
                 host_short_name = data.get('host', 'unknown').split('.')[0]
                 config_host = f"{host_short_name}-{alias}"
            
            identity_file_local_abs_path = local_key_path.replace("\\", "/") 
            lines.append(f"Host {config_host}")
            lines.append(f"  HostName {data.get('host', 'unknown_host.com')}")
            lines.append(f"  User git")
            lines.append(f"  IdentityFile {identity_file_local_abs_path}") 
            lines.append(f"  IdentitiesOnly yes")
            lines.append("")
            active_local_entries += 1
    
    try:
        with open(LOCAL_CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if active_local_entries > 0:
            print(f"INFO: Lokalny plik konfiguracyjny '{LOCAL_CONFIG_FILENAME}' zaktualizowany. Liczba wpisów: {active_local_entries}")
        else:
            print(f"INFO: Lokalny plik konfiguracyjny '{LOCAL_CONFIG_FILENAME}' jest pusty (brak kluczy lokalnych).")
        return True 
    except IOError as e:
        print(f"BŁĄD: Nie można zapisać lokalnego pliku konfiguracyjnego '{LOCAL_CONFIG_FILE_PATH}': {e}")
        return False 


def generate_key(email, host, alias, parent_widget=None): 
    if not email or not host or not alias:
        if parent_widget: QMessageBox.warning(parent_widget, "Brak danych", "E-mail, Host i Alias są wymagane.")
        return None 
    
    ensure_db()
    ensure_dir(LOCAL_KEYS_STORAGE_DIR)

    local_key_path = os.path.join(LOCAL_KEYS_STORAGE_DIR, alias) 
    
    if os.path.exists(local_key_path) or os.path.exists(local_key_path + ".pub"):
        reply = QMessageBox.StandardButton.No # Domyślna odpowiedź, jeśli parent_widget nie istnieje
        if parent_widget:
             reply = QMessageBox.question(parent_widget, "Potwierdzenie", 
                                         f"Plik klucza '{alias}' lub '{alias}.pub' już istnieje w folderze '{LOCAL_KEYS_BASE_DIR_NAME}'. Czy chcesz go nadpisać?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return f"Generowanie klucza '{alias}' anulowane."
        else:
            try: 
                if os.path.exists(local_key_path): os.remove(local_key_path)
                if os.path.exists(local_key_path + ".pub"): os.remove(local_key_path + ".pub")
            except OSError as e:
                if parent_widget: QMessageBox.critical(parent_widget, "Błąd usuwania", f"Nie można usunąć istniejącego pliku klucza: {e}")
                return None 

    comment_string_ssh = f"email:{email} alias:{alias} host:{host}"
    cmd = ["ssh-keygen", "-t", "ed25519", "-C", comment_string_ssh, "-f", local_key_path, "-N", ""]
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo) 
    except subprocess.CalledProcessError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd ssh-keygen", f"Błąd wykonania ssh-keygen:\n{e.stderr}")
        return None
    except FileNotFoundError:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd ssh-keygen", "Nie znaleziono polecenia 'ssh-keygen'.\nUpewnij się, że jest zainstalowane (np. z Git) i dostępne w PATH.")
        return None
    except Exception as e: 
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd subprocess", f"Niespodziewany błąd podczas uruchamiania ssh-keygen:\n{e}")
        return None


    public_key_file_path = local_key_path + ".pub"
    host_short_name = host.split('.')[0] 
    key_name_metadata = f"id_ed25519_{host_short_name}-{alias}" 
    metadata_line_for_pub_key = f"# key_name: {key_name_metadata}\n" 

    try:
        with open(public_key_file_path, "r+", encoding="utf-8") as f_pub:
            original_pub_key_content = f_pub.read()
            f_pub.seek(0, 0)
            f_pub.write(metadata_line_for_pub_key + original_pub_key_content)
    except IOError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu .pub", f"Błąd podczas dodawania metadanych do pliku {public_key_file_path}:\n{e}")
        return None

    try: 
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
         keys = {} 

    config_host_alias = f"{host_short_name}-{alias}" 
    keys[alias] = {
        "email": email, 
        "host": host, 
        "path": local_key_path, 
        "config_host_alias": config_host_alias, 
        "in_ssh_dir": False 
    }
    try:
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=4, ensure_ascii=False) 
    except IOError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu DB", f"Nie można zapisać bazy danych {KEYS_DB}:\n{e}")
        return None 

    if not update_local_config_file(): 
         if parent_widget: QMessageBox.warning(parent_widget, "Ostrzeżenie", f"Nie udało się zaktualizować lokalnego pliku {LOCAL_CONFIG_FILENAME}.")
         
    return f"Klucz '{alias}' wygenerowany w '{LOCAL_KEYS_BASE_DIR_NAME}'.\nDodano do .pub: {metadata_line_for_pub_key.strip()}"

def move_key_to_ssh(alias, parent_widget=None): 
    ssh_dir = os.path.expanduser("~/.ssh") 
    os.makedirs(ssh_dir, exist_ok=True)
    ensure_db()

    try:
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd Bazy Danych", f"Nie można odczytać pliku {KEYS_DB}.")
        return None 

    if alias not in keys:
        if parent_widget: QMessageBox.warning(parent_widget, "Nie znaleziono aliasu", f"Alias '{alias}' nie istnieje w bazie.")
        return None
    
    entry = keys[alias]
    ssh_key_dest_path_base = os.path.join(ssh_dir, alias) 
    if entry.get("in_ssh_dir", False) and os.path.exists(ssh_key_dest_path_base):
        reply = QMessageBox.StandardButton.No
        if parent_widget:
             reply = QMessageBox.question(parent_widget, "Potwierdzenie", 
                                          f"Klucz '{alias}' jest już prawdopodobnie w ~/.ssh. Czy chcesz spróbować przenieść/skonfigurować ponownie?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                          QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return f"Operacja dla '{alias}' anulowana."

    local_key_path_base = entry.get("path", os.path.join(LOCAL_KEYS_STORAGE_DIR, alias))
    if LOCAL_KEYS_STORAGE_DIR not in local_key_path_base:
         local_key_path_base = os.path.join(LOCAL_KEYS_STORAGE_DIR, alias) 

    local_key_priv_path = local_key_path_base
    local_key_pub_path = local_key_path_base + ".pub"

    if not os.path.exists(local_key_priv_path) or not os.path.exists(local_key_pub_path):
        if parent_widget: QMessageBox.critical(parent_widget, "Brak plików źródłowych", f"Brak plików klucza '{alias}' w folderze '{LOCAL_KEYS_BASE_DIR_NAME}'. Wygeneruj je najpierw.")
        return None

    try:
        shutil.copy2(local_key_priv_path, ssh_key_dest_path_base)
        shutil.copy2(local_key_pub_path, ssh_key_dest_path_base + ".pub")
        os.chmod(ssh_key_dest_path_base, 0o600)
        os.chmod(ssh_key_dest_path_base + ".pub", 0o644)
    except Exception as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd kopiowania", f"Błąd podczas kopiowania plików klucza '{alias}':\n{e}")
        return None

    keys[alias]["path"] = ssh_key_dest_path_base 
    keys[alias]["in_ssh_dir"] = True
    try:
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=4, ensure_ascii=False)
    except IOError as e:
         if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu DB", f"Nie można zaktualizować bazy danych {KEYS_DB} po przeniesieniu:\n{e}")
         return f"Klucze '{alias}' skopiowane, ale wystąpił błąd aktualizacji bazy danych!"

    
    update_config_file(parent_widget) 
    update_local_config_file() 
    return f"Klucz '{alias}' został skopiowany do ~/.ssh i konfiguracja zaktualizowana."

def delete_key(alias, parent_widget=None): 
    ensure_db()
    try:
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd Bazy Danych", f"Nie można odczytać pliku {KEYS_DB}.")
        return None

    if alias not in keys:
        if parent_widget: QMessageBox.warning(parent_widget, "Nie znaleziono aliasu", f"Alias '{alias}' nie istnieje w bazie.")
        return None

    entry = keys[alias]
    paths_to_delete = set()
    
    local_key_in_storage_path = os.path.join(LOCAL_KEYS_STORAGE_DIR, alias)
    paths_to_delete.add(local_key_in_storage_path)

    if entry.get("in_ssh_dir"):
        paths_to_delete.add(os.path.join(os.path.expanduser("~/.ssh"), alias))
    if "path" in entry and os.path.dirname(entry["path"]) == APP_DIR: 
        paths_to_delete.add(entry["path"])

    files_deleted_count = 0
    for key_path_base in paths_to_delete:
        try:
            if os.path.exists(key_path_base):
                os.remove(key_path_base)
                files_deleted_count += 1
            if os.path.exists(key_path_base + ".pub"):
                os.remove(key_path_base + ".pub")
                files_deleted_count += 1
        except OSError as e:
            print(f"Ostrzeżenie: Nie udało się usunąć pliku {key_path_base} lub {key_path_base}.pub: {e}")

    del keys[alias]
    try:
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=4, ensure_ascii=False)
    except IOError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu DB", f"Nie można zaktualizować bazy danych {KEYS_DB} po usunięciu:\n{e}")
        return f"Wystąpił błąd aktualizacji bazy danych! Pliki mogły zostać usunięte."

    update_config_file(parent_widget) 
    update_local_config_file() 
    if files_deleted_count > 0:
        return f"Klucz '{alias}' (pliki i wpis) usunięty."
    else:
        return f"Wpis dla klucza '{alias}' usunięty z bazy i konfiguracji (pliki nie znalezione)."

def update_config_file(parent_widget=None): 
    ensure_db()
    try:
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys_metadata = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"BŁĄD: Nie można odczytać bazy danych kluczy '{KEYS_DB}' przy aktualizacji ~/.ssh/config: {e}")
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd Bazy Danych", f"Nie można odczytać pliku {KEYS_DB}. Aktualizacja ~/.ssh/config przerwana.")
        return False

    lines = [] 
    active_config_entries = 0
    for alias, data in keys_metadata.items():
        if data.get("in_ssh_dir", False) and data.get("path") and os.path.expanduser("~/.ssh") in data.get("path"): 
            config_host = data.get("config_host_alias")
            if not config_host: 
                 host_short_name = data.get('host', 'unknown').split('.')[0]
                 config_host = f"{host_short_name}-{alias}"

            identity_file_in_ssh_config = os.path.join("~/.ssh", alias).replace("\\", "/") 
            
            lines.append(f"Host {config_host}") 
            lines.append(f"  HostName {data.get('host', 'unknown_host.com')}") 
            lines.append(f"  User git")
            lines.append(f"  IdentityFile {identity_file_in_ssh_config}") 
            lines.append(f"  IdentitiesOnly yes")
            lines.append("")
            active_config_entries +=1
    
    ensure_dir(os.path.expanduser("~/.ssh")) 
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if os.name != 'nt': 
            os.chmod(CONFIG_PATH, 0o600)
        
        if active_config_entries > 0:
            print(f"INFO: Plik ~/.ssh/config zaktualizowany. Liczba aktywnych wpisów: {active_config_entries}")
        else:
            print(f"INFO: Plik ~/.ssh/config jest teraz pusty (lub został wyczyszczony), ponieważ żadne zarządzane klucze nie są w ~/.ssh.")
        return True

    except IOError as e:
        if parent_widget: QMessageBox.showwarning(parent_widget, "Błąd zapisu config", f"Nie można zapisać pliku {CONFIG_PATH}:\n{e}\nSprawdź uprawnienia.")
        return False


def show_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Plik {CONFIG_PATH} nie istnieje."

def show_keys_json():
    ensure_db()
    try:
      with open(KEYS_DB, "r", encoding="utf-8") as f:
          return json.dumps(json.load(f), indent=4, ensure_ascii=False)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return f"Błąd odczytu pliku bazy danych {KEYS_DB}:\n{e}"


def show_local_config_file():
    ensure_dir(LOCAL_KEYS_STORAGE_DIR) 
    try:
        with open(LOCAL_CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Lokalny plik konfiguracyjny '{LOCAL_CONFIG_FILENAME}' nie istnieje (folder: '{LOCAL_KEYS_BASE_DIR_NAME}').\nZostanie utworzony po wygenerowaniu pierwszego klucza."


# --- Klasa Okna Dialogowego do Wyświetlania Tekstu ---
class TextViewerDialog(QDialog):
    def __init__(self, title, content, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400) 

        self.layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(content)
        # Usunięto setStyleSheet - użyje globalnej palety
        self.layout.addWidget(self.text_edit)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        self.layout.addWidget(self.button_box)

# --- Główna Klasa Aplikacji GUI (PyQt6) ---
class SSHKeyManagerApp(QWidget): 
    def __init__(self):
        super().__init__()
        self.init_ui()
        # Przeniesiono ładowanie kluczy po ustawieniu palety w __main__
        # self.load_and_display_keys() 

    def init_ui(self):
        self.setWindowTitle("Menedżer Kluczy SSH (PyQt6 - Prosty Ciemny)")
        self.setGeometry(200, 200, 850, 600) 

        main_layout = QVBoxLayout(self)

        # Ramka Wejściowa
        input_groupbox = QGroupBox("Dane Klucza")
        input_layout = QGridLayout(input_groupbox) 
        input_layout.addWidget(QLabel("E-mail:"), 0, 0, Qt.AlignmentFlag.AlignRight)
        self.email_input = QLineEdit()
        input_layout.addWidget(self.email_input, 0, 1)
        input_layout.addWidget(QLabel("Host:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        self.host_combo = QComboBox()
        self.host_combo.addItems(["github.com", "gitlab.com", "bitbucket.org", "inny_host.com"])
        input_layout.addWidget(self.host_combo, 1, 1)
        input_layout.addWidget(QLabel("Alias:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        self.alias_input = QLineEdit()
        input_layout.addWidget(self.alias_input, 2, 1)
        input_layout.setColumnStretch(1, 1) 
        main_layout.addWidget(input_groupbox)

        # Ramka Akcji
        actions_groupbox = QGroupBox("Akcje")
        actions_layout = QGridLayout(actions_groupbox) 
        self.generate_btn = QPushButton("Generuj klucz")
        self.generate_btn.clicked.connect(self.on_generate)
        actions_layout.addWidget(self.generate_btn, 0, 0)
        self.copy_btn = QPushButton(f"Kopiuj do {os.path.expanduser('~/.ssh')}") 
        self.copy_btn.clicked.connect(self.on_copy_to_ssh)
        actions_layout.addWidget(self.copy_btn, 0, 1)
        self.delete_btn = QPushButton("Usuń klucz")
        self.delete_btn.clicked.connect(self.on_delete)
        actions_layout.addWidget(self.delete_btn, 0, 2)
        self.show_sys_config_btn = QPushButton(f"Pokaż {CONFIG_PATH}")
        self.show_sys_config_btn.clicked.connect(self.on_show_config)
        actions_layout.addWidget(self.show_sys_config_btn, 1, 0)
        self.show_db_btn = QPushButton(f"Pokaż {os.path.basename(KEYS_DB)}")
        self.show_db_btn.clicked.connect(self.on_show_json)
        actions_layout.addWidget(self.show_db_btn, 1, 1)
        self.show_local_config_btn = QPushButton(f"Pokaż {LOCAL_CONFIG_FILENAME}") # Użycie nowej stałej
        self.show_local_config_btn.clicked.connect(self.on_show_local_config)
        actions_layout.addWidget(self.show_local_config_btn, 1, 2)
        main_layout.addWidget(actions_groupbox)

        # Ramka Listy Kluczy
        list_groupbox = QGroupBox("Dostępne Klucze (z bazy aplikacji)")
        list_layout = QVBoxLayout(list_groupbox) 
        self.keys_list_widget = QListWidget()
        # Usunięto setStyleSheet - użyje globalnej palety
        # Ustawienie czcionki monospaced bezpośrednio
        list_font = QFont("Consolas", 9) 
        self.keys_list_widget.setFont(list_font)
        list_layout.addWidget(self.keys_list_widget)
        main_layout.addWidget(list_groupbox)
        main_layout.setStretchFactor(list_groupbox, 1) 

    # Metody obsługi zdarzeń (Sloty) - bez zmian w logice wywołań
    def show_message(self, title, text, icon=QMessageBox.Icon.Information):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon)
        # Dodanie stylizacji do QMessageBox (opcjonalnie, może dziedziczyć)
        msg_box.setStyleSheet(f"QMessageBox {{ background-color: {DARK_COLOR.name()}; }}"
                              f"QLabel {{ color: {LIGHT_FG_COLOR.name()}; background-color: transparent; }}"
                              f"QPushButton {{ min-width: 70px; }}") # Użyj kolorów z palety
        msg_box.exec()

    def on_generate(self):
        email = self.email_input.text().strip()
        host = self.host_combo.currentText()
        alias = self.alias_input.text().strip()
        result = generate_key(email, host, alias, parent_widget=self)
        if result and "anulowane" not in result.lower(): # Pokaż tylko sukcesy
            self.show_message("Generowanie Klucza", result)
        if result: # Zawsze odświeżaj, nawet jeśli anulowano, aby wyczyścić ewentualne błędy
            self.load_and_display_keys()

    def on_copy_to_ssh(self): 
        alias = self.alias_input.text().strip()
        if not alias:
            self.show_message("Brak aliasu", "Podaj alias klucza do skopiowania.", QMessageBox.Icon.Warning)
            return
        result = move_key_to_ssh(alias, parent_widget=self) 
        if result and "anulowane" not in result.lower():
            self.show_message("Kopiowanie Klucza", result)
        if result: # Zawsze odświeżaj
            self.load_and_display_keys()

    def on_delete(self):
        alias = self.alias_input.text().strip()
        if not alias:
            self.show_message("Brak aliasu", "Podaj alias klucza do usunięcia.", QMessageBox.Icon.Warning)
            return
        
        reply = QMessageBox.question(self, "Potwierdzenie usunięcia", 
                                     f"Czy na pewno chcesz usunąć klucz '{alias}'?", # Krótszy tekst
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            result = delete_key(alias, parent_widget=self)
            if result:
                self.show_message("Usuwanie Klucza", result)
                self.load_and_display_keys()

    def on_show_config(self):
        content = show_config()
        self.display_text_dialog(f"Zawartość systemowego pliku: {CONFIG_PATH}", content)

    def on_show_json(self):
        content = show_keys_json()
        self.display_text_dialog(f"Zawartość bazy danych: {KEYS_DB}", content)

    def on_show_local_config(self):
        content = show_local_config_file()
        self.display_text_dialog(f"Zawartość lokalnego pliku: {LOCAL_CONFIG_FILE_PATH}", content)

    def display_text_dialog(self, title, content):
        dialog = TextViewerDialog(title, content, self)
        dialog.exec()

    def load_and_display_keys(self):
        """Ładuje dane z KEYS_DB i aktualizuje QListWidget."""
        self.keys_list_widget.clear()
        try:
            ensure_db()
            with open(KEYS_DB, "r", encoding="utf-8") as f:
                keys = json.load(f)
            if not keys:
                self.keys_list_widget.addItem("  Brak kluczy w bazie danych aplikacji.")
            else:
                for alias, data in keys.items():
                    email_display = data.get('email', 'brak emaila')
                    status_info = []
                    path_to_display = "Nieznana ścieżka"
                    config_host_display = data.get("config_host_alias", f"{data.get('host','unknown').split('.')[0]}-{alias}")

                    if data.get("in_ssh_dir"):
                        path_in_ssh = os.path.join(os.path.expanduser("~/.ssh"), alias)
                        path_to_display = path_in_ssh
                        priv_key_exists = os.path.exists(path_in_ssh)
                        pub_key_exists = os.path.exists(path_in_ssh + ".pub")
                        status_info.append(f"w ~/.ssh (Host: {config_host_display})")
                    else:
                        local_path = data.get("path", os.path.join(LOCAL_KEYS_STORAGE_DIR, alias))
                        path_to_display = local_path
                        priv_key_exists = os.path.exists(local_path)
                        pub_key_exists = os.path.exists(local_path + ".pub")
                        status_info.append(f"w {LOCAL_KEYS_BASE_DIR_NAME} (Config Host będzie: {config_host_display})")
                    
                    if priv_key_exists and pub_key_exists: pass 
                    elif priv_key_exists and not pub_key_exists: status_info.append("BRAK .pub!")
                    elif not priv_key_exists and pub_key_exists: status_info.append("BRAK klucza pryw.!")
                    elif not priv_key_exists and not pub_key_exists: status_info.append("BRAK plików!")
                    
                    status_text = ", ".join(s for s in status_info if s)
                    line1 = f"Alias: {alias}  |  Email: {email_display}"
                    line2 = f"  └─ ({status_text}) Ścieżka: {path_to_display}"
                    
                    self.keys_list_widget.addItem(line1)
                    self.keys_list_widget.addItem(line2)
                    self.keys_list_widget.addItem("") 

        except FileNotFoundError:
            self.keys_list_widget.addItem(f"  Baza danych ({KEYS_DB}) nie znaleziona.")
        except json.JSONDecodeError:
            self.keys_list_widget.addItem("  Błąd odczytu bazy danych (nieprawidłowy JSON).")


# --- Główna część aplikacji ---
if __name__ == '__main__':
    app = QApplication(sys.argv) 

    # --- Ustawienie Prostej Ciemnej Palety ---
    dark_palette = QPalette()
    # Role dla tekstu
    dark_palette.setColor(QPalette.ColorRole.WindowText, LIGHT_FG_COLOR) # Główny tekst w oknie
    dark_palette.setColor(QPalette.ColorRole.Text, LIGHT_FG_COLOR)       # Tekst w polach edycji, listach itp.
    dark_palette.setColor(QPalette.ColorRole.ButtonText, LIGHT_FG_COLOR) # Tekst na przyciskach
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red) # Tekst bardzo kontrastowy (rzadko używany)
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, LIGHT_FG_COLOR) # Tekst zaznaczenia

    # Role dla tła
    dark_palette.setColor(QPalette.ColorRole.Window, DARK_COLOR)          # Tło głównego okna
    dark_palette.setColor(QPalette.ColorRole.Base, DARK_WIDGET_BG_COLOR)  # Tło dla widgetów z tekstem (LineEdit, ListWidget, TextEdit)
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, DARK_COLOR)   # Tło alternatywne (np. w widokach tabel)
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, DARK_COLOR)     # Tło podpowiedzi
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, LIGHT_FG_COLOR) # Tekst podpowiedzi
    dark_palette.setColor(QPalette.ColorRole.Button, DARK_WIDGET_BG_COLOR) # Tło przycisków (może być lekko inne niż okna)
    dark_palette.setColor(QPalette.ColorRole.Highlight, HIGHLIGHT_COLOR)  # Tło zaznaczenia

    # Role dla nieaktywnych elementów
    dark_palette.setColor(QPalette.ColorRole.PlaceholderText, DISABLED_COLOR) # Tekst zastępczy
    # Można też ustawić kolory dla stanu Disabled, np. ciemniejszy tekst/tło

    # Zastosowanie palety do całej aplikacji
    app.setPalette(dark_palette)
    
    # Ustawienie domyślnej czcionki (opcjonalnie)
    # default_font = QFont("Segoe UI", 9) 
    # app.setFont(default_font)

    # --- Koniec ustawiania palety ---

    main_window = SSHKeyManagerApp() 
    main_window.load_and_display_keys() # Załaduj klucze *po* ustawieniu palety i utworzeniu okna
    main_window.show() 

    ensure_dir(LOCAL_KEYS_STORAGE_DIR) 
    update_local_config_file() 

    sys.exit(app.exec())