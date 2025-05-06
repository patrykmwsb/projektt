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
from PyQt6.QtGui import QPalette, QColor, QFont # Importy dla palety, kolorów i czcionek
from PyQt6.QtCore import Qt # Importy dla stałych Qt (np. AlignmentFlag)

# --- Ustalenie Ścieżki Aplikacji (dla .py i .exe) ---
if getattr(sys, 'frozen', False): # Sprawdza, czy skrypt jest uruchomiony jako "zamrożony" plik exe
    application_path = os.path.dirname(sys.executable) # Pobierz ścieżkę do pliku .exe
else: # Jeśli uruchomiony jako normalny skrypt .py
    try:
        application_path = os.path.dirname(os.path.abspath(__file__)) # Pobierz ścieżkę do pliku .py
    except NameError: 
         application_path = os.getcwd() # Fallback, jeśli __file__ nie jest zdefiniowane

APP_DIR = application_path # Używana ścieżka bazowa dla plików aplikacji

# --- Stałe Globalne ---
LOCAL_KEYS_BASE_DIR_NAME = "generated_keys_storage" # Nazwa folderu na lokalne klucze
LOCAL_KEYS_STORAGE_DIR = os.path.join(APP_DIR, LOCAL_KEYS_BASE_DIR_NAME) # Pełna ścieżka do folderu lokalnych kluczy
LOCAL_CONFIG_FILENAME = "config" # Zmieniona nazwa lokalnego pliku config
LOCAL_CONFIG_FILE_PATH = os.path.join(LOCAL_KEYS_STORAGE_DIR, LOCAL_CONFIG_FILENAME) # Pełna ścieżka do lokalnego pliku config
KEYS_DB = os.path.join(APP_DIR, "keys_db.json") # Ścieżka do bazy metadanych kluczy
CONFIG_PATH = os.path.expanduser("~/.ssh/config") # Ścieżka do systemowego pliku ~/.ssh/config

# --- Kolory dla Ciemnego Motywu (używane w QPalette) ---
DARK_COLOR = QColor(45, 45, 45)             # Ciemnoszary dla tła okna
DISABLED_COLOR = QColor(127, 127, 127)      # Szary dla nieaktywnych elementów
DARK_WIDGET_BG_COLOR = QColor(60, 60, 60)    # Ciemniejszy dla tła pól tekstowych, list
LIGHT_FG_COLOR = QColor(220, 220, 220)      # Jasny dla tekstu
HIGHLIGHT_COLOR = QColor(0, 120, 215)       # Niebieski dla zaznaczenia

# --- Funkcje Pomocnicze ---
def ensure_dir(dir_path):
    """Tworzy katalog, jeśli nie istnieje."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

# --- Funkcje Logiki Aplikacji (backend) ---
def ensure_db():
    """Tworzy plik bazy danych JSON (keys_db.json), jeśli nie istnieje."""
    ensure_dir(APP_DIR) 
    if not os.path.exists(KEYS_DB):
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump({}, f) # Inicjalizuje pustym słownikiem JSON

def update_local_config_file():
    """Tworzy/aktualizuje lokalny plik 'config' dla kluczy w 'generated_keys_storage'."""
    ensure_dir(LOCAL_KEYS_STORAGE_DIR) 
    ensure_db() 
    try: 
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys_metadata = json.load(f) # Załaduj metadane
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"BŁĄD: Nie można odczytać bazy danych kluczy '{KEYS_DB}' przy aktualizacji lokalnego configa: {e}")
        return False 

    lines = [] # Lista linii dla lokalnego pliku config
    active_local_entries = 0
    for alias, data in keys_metadata.items():
        # Dodaj wpis tylko jeśli klucz jest lokalny (nie przeniesiony do ~/.ssh)
        if not data.get("in_ssh_dir", False) and data.get("path") and LOCAL_KEYS_STORAGE_DIR in data.get("path"):
            local_key_path = data.get("path") 
            config_host = data.get("config_host_alias", f"{data.get('host','unknown').split('.')[0]}-{alias}") # Pobierz lub stwórz alias hosta dla config
            identity_file_local_abs_path = local_key_path.replace("\\", "/") # Absolutna ścieżka do lokalnego klucza

            # Dodaj linie konfiguracji SSH
            lines.append(f"Host {config_host}")
            lines.append(f"  HostName {data.get('host', 'unknown_host.com')}")
            lines.append(f"  User git")
            lines.append(f"  IdentityFile {identity_file_local_abs_path}") 
            lines.append(f"  IdentitiesOnly yes")
            lines.append("")
            active_local_entries += 1
    
    # Zapisz linie do lokalnego pliku config
    try:
        with open(LOCAL_CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        # Informacja w konsoli
        if active_local_entries > 0:
            print(f"INFO: Lokalny plik konfiguracyjny '{LOCAL_CONFIG_FILENAME}' zaktualizowany. Liczba wpisów: {active_local_entries}")
        else:
            print(f"INFO: Lokalny plik konfiguracyjny '{LOCAL_CONFIG_FILENAME}' jest pusty (brak kluczy lokalnych).")
        return True 
    except IOError as e:
        print(f"BŁĄD: Nie można zapisać lokalnego pliku konfiguracyjnego '{LOCAL_CONFIG_FILE_PATH}': {e}")
        return False 

def generate_key(email, host, alias, parent_widget=None): 
    """Generuje klucz SSH, dodaje metadane, zapisuje lokalnie i aktualizuje bazy."""
    if not email or not host or not alias: # Podstawowa walidacja
        if parent_widget: QMessageBox.warning(parent_widget, "Brak danych", "E-mail, Host i Alias są wymagane.")
        return None 
    
    ensure_db()
    ensure_dir(LOCAL_KEYS_STORAGE_DIR)

    local_key_path = os.path.join(LOCAL_KEYS_STORAGE_DIR, alias) # Ścieżka do klucza w folderze lokalnym
    
    # Sprawdzenie istnienia i potwierdzenie nadpisania
    if os.path.exists(local_key_path) or os.path.exists(local_key_path + ".pub"):
        reply = QMessageBox.StandardButton.No 
        if parent_widget:
             reply = QMessageBox.question(parent_widget, "Potwierdzenie", 
                                         f"Plik klucza '{alias}' lub '{alias}.pub' już istnieje w folderze '{LOCAL_KEYS_BASE_DIR_NAME}'. Czy chcesz go nadpisać?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return f"Generowanie klucza '{alias}' anulowane."
        else:
            try: # Usunięcie istniejących plików
                if os.path.exists(local_key_path): os.remove(local_key_path)
                if os.path.exists(local_key_path + ".pub"): os.remove(local_key_path + ".pub")
            except OSError as e:
                if parent_widget: QMessageBox.critical(parent_widget, "Błąd usuwania", f"Nie można usunąć istniejącego pliku klucza: {e}")
                return None 

    # Przygotowanie i wykonanie polecenia ssh-keygen
    comment_string_ssh = f"email:{email} alias:{alias} host:{host}" # Komentarz dla klucza SSH
    cmd = ["ssh-keygen", "-t", "ed25519", "-C", comment_string_ssh, "-f", local_key_path, "-N", ""] # Generowanie bez hasła
    try:
        startupinfo = None # Dla ukrycia okna konsoli w Windows
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
        process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo) 
    except subprocess.CalledProcessError as e: # Błąd wykonania ssh-keygen
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd ssh-keygen", f"Błąd wykonania ssh-keygen:\n{e.stderr}")
        return None
    except FileNotFoundError: # Brak ssh-keygen w systemie
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd ssh-keygen", "Nie znaleziono polecenia 'ssh-keygen'.\nUpewnij się, że jest zainstalowane (np. z Git) i dostępne w PATH.")
        return None
    except Exception as e: # Inne błędy subprocess
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd subprocess", f"Niespodziewany błąd podczas uruchamiania ssh-keygen:\n{e}")
        return None

    # Dodanie linii metadanych do pliku .pub
    public_key_file_path = local_key_path + ".pub"
    host_short_name = host.split('.')[0] 
    key_name_metadata = f"id_ed25519_{host_short_name}-{alias}" # Konstrukcja nazwy klucza dla metadanych
    metadata_line_for_pub_key = f"# key_name: {key_name_metadata}\n" # Linia dodawana do pliku .pub

    try: # Odczyt i zapis pliku .pub z dodaną linią
        with open(public_key_file_path, "r+", encoding="utf-8") as f_pub:
            original_pub_key_content = f_pub.read()
            f_pub.seek(0, 0) # Powrót na początek pliku
            f_pub.write(metadata_line_for_pub_key + original_pub_key_content) # Zapis metadanych + oryginalna treść
    except IOError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu .pub", f"Błąd podczas dodawania metadanych do pliku {public_key_file_path}:\n{e}")
        return None

    # Odczyt i aktualizacja bazy danych keys_db.json
    try: 
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
         keys = {} # Stwórz nową, jeśli plik nie istnieje lub jest uszkodzony

    config_host_alias = f"{host_short_name}-{alias}" # Alias używany w dyrektywie Host w plikach config
    # Dodanie nowego wpisu do słownika bazy danych
    keys[alias] = {
        "email": email, 
        "host": host, 
        "path": local_key_path, # Zapisuje ścieżkę do lokalnego klucza
        "config_host_alias": config_host_alias, 
        "in_ssh_dir": False # Początkowo klucz nie jest w ~/.ssh
    }
    try: # Zapis zaktualizowanej bazy danych
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=4, ensure_ascii=False) 
    except IOError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu DB", f"Nie można zapisać bazy danych {KEYS_DB}:\n{e}")
        return None 

    # Aktualizacja lokalnego pliku konfiguracyjnego
    if not update_local_config_file(): 
         if parent_widget: QMessageBox.warning(parent_widget, "Ostrzeżenie", f"Nie udało się zaktualizować lokalnego pliku {LOCAL_CONFIG_FILENAME}.")
         
    return f"Klucz '{alias}' wygenerowany w '{LOCAL_KEYS_BASE_DIR_NAME}'.\nDodano do .pub: {metadata_line_for_pub_key.strip()}"

def move_key_to_ssh(alias, parent_widget=None): 
    """Kopiuje pliki klucza do ~/.ssh i aktualizuje konfiguracje."""
    ssh_dir = os.path.expanduser("~/.ssh") 
    os.makedirs(ssh_dir, exist_ok=True) # Upewnij się, że katalog ~/.ssh istnieje
    ensure_db()

    try:
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd Bazy Danych", f"Nie można odczytać pliku {KEYS_DB}.")
        return None 

    if alias not in keys: # Sprawdź, czy alias jest w bazie
        if parent_widget: QMessageBox.warning(parent_widget, "Nie znaleziono aliasu", f"Alias '{alias}' nie istnieje w bazie.")
        return None
    
    entry = keys[alias]
    ssh_key_dest_path_base = os.path.join(ssh_dir, alias) # Ścieżka docelowa w ~/.ssh
    # Zapytaj o nadpisanie, jeśli klucz już tam jest
    if entry.get("in_ssh_dir", False) and os.path.exists(ssh_key_dest_path_base):
        reply = QMessageBox.StandardButton.No
        if parent_widget:
             reply = QMessageBox.question(parent_widget, "Potwierdzenie", 
                                          f"Klucz '{alias}' jest już prawdopodobnie w ~/.ssh. Czy chcesz spróbować przenieść/skonfigurować ponownie?",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                          QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.No:
            return f"Operacja dla '{alias}' anulowana."

    # Znajdź ścieżkę do lokalnych plików źródłowych
    local_key_path_base = entry.get("path", os.path.join(LOCAL_KEYS_STORAGE_DIR, alias))
    # Poprawka: upewnij się, że ścieżka lokalna jest poprawna, jeśli 'path' zostało zmienione
    if LOCAL_KEYS_STORAGE_DIR not in local_key_path_base:
         local_key_path_base = os.path.join(LOCAL_KEYS_STORAGE_DIR, alias) 

    local_key_priv_path = local_key_path_base
    local_key_pub_path = local_key_path_base + ".pub"

    # Sprawdź, czy pliki źródłowe istnieją
    if not os.path.exists(local_key_priv_path) or not os.path.exists(local_key_pub_path):
        if parent_widget: QMessageBox.critical(parent_widget, "Brak plików źródłowych", f"Brak plików klucza '{alias}' w folderze '{LOCAL_KEYS_BASE_DIR_NAME}'. Wygeneruj je najpierw.")
        return None

    try:
        # Kopiowanie plików do ~/.ssh
        shutil.copy2(local_key_priv_path, ssh_key_dest_path_base) # Kopiuj prywatny
        shutil.copy2(local_key_pub_path, ssh_key_dest_path_base + ".pub") # Kopiuj publiczny
        # Ustaw uprawnienia w ~/.ssh
        os.chmod(ssh_key_dest_path_base, 0o600) # Prywatny: rw-------
        os.chmod(ssh_key_dest_path_base + ".pub", 0o644) # Publiczny: rw-r--r--
    except Exception as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd kopiowania", f"Błąd podczas kopiowania plików klucza '{alias}':\n{e}")
        return None

    # Aktualizacja bazy danych
    keys[alias]["path"] = ssh_key_dest_path_base # Zmień ścieżkę na tę w ~/.ssh
    keys[alias]["in_ssh_dir"] = True # Oznacz jako przeniesiony
    try: # Zapisz zmiany w bazie
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=4, ensure_ascii=False)
    except IOError as e:
         if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu DB", f"Nie można zaktualizować bazy danych {KEYS_DB} po przeniesieniu:\n{e}")
         return f"Klucze '{alias}' skopiowane, ale wystąpił błąd aktualizacji bazy danych!"

    # Zaktualizuj oba pliki konfiguracyjne
    update_config_file(parent_widget) # Aktualizuje ~/.ssh/config
    update_local_config_file() # Aktualizuje lokalny config (usuwa z niego wpis)
    return f"Klucz '{alias}' został skopiowany do ~/.ssh i konfiguracja zaktualizowana."

def delete_key(alias, parent_widget=None): 
    """Usuwa klucz: pliki lokalne, pliki w ~/.ssh (jeśli istnieją), wpis z bazy i configów."""
    ensure_db()
    try:
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd Bazy Danych", f"Nie można odczytać pliku {KEYS_DB}.")
        return None

    if alias not in keys: # Sprawdź, czy alias istnieje
        if parent_widget: QMessageBox.warning(parent_widget, "Nie znaleziono aliasu", f"Alias '{alias}' nie istnieje w bazie.")
        return None

    entry = keys[alias]
    paths_to_delete = set() # Zbiór ścieżek bazowych do usunięcia
    
    # Zawsze dodaj ścieżkę w lokalnym storage do usunięcia
    local_key_in_storage_path = os.path.join(LOCAL_KEYS_STORAGE_DIR, alias)
    paths_to_delete.add(local_key_in_storage_path)

    # Jeśli klucz był przeniesiony, dodaj ścieżkę w ~/.ssh
    if entry.get("in_ssh_dir"):
        paths_to_delete.add(os.path.join(os.path.expanduser("~/.ssh"), alias))
    # Dodaj starą ścieżkę, jeśli jest inna (dla pewności)
    if "path" in entry and entry["path"] not in paths_to_delete: 
        paths_to_delete.add(entry["path"])

    # Pętla usuwająca pliki
    files_deleted_count = 0
    for key_path_base in paths_to_delete:
        try:
            # Usuń plik prywatny i publiczny
            if os.path.exists(key_path_base):
                os.remove(key_path_base)
                files_deleted_count += 1
            if os.path.exists(key_path_base + ".pub"):
                os.remove(key_path_base + ".pub")
                files_deleted_count += 1
        except OSError as e:
            # Wypisz ostrzeżenie w konsoli, ale nie przerywaj operacji
            print(f"Ostrzeżenie: Nie udało się usunąć pliku {key_path_base} lub {key_path_base}.pub: {e}")

    # Usuń wpis z bazy danych (słownika w pamięci)
    del keys[alias]
    try: # Zapisz zmienioną bazę danych na dysk
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump(keys, f, indent=4, ensure_ascii=False)
    except IOError as e:
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd zapisu DB", f"Nie można zaktualizować bazy danych {KEYS_DB} po usunięciu:\n{e}")
        return f"Wystąpił błąd aktualizacji bazy danych! Pliki mogły zostać usunięte."

    # Zaktualizuj oba pliki konfiguracyjne (usuną wpis dla aliasu)
    update_config_file(parent_widget) 
    update_local_config_file() 
    if files_deleted_count > 0:
        return f"Klucz '{alias}' (pliki i wpis) usunięty."
    else:
        # Pliki mogły nie istnieć, ale wpis z bazy i configów został usunięty
        return f"Wpis dla klucza '{alias}' usunięty z bazy i konfiguracji (pliki nie znalezione)."

def update_config_file(parent_widget=None): 
    """Nadpisuje systemowy plik ~/.ssh/config wpisami dla kluczy w ~/.ssh."""
    ensure_db()
    try:
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys_metadata = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"BŁĄD: Nie można odczytać bazy danych kluczy '{KEYS_DB}' przy aktualizacji ~/.ssh/config: {e}")
        if parent_widget: QMessageBox.critical(parent_widget, "Błąd Bazy Danych", f"Nie można odczytać pliku {KEYS_DB}. Aktualizacja ~/.ssh/config przerwana.")
        return False # Zwróć błąd

    lines = [] # Linie do zapisu
    active_config_entries = 0
    # Iteruj przez bazę danych
    for alias, data in keys_metadata.items():
        # Weź pod uwagę tylko klucze oznaczone jako będące w ~/.ssh
        if data.get("in_ssh_dir", False) and data.get("path") and os.path.expanduser("~/.ssh") in data.get("path"): 
            config_host = data.get("config_host_alias", f"{data.get('host','unknown').split('.')[0]}-{alias}") # Host dla configa
            identity_file_in_ssh_config = os.path.join("~/.ssh", alias).replace("\\", "/") # Ścieżka do klucza (plik = alias)

            # Dodaj linie konfiguracyjne
            lines.append(f"Host {config_host}") 
            lines.append(f"  HostName {data.get('host', 'unknown_host.com')}") 
            lines.append(f"  User git")
            lines.append(f"  IdentityFile {identity_file_in_ssh_config}") 
            lines.append(f"  IdentitiesOnly yes")
            lines.append("")
            active_config_entries +=1
    
    ensure_dir(os.path.expanduser("~/.ssh")) # Upewnij się, że katalog istnieje
    try: # Zapisz plik ~/.ssh/config
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        if os.name != 'nt': # Ustaw uprawnienia poza Windows
            os.chmod(CONFIG_PATH, 0o600)
        
        # Informacja w konsoli
        if active_config_entries > 0:
            print(f"INFO: Plik ~/.ssh/config zaktualizowany. Liczba aktywnych wpisów: {active_config_entries}")
        else:
            print(f"INFO: Plik ~/.ssh/config jest teraz pusty (lub został wyczyszczony), ponieważ żadne zarządzane klucze nie są w ~/.ssh.")
        return True # Sukces
    except IOError as e:
        if parent_widget: QMessageBox.showwarning(parent_widget, "Błąd zapisu config", f"Nie można zapisać pliku {CONFIG_PATH}:\n{e}\nSprawdź uprawnienia.")
        return False # Błąd


def show_config():
    """Odczytuje zawartość systemowego pliku ~/.ssh/config."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Plik {CONFIG_PATH} nie istnieje."

def show_keys_json():
    """Odczytuje zawartość bazy danych keys_db.json."""
    ensure_db()
    try:
      with open(KEYS_DB, "r", encoding="utf-8") as f:
          # Ładuje i od razu formatuje do ładnego stringa JSON
          return json.dumps(json.load(f), indent=4, ensure_ascii=False)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        return f"Błąd odczytu pliku bazy danych {KEYS_DB}:\n{e}"

def show_local_config_file():
    """Odczytuje zawartość lokalnego pliku konfiguracyjnego."""
    ensure_dir(LOCAL_KEYS_STORAGE_DIR) 
    try:
        with open(LOCAL_CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        # Zwraca informację, jeśli plik jeszcze nie istnieje
        return f"Lokalny plik konfiguracyjny '{LOCAL_CONFIG_FILENAME}' nie istnieje (folder: '{LOCAL_KEYS_BASE_DIR_NAME}').\nZostanie utworzony po wygenerowaniu pierwszego klucza."


# --- Klasa Okna Dialogowego do Wyświetlania Tekstu ---
class TextViewerDialog(QDialog): # Dziedziczy po QDialog (standardowe okno dialogowe)
    def __init__(self, title, content, parent=None):
        super().__init__(parent) # Wywołanie konstruktora klasy nadrzędnej
        self.setWindowTitle(title) # Ustawienie tytułu okna
        self.setMinimumSize(600, 400) # Minimalny rozmiar okna dialogowego

        self.layout = QVBoxLayout(self) # Główny layout pionowy dla okna dialogowego

        self.text_edit = QTextEdit(self) # Pole tekstowe do wyświetlania zawartości
        self.text_edit.setReadOnly(True) # Ustawienie pola jako tylko do odczytu
        self.text_edit.setPlainText(content) # Wstawienie tekstu
        # Ustawienie czcionki monospaced dla lepszej czytelności kodu/konfiguracji
        font = QFont("Consolas", 10) # Można zmienić na inną czcionkę monospaced
        self.text_edit.setFont(font)
        self.layout.addWidget(self.text_edit) # Dodanie pola tekstowego do layoutu

        # Standardowy zestaw przycisków dla dialogu (tutaj tylko OK)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept) # Połączenie sygnału 'accepted' (kliknięcie OK) z metodą 'accept' (zamknięcie dialogu)
        self.layout.addWidget(self.button_box) # Dodanie przycisków do layoutu

# --- Główna Klasa Aplikacji GUI (PyQt6) ---
class SSHKeyManagerApp(QWidget): # Główny widget aplikacji
    def __init__(self):
        super().__init__() # Konstruktor klasy nadrzędnej
        self.init_ui() # Metoda inicjalizująca interfejs użytkownika
        # Ładowanie kluczy przeniesione do bloku __main__ po ustawieniu palety

    def init_ui(self):
        """Inicjalizuje i układa wszystkie widgety interfejsu."""
        self.setWindowTitle("Menedżer Kluczy SSH (PyQt6 - Prosty Ciemny)") # Tytuł okna
        self.setGeometry(200, 200, 850, 600) # Pozycja i rozmiar okna

        main_layout = QVBoxLayout(self) # Główny layout pionowy dla całego okna

        # --- Ramka Wejściowa (GroupBox) ---
        input_groupbox = QGroupBox("Dane Klucza") # Grupująca ramka z tytułem
        input_layout = QGridLayout(input_groupbox) # Layout siatkowy wewnątrz ramki

        # Etykieta i pole dla E-mail
        input_layout.addWidget(QLabel("E-mail:"), 0, 0, Qt.AlignmentFlag.AlignRight) # Etykieta, wiersz 0, kolumna 0, wyrównana do prawej
        self.email_input = QLineEdit() # Pole do wpisywania tekstu
        input_layout.addWidget(self.email_input, 0, 1) # Pole tekstowe, wiersz 0, kolumna 1

        # Etykieta i lista rozwijana dla Hosta
        input_layout.addWidget(QLabel("Host:"), 1, 0, Qt.AlignmentFlag.AlignRight)
        self.host_combo = QComboBox() # Lista rozwijana
        self.host_combo.addItems(["github.com", "gitlab.com", "bitbucket.org", "inny_host.com"]) # Dodanie opcji
        input_layout.addWidget(self.host_combo, 1, 1)

        # Etykieta i pole dla Aliasu
        input_layout.addWidget(QLabel("Alias:"), 2, 0, Qt.AlignmentFlag.AlignRight)
        self.alias_input = QLineEdit()
        input_layout.addWidget(self.alias_input, 2, 1)

        input_layout.setColumnStretch(1, 1) # Pozwól drugiej kolumnie (pola wprowadzania) się rozciągać
        main_layout.addWidget(input_groupbox) # Dodaj ramkę wejściową do głównego layoutu

        # --- Ramka Akcji ---
        actions_groupbox = QGroupBox("Akcje")
        actions_layout = QGridLayout(actions_groupbox) 

        # Przyciski akcji i podłączenie ich sygnału 'clicked' do odpowiednich metod (slotów)
        self.generate_btn = QPushButton("Generuj klucz")
        self.generate_btn.clicked.connect(self.on_generate) # Po kliknięciu wywołaj on_generate
        actions_layout.addWidget(self.generate_btn, 0, 0) # Wiersz 0, Kolumna 0

        self.copy_btn = QPushButton(f"Kopiuj do {os.path.expanduser('~/.ssh')}") 
        self.copy_btn.clicked.connect(self.on_copy_to_ssh)
        actions_layout.addWidget(self.copy_btn, 0, 1) # Wiersz 0, Kolumna 1

        self.delete_btn = QPushButton("Usuń klucz")
        self.delete_btn.clicked.connect(self.on_delete)
        actions_layout.addWidget(self.delete_btn, 0, 2) # Wiersz 0, Kolumna 2

        self.show_sys_config_btn = QPushButton(f"Pokaż {CONFIG_PATH}")
        self.show_sys_config_btn.clicked.connect(self.on_show_config)
        actions_layout.addWidget(self.show_sys_config_btn, 1, 0) # Wiersz 1, Kolumna 0
        
        self.show_db_btn = QPushButton(f"Pokaż {os.path.basename(KEYS_DB)}")
        self.show_db_btn.clicked.connect(self.on_show_json)
        actions_layout.addWidget(self.show_db_btn, 1, 1) # Wiersz 1, Kolumna 1

        self.show_local_config_btn = QPushButton(f"Pokaż {LOCAL_CONFIG_FILENAME}")
        self.show_local_config_btn.clicked.connect(self.on_show_local_config)
        actions_layout.addWidget(self.show_local_config_btn, 1, 2) # Wiersz 1, Kolumna 2

        main_layout.addWidget(actions_groupbox) # Dodaj ramkę akcji do głównego layoutu

        # --- Ramka Listy Kluczy ---
        list_groupbox = QGroupBox("Dostępne Klucze (z bazy aplikacji)")
        list_layout = QVBoxLayout(list_groupbox) 
        self.keys_list_widget = QListWidget() # Widget listy
        
        # Ustawienie czcionki monospaced bezpośrednio dla ListWidget
        list_font = QFont("Consolas", 9) # Wybierz czcionkę (upewnij się, że jest dostępna)
        self.keys_list_widget.setFont(list_font)
        
        list_layout.addWidget(self.keys_list_widget) # Dodaj listę do layoutu ramki
        main_layout.addWidget(list_groupbox) # Dodaj ramkę listy do głównego layoutu
        main_layout.setStretchFactor(list_groupbox, 1) # Pozwól tej ramce rozciągać się pionowo

    # --- Metody obsługi zdarzeń (Sloty) ---
    def show_message(self, title, text, icon=QMessageBox.Icon.Information):
        """Wyświetla okno komunikatu QMessageBox."""
        msg_box = QMessageBox(self) # Ustawienie rodzica okna
        msg_box.setWindowTitle(title)
        msg_box.setText(text)
        msg_box.setIcon(icon) # Ikona (Informacja, Ostrzeżenie, Błąd)
        # Prosta stylizacja QMessageBox dla spójności z paletą
        msg_box.setStyleSheet(f"QMessageBox {{ background-color: {DARK_COLOR.name()}; }}"
                              f"QLabel {{ color: {LIGHT_FG_COLOR.name()}; background-color: transparent; }}"
                              f"QPushButton {{ min-width: 70px; /* Użyje stylu z palety */ }}")
        msg_box.exec() # Wyświetl okno modalnie

    # Metody on_... wywołują odpowiednie funkcje backendowe i odświeżają listę
    def on_generate(self):
        email = self.email_input.text().strip() # Pobierz tekst z pola email
        host = self.host_combo.currentText() # Pobierz wybraną wartość z comboboxa
        alias = self.alias_input.text().strip() # Pobierz tekst z pola alias
        result = generate_key(email, host, alias, parent_widget=self) # Wywołaj funkcję generującą
        if result and "anulowane" not in result.lower(): # Pokaż komunikat tylko jeśli nie anulowano
            self.show_message("Generowanie Klucza", result)
        if result: # Zawsze odświeżaj listę po próbie operacji
            self.load_and_display_keys()

    def on_copy_to_ssh(self): 
        alias = self.alias_input.text().strip()
        if not alias:
            self.show_message("Brak aliasu", "Podaj alias klucza do skopiowania.", QMessageBox.Icon.Warning)
            return
        result = move_key_to_ssh(alias, parent_widget=self) # Wywołaj funkcję kopiującą
        if result and "anulowane" not in result.lower():
            self.show_message("Kopiowanie Klucza", result)
        if result: 
            self.load_and_display_keys()

    def on_delete(self):
        alias = self.alias_input.text().strip()
        if not alias:
            self.show_message("Brak aliasu", "Podaj alias klucza do usunięcia.", QMessageBox.Icon.Warning)
            return
        
        # Zapytaj użytkownika o potwierdzenie
        reply = QMessageBox.question(self, "Potwierdzenie usunięcia", 
                                     f"Czy na pewno chcesz usunąć klucz '{alias}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes: # Jeśli użytkownik potwierdzi
            result = delete_key(alias, parent_widget=self) # Wywołaj funkcję usuwającą
            if result:
                self.show_message("Usuwanie Klucza", result)
                self.load_and_display_keys() # Odśwież listę

    def on_show_config(self):
        """Wyświetla zawartość systemowego pliku config."""
        content = show_config()
        self.display_text_dialog(f"Zawartość systemowego pliku: {CONFIG_PATH}", content)

    def on_show_json(self):
        """Wyświetla zawartość bazy danych keys_db.json."""
        content = show_keys_json()
        self.display_text_dialog(f"Zawartość bazy danych: {KEYS_DB}", content)

    def on_show_local_config(self):
        """Wyświetla zawartość lokalnego pliku config."""
        content = show_local_config_file()
        self.display_text_dialog(f"Zawartość lokalnego pliku: {LOCAL_CONFIG_FILE_PATH}", content)

    def display_text_dialog(self, title, content):
        """Metoda pomocnicza do tworzenia i wyświetlania okna dialogowego z tekstem."""
        dialog = TextViewerDialog(title, content, self) # Utwórz instancję dialogu
        dialog.exec() # Wyświetl dialog modalnie (blokuje główne okno)

    def load_and_display_keys(self):
        """Ładuje dane o kluczach z pliku JSON i aktualizuje listę w GUI."""
        self.keys_list_widget.clear() # Wyczyść starą zawartość listy
        try:
            ensure_db() # Upewnij się, że plik bazy istnieje
            with open(KEYS_DB, "r", encoding="utf-8") as f:
                keys = json.load(f) # Załaduj dane
            if not keys:
                self.keys_list_widget.addItem("  Brak kluczy w bazie danych aplikacji.")
            else:
                # Iteruj przez załadowane klucze
                for alias, data in keys.items():
                    email_display = data.get('email', 'brak emaila')
                    status_info = [] # Informacje o statusie plików i lokalizacji
                    path_to_display = "Nieznana ścieżka" # Ścieżka do wyświetlenia
                    config_host_display = data.get("config_host_alias", f"{data.get('host','unknown').split('.')[0]}-{alias}")

                    # Sprawdź, gdzie jest klucz i jaki jest stan plików
                    if data.get("in_ssh_dir"):
                        # Klucz w ~/.ssh
                        path_in_ssh = os.path.join(os.path.expanduser("~/.ssh"), alias)
                        path_to_display = path_in_ssh
                        priv_key_exists = os.path.exists(path_in_ssh)
                        pub_key_exists = os.path.exists(path_in_ssh + ".pub")
                        status_info.append(f"w ~/.ssh (Host: {config_host_display})")
                    else:
                        # Klucz lokalnie
                        local_path = data.get("path", os.path.join(LOCAL_KEYS_STORAGE_DIR, alias))
                        path_to_display = local_path
                        priv_key_exists = os.path.exists(local_path)
                        pub_key_exists = os.path.exists(local_path + ".pub")
                        status_info.append(f"w {LOCAL_KEYS_BASE_DIR_NAME} (Config Host będzie: {config_host_display})")
                    
                    # Sprawdzenie istnienia plików
                    if priv_key_exists and pub_key_exists: pass # OK
                    elif priv_key_exists and not pub_key_exists: status_info.append("BRAK .pub!")
                    elif not priv_key_exists and pub_key_exists: status_info.append("BRAK klucza pryw.!")
                    elif not priv_key_exists and not pub_key_exists: status_info.append("BRAK plików!")
                    
                    # Formatowanie wpisu dla listy
                    status_text = ", ".join(s for s in status_info if s)
                    line1 = f"Alias: {alias}  |  Email: {email_display}"
                    line2 = f"  └─ ({status_text}) Ścieżka: {path_to_display}"
                    
                    # Dodanie sformatowanych linii do QListWidget
                    self.keys_list_widget.addItem(line1)
                    self.keys_list_widget.addItem(line2)
                    self.keys_list_widget.addItem("") # Dodaj pustą linię jako separator

        except FileNotFoundError: # Obsługa braku pliku bazy
            self.keys_list_widget.addItem(f"  Baza danych ({KEYS_DB}) nie znaleziona.")
        except json.JSONDecodeError: # Obsługa błędu formatu JSON
            self.keys_list_widget.addItem("  Błąd odczytu bazy danych (nieprawidłowy JSON).")


# --- Główna część aplikacji (uruchomienie) ---
if __name__ == '__main__':
    app = QApplication(sys.argv) # Inicjalizacja aplikacji PyQt

    # --- Ustawienie Prostej Ciemnej Palety Kolorów ---
    dark_palette = QPalette() # Stworzenie obiektu palety
    # Ustawienie kolorów dla różnych ról (tekst, tło, przyciski, zaznaczenie...)
    dark_palette.setColor(QPalette.ColorRole.WindowText, LIGHT_FG_COLOR) 
    dark_palette.setColor(QPalette.ColorRole.Text, LIGHT_FG_COLOR)       
    dark_palette.setColor(QPalette.ColorRole.ButtonText, LIGHT_FG_COLOR) 
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red) 
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, LIGHT_FG_COLOR) 
    dark_palette.setColor(QPalette.ColorRole.Window, DARK_COLOR)          
    dark_palette.setColor(QPalette.ColorRole.Base, DARK_WIDGET_BG_COLOR)  
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, DARK_COLOR)   
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, DARK_COLOR)     
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, LIGHT_FG_COLOR) 
    dark_palette.setColor(QPalette.ColorRole.Button, DARK_WIDGET_BG_COLOR) 
    dark_palette.setColor(QPalette.ColorRole.Highlight, HIGHLIGHT_COLOR)  
    dark_palette.setColor(QPalette.ColorRole.PlaceholderText, DISABLED_COLOR) 
    # Zastosowanie zdefiniowanej palety do całej aplikacji
    app.setPalette(dark_palette)
    # --- Koniec ustawiania palety ---

    main_window = SSHKeyManagerApp() # Utworzenie instancji głównego okna aplikacji
    main_window.load_and_display_keys() # Załadowanie i wyświetlenie kluczy po stworzeniu okna
    main_window.show() # Wyświetlenie głównego okna

    # Inicjalizacja: upewnij się, że foldery istnieją i lokalny config jest aktualny
    ensure_dir(LOCAL_KEYS_STORAGE_DIR) 
    update_local_config_file() 

    sys.exit(app.exec()) # Uruchomienie głównej pętli zdarzeń aplikacji PyQt
