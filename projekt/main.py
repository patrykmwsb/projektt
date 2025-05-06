import os
import json
import shutil
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk # Upewnij się, że ttk jest importowane

# --- Stałe Globalne ---
APP_DIR = os.path.dirname(os.path.abspath(__file__)) # Katalog, w którym znajduje się skrypt
KEYS_DB = os.path.join(APP_DIR, "keys_db.json")      # Ścieżka do pliku bazy danych JSON (przechowuje metadane kluczy)
CONFIG_PATH = os.path.expanduser("~/.ssh/config")    # Ścieżka do systemowego pliku konfiguracyjnego SSH

# --- Kolory dla Ciemnego Motywu ---
DARK_BG = "#2e2e2e"
LIGHT_FG = "#e0e0e0" 
ENTRY_BG = "#3c3c3c"
BUTTON_BG = "#4a4a4a" 
BUTTON_FG = LIGHT_FG
ACTIVE_BUTTON_BG = "#5f5f5f" 
SELECT_BG = "#0078D7" 
BORDER_COLOR = "#555555" 

# --- Funkcje Logiki Aplikacji ---
def ensure_db():
    """Tworzy plik bazy danych JSON, jeśli nie istnieje."""
    if not os.path.exists(KEYS_DB):
        with open(KEYS_DB, "w", encoding="utf-8") as f:
            json.dump({}, f) # Inicjalizuje pustym obiektem JSON

def generate_key(email, host, alias):
    """Generuje parę kluczy SSH (prywatny i publiczny) i zapisuje informacje w bazie."""
    if not email or not host or not alias:
        return "E-mail, Host i Alias są wymagane." # Walidacja danych wejściowych
    ensure_db() # Upewnij się, że baza danych istnieje
    key_path = os.path.join(APP_DIR, alias) # Ścieżka do klucza w folderze aplikacji (nazwa pliku = alias)
    
    # Sprawdzenie, czy pliki klucza już istnieją i pytanie o nadpisanie
    if os.path.exists(key_path) or os.path.exists(key_path + ".pub"):
        if not messagebox.askyesno("Potwierdzenie", f"Plik klucza '{alias}' lub '{alias}.pub' już istnieje w folderze aplikacji. Czy chcesz go nadpisać?"):
            return f"Generowanie klucza '{alias}' anulowane."
        else:
            # Próba usunięcia istniejących plików przed wygenerowaniem nowych
            try:
                if os.path.exists(key_path): os.remove(key_path)
                if os.path.exists(key_path + ".pub"): os.remove(key_path + ".pub")
            except OSError as e:
                return f"Nie można usunąć istniejącego pliku klucza: {e}"

    # Komentarz dołączany do klucza publicznego
    comment_string = f"email:{email} alias:{alias} host:{host}"
    # Polecenie systemowe do generowania klucza SSH
    cmd = ["ssh-keygen", "-t", "ed25519", "-C", comment_string, "-f", key_path, "-N", ""] # -N "" oznacza brak hasła
    try:
        # Uruchomienie polecenia ssh-keygen
        process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
    except subprocess.CalledProcessError as e:
        return f"Błąd ssh-keygen: {e.stderr}" # Błąd wykonania polecenia
    except FileNotFoundError:
        return "Błąd: polecenie ssh-keygen nie znalezione. Upewnij się, że jest zainstalowane i w PATH." # ssh-keygen nie jest dostępne

    # Zapis informacji o kluczu do bazy danych JSON
    with open(KEYS_DB, "r", encoding="utf-8") as f:
        keys = json.load(f)
    keys[alias] = {"email": email, "host": host, "path": key_path, "in_ssh_dir": False} # Zapis metadanych
    with open(KEYS_DB, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=4, ensure_ascii=False) # Zapis z formatowaniem
    return f"Klucz '{alias}' wygenerowany w folderze aplikacji.\nKomentarz klucza publicznego: {comment_string}"

def move_key_to_ssh(alias):
    """Przenosi (kopiuje) wygenerowane pliki klucza do katalogu ~/.ssh i aktualizuje konfigurację."""
    ssh_dir = os.path.expanduser("~/.ssh") # Standardowy katalog SSH użytkownika
    os.makedirs(ssh_dir, exist_ok=True) # Utwórz katalog ~/.ssh, jeśli nie istnieje
    ensure_db()

    with open(KEYS_DB, "r", encoding="utf-8") as f:
        keys = json.load(f) # Odczyt bazy metadanych

    if alias not in keys:
        return f"Alias '{alias}' nie istnieje w bazie." # Sprawdzenie, czy alias istnieje
    
    entry = keys[alias] # Pobranie danych dla aliasu
    # Sprawdzenie, czy klucz nie został już przeniesiony
    if entry.get("in_ssh_dir", False) and os.path.exists(entry["path"]):
         if not messagebox.askyesno("Potwierdzenie", f"Klucz '{alias}' jest już oznaczony jako przeniesiony i plik istnieje w '{entry['path']}'. Czy chcesz spróbować przenieść/skonfigurować ponownie?"):
            return f"Operacja dla '{alias}' anulowana."

    # Ścieżki do plików klucza w folderze aplikacji
    app_key_path = os.path.join(APP_DIR, alias)
    app_key_pub_path = app_key_path + ".pub"

    if not os.path.exists(app_key_path) or not os.path.exists(app_key_pub_path):
        return f"Brak plików klucza '{alias}' w folderze aplikacji. Wygeneruj je najpierw."

    # Nowa ścieżka dla plików klucza w katalogu ~/.ssh
    new_path_base = os.path.join(ssh_dir, alias) 
    try:
        # Kopiowanie plików klucza
        shutil.copy2(app_key_path, new_path_base)
        shutil.copy2(app_key_pub_path, new_path_base + ".pub")
        # Ustawienie odpowiednich uprawnień dla plików kluczy
        os.chmod(new_path_base, 0o600) # Klucz prywatny: tylko właściciel może czytać/pisać
        os.chmod(new_path_base + ".pub", 0o644) # Klucz publiczny: może być czytany przez innych
    except Exception as e:
        return f"Błąd podczas kopiowania plików klucza '{alias}': {e}"

    # Aktualizacja ścieżki i statusu w bazie metadanych
    keys[alias]["path"] = new_path_base 
    keys[alias]["in_ssh_dir"] = True
    with open(KEYS_DB, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=4, ensure_ascii=False)
    
    update_config_file() # Zaktualizuj plik ~/.ssh/config
    return f"Klucz '{alias}' został przeniesiony do ~/.ssh i konfiguracja zaktualizowana."

def delete_key(alias):
    """Usuwa pliki klucza (z folderu aplikacji i ~/.ssh) oraz wpis z bazy i konfiguracji."""
    ensure_db()
    with open(KEYS_DB, "r", encoding="utf-8") as f:
        keys = json.load(f)

    if alias not in keys:
        return f"Alias '{alias}' nie istnieje w bazie."

    entry = keys[alias]
    paths_to_delete = set() # Zbiór ścieżek do usunięcia, aby uniknąć duplikatów
    # Dodaj ścieżkę zapisaną w bazie (może być lokalna lub w ~/.ssh)
    if "path" in entry: paths_to_delete.add(entry["path"])
    # Dodaj domyślną ścieżkę lokalną (na wszelki wypadek)
    paths_to_delete.add(os.path.join(APP_DIR, alias))
    # Jeśli klucz był w ~/.ssh, dodaj tę ścieżkę
    if entry.get("in_ssh_dir"):
        paths_to_delete.add(os.path.join(os.path.expanduser("~/.ssh"), alias))

    files_deleted_count = 0
    # Iteracja przez ścieżki i usuwanie plików
    for key_path_base in paths_to_delete:
        try:
            if os.path.exists(key_path_base):
                os.remove(key_path_base) # Usuń plik klucza prywatnego
                files_deleted_count += 1
            if os.path.exists(key_path_base + ".pub"):
                os.remove(key_path_base + ".pub") # Usuń plik klucza publicznego
                files_deleted_count += 1
        except OSError as e:
            # Wyświetl ostrzeżenie, ale kontynuuj, aby usunąć wpisy z bazy/konfiguracji
            print(f"Ostrzeżenie: Nie udało się usunąć pliku {key_path_base} lub {key_path_base}.pub: {e}")

    del keys[alias] # Usuń wpis aliasu z bazy metadanych
    with open(KEYS_DB, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=4, ensure_ascii=False)
    
    update_config_file() # Zaktualizuj plik ~/.ssh/config (usunie wpis dla tego aliasu)
    if files_deleted_count > 0:
        return f"Klucz '{alias}' (pliki i wpis) usunięty."
    else:
        return f"Wpis dla klucza '{alias}' usunięty z bazy i konfiguracji (pliki nie znalezione)."

def update_config_file():
    """Aktualizuje (nadpisuje) plik ~/.ssh/config na podstawie kluczy oznaczonych jako 'in_ssh_dir'."""
    ensure_db()
    with open(KEYS_DB, "r", encoding="utf-8") as f:
        keys = json.load(f)

    lines = [] # Lista linii do zapisu w pliku config
    for alias, data in keys.items():
        # Dodaj do configu tylko te klucze, które są w katalogu ~/.ssh
        if data.get("in_ssh_dir", False) and "path" in data:
            identity_file_path = data['path'] # Ścieżka do klucza prywatnego w ~/.ssh
            try:
                # Konwersja na ścieżkę względną z tyldą (~) jeśli to możliwe
                home_dir = os.path.expanduser("~")
                if identity_file_path.startswith(home_dir):
                    identity_file_path = "~" + identity_file_path[len(home_dir):]
                identity_file_path = identity_file_path.replace("\\", "/") # Upewnij się, że są slashe (ważne dla Windows)
            except Exception:
                pass # Jeśli konwersja się nie uda, użyj oryginalnej (absolutnej) ścieżki
            
            # Formatowanie wpisu dla pliku ~/.ssh/config
            lines.append(f"Host {alias}")
            lines.append(f"  HostName {data['host']}")
            lines.append(f"  User git") # Domyślny użytkownik dla GitHuba/GitLaba
            lines.append(f"  IdentityFile {identity_file_path}")
            lines.append(f"  IdentitiesOnly yes") # Dobra praktyka bezpieczeństwa
            lines.append("") # Pusta linia dla czytelności
    
    os.makedirs(os.path.expanduser("~/.ssh"), exist_ok=True) # Upewnij się, że katalog ~/.ssh istnieje
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            f.write("\n".join(lines)) # Zapisz nowe linie do pliku config
        if os.name != 'nt': # Na systemach innych niż Windows (Linux, macOS)
            os.chmod(CONFIG_PATH, 0o600) # Ustaw uprawnienia dla pliku config
    except IOError as e:
        messagebox.showwarning("Błąd zapisu config", f"Nie można zapisać pliku {CONFIG_PATH}: {e}\nSprawdź uprawnienia.")

def show_config():
    """Odczytuje i zwraca zawartość pliku ~/.ssh/config."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Plik {CONFIG_PATH} nie istnieje."

def show_keys_json():
    """Odczytuje i zwraca zawartość bazy danych kluczy (KEYS_DB) jako sformatowany JSON."""
    ensure_db()
    with open(KEYS_DB, "r", encoding="utf-8") as f:
        return json.dumps(json.load(f), indent=4, ensure_ascii=False)

# --- Funkcje obsługi zdarzeń GUI ---
def on_generate():
    """Obsługa kliknięcia przycisku 'Generuj klucz'."""
    msg = generate_key(email_entry.get(), host_var.get(), alias_entry.get())
    messagebox.showinfo("Generowanie Klucza", msg)
    update_keys_display() # Odśwież listę kluczy

def on_delete():
    """Obsługa kliknięcia przycisku 'Usuń klucz'."""
    alias = alias_entry.get()
    if not alias: # Sprawdzenie, czy alias został podany
        messagebox.showwarning("Brak aliasu", "Podaj alias klucza do usunięcia.")
        return
    # Potwierdzenie operacji usunięcia
    if messagebox.askyesno("Potwierdzenie usunięcia", f"Czy na pewno chcesz usunąć klucz '{alias}' (pliki, wpis z bazy i konfiguracji SSH)?"):
        msg = delete_key(alias)
        messagebox.showinfo("Usuwanie Klucza", msg)
        update_keys_display() # Odśwież listę kluczy

def on_move_to_ssh():
    """Obsługa kliknięcia przycisku 'Przenieś do ~/.ssh'."""
    alias = alias_entry.get()
    if not alias: # Sprawdzenie, czy alias został podany
        messagebox.showwarning("Brak aliasu", "Podaj alias klucza do przeniesienia.")
        return
    msg = move_key_to_ssh(alias)
    messagebox.showinfo("Przenoszenie Klucza", msg)
    update_keys_display() # Odśwież listę kluczy

def on_show_config():
    """Obsługa kliknięcia przycisku 'Pokaż ~/.ssh/config'."""
    content = show_config()
    display_text(f"Zawartość pliku: {CONFIG_PATH}", content) # Wyświetl zawartość w nowym oknie

def on_show_json(): 
    """Obsługa kliknięcia przycisku 'Pokaż bazę kluczy'."""
    content = show_keys_json()
    display_text(f"Zawartość pliku: {KEYS_DB}", content) # Wyświetl zawartość w nowym oknie

def display_text(title, content):
    """Tworzy nowe okno (Toplevel) do wyświetlania tekstu."""
    win = tk.Toplevel(root) # Nowe okno podrzędne
    win.title(title)
    win.geometry("700x500") 
    win.configure(bg=DARK_BG) # Ustaw tło dla nowego okna

    text_frame = ttk.Frame(win, padding=10) # Ramka dla ScrolledText i przycisku
    text_frame.pack(fill=tk.BOTH, expand=True)
    
    text_area = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, width=80, height=20, font=("Consolas", 10))
    text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Rozciągnij pole tekstowe
    
    # Stylizacja pola tekstowego
    text_area.configure(bg=ENTRY_BG, fg=LIGHT_FG, insertbackground=LIGHT_FG, relief=tk.FLAT, borderwidth=1, highlightthickness=1, highlightbackground=BORDER_COLOR)
    text_area.insert(tk.END, content) # Wstaw tekst
    text_area.config(state=tk.DISABLED) # Ustaw pole jako tylko do odczytu
    
    # Przycisk "Zamknij" w nowym oknie
    close_button = ttk.Button(win, text="Zamknij", command=win.destroy, style="Accent.TButton") # Użyj specjalnego stylu
    close_button.pack(pady=(5,10)) # Dodaj padding pod przyciskiem


def update_keys_display():
    """Odświeża listę dostępnych kluczy w GUI."""
    keys_listbox.delete(0, tk.END) # Wyczyść aktualną listę
    try:
        ensure_db()
        with open(KEYS_DB, "r", encoding="utf-8") as f:
            keys = json.load(f) # Załaduj metadane kluczy
        if not keys:
            keys_listbox.insert(tk.END, "  Brak kluczy w bazie danych aplikacji.")
        else:
            # Iteruj przez klucze i dodawaj je do Listboxa
            for alias, data in keys.items():
                path_display = data.get('path', 'Brak ścieżki')
                email_display = data.get('email', 'brak emaila')
                status_info = [] # Lista informacji o statusie
                
                # Sprawdzenie istnienia plików kluczy
                priv_key_exists = os.path.exists(path_display)
                pub_key_exists = os.path.exists(path_display + ".pub")

                if priv_key_exists and pub_key_exists:
                    # Można pominąć "Pliki OK" dla czystszego wyglądu
                    pass 
                elif priv_key_exists and not pub_key_exists:
                    status_info.append("BRAK .pub!")
                elif not priv_key_exists and pub_key_exists:
                    status_info.append("BRAK klucza pryw.!")
                elif not priv_key_exists and not pub_key_exists:
                    status_info.append("BRAK plików!")
                
                # Informacja o lokalizacji klucza
                if data.get("in_ssh_dir"):
                    status_info.append("w ~/.ssh")
                else:
                    status_info.append("w folderze aplikacji")
                
                # Formatowanie tekstu statusu (usuwa puste elementy)
                status_text = ", ".join(s for s in status_info if s)
                display_string = f"  Alias: {alias:<18} Email: {email_display:<28} Ścieżka: {path_display} ({status_text})"
                keys_listbox.insert(tk.END, display_string) # Dodaj wpis do Listboxa
    except FileNotFoundError:
        keys_listbox.insert(tk.END, f"  Baza danych ({KEYS_DB}) nie znaleziona.")
    except json.JSONDecodeError:
        keys_listbox.insert(tk.END, "  Błąd odczytu bazy danych (nieprawidłowy JSON).")
    keys_listbox.config(width=0) # Automatyczne dopasowanie szerokości Listboxa

# --- Główne okno aplikacji ---
root = tk.Tk() # Stworzenie głównego okna
root.title("Menedżer Kluczy SSH") # Tytuł okna
root.geometry("980x600") # Rozmiar okna
root.configure(bg=DARK_BG) # Ustawienie ciemnego tła dla głównego okna

# --- Konfiguracja Stylów ttk ---
style = ttk.Style(root) # Inicjalizacja obiektu stylu
style.theme_use('clam') # Wybór motywu bazowego ('clam' jest elastyczny)

# Definicja ogólnych stylów dla widgetów ttk
style.configure('.', background=DARK_BG, foreground=LIGHT_FG, fieldbackground=ENTRY_BG, borderwidth=1, lightcolor=DARK_BG, darkcolor=DARK_BG)
style.map('.', background=[('active', ACTIVE_BUTTON_BG)]) # Efekt hover dla niektórych widgetów

# Style dla poszczególnych typów widgetów ttk
style.configure("TLabel", background=DARK_BG, foreground=LIGHT_FG, padding=2)
style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=LIGHT_FG, insertcolor=LIGHT_FG, bordercolor=BORDER_COLOR)
style.configure("TButton", background=BUTTON_BG, foreground=BUTTON_FG, padding=5, borderwidth=1, relief="raised")
style.map("TButton",
          background=[('pressed', SELECT_BG), ('active', ACTIVE_BUTTON_BG)], # Wygląd przycisku w różnych stanach
          foreground=[('pressed', LIGHT_FG), ('active', LIGHT_FG)],
          relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

style.configure("TLabelFrame", background=DARK_BG, bordercolor=BORDER_COLOR) # Ramki grupujące
style.configure("TLabelFrame.Label", background=DARK_BG, foreground=LIGHT_FG, font=('TkDefaultFont', 9, 'bold')) # Etykieta ramki

style.configure("TCombobox", fieldbackground=ENTRY_BG, background=BUTTON_BG, foreground=LIGHT_FG, arrowcolor=LIGHT_FG, bordercolor=BORDER_COLOR)
style.map('TCombobox', # Wygląd Comboboxa w różnych stanach
          fieldbackground=[('readonly', ENTRY_BG)],
          selectbackground=[('readonly', DARK_BG)], 
          selectforeground=[('readonly', LIGHT_FG)],
          foreground=[('readonly', LIGHT_FG)],
          arrowcolor=[('readonly', LIGHT_FG)])

# Próba stylizacji listy rozwijanej w TCombobox (może nie działać identycznie na wszystkich systemach)
root.option_add('*TCombobox*Listbox.background', ENTRY_BG)
root.option_add('*TCombobox*Listbox.foreground', LIGHT_FG)
root.option_add('*TCombobox*Listbox.selectBackground', SELECT_BG)
root.option_add('*TCombobox*Listbox.selectForeground', LIGHT_FG)
root.option_add('*TCombobox*Listbox.font', ("Consolas", 10))

# Specjalny styl dla przycisku "Zamknij" (akcentujący)
style.configure("Accent.TButton", background=SELECT_BG, foreground=LIGHT_FG, padding=5)
style.map("Accent.TButton",
          background=[('pressed', ACTIVE_BUTTON_BG), ('active', ACTIVE_BUTTON_BG)],
          relief=[('pressed', 'sunken'), ('!pressed', 'raised')])


# --- Układ GUI (rozmieszczenie widgetów w oknie) ---
# Ramka dla pól wejściowych (email, host, alias)
input_frame = ttk.LabelFrame(root, text="Dane Klucza", padding=(10, 10))
input_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=(10,5), sticky="ew") # "ew" = rozciągnij wschód-zachód

# Pola wejściowe
ttk.Label(input_frame, text="E-mail:").grid(row=0, column=0, padx=5, pady=5, sticky="e") # "e" = wyrównaj do prawej (wschód)
email_entry = ttk.Entry(input_frame, width=50)
email_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w") # "w" = wyrównaj do lewej (zachód)

ttk.Label(input_frame, text="Host:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
host_var = tk.StringVar(value="github.com") # Zmienna przechowująca wybraną wartość hosta
host_options = ["github.com", "gitlab.com", "bitbucket.org", "inny_host.com"] # Opcje dla Comboboxa
host_menu = ttk.Combobox(input_frame, textvariable=host_var, values=host_options, width=47, state="readonly") # state="readonly" - użytkownik nie może wpisać własnej wartości
host_menu.set(host_options[0]) # Ustawienie domyślnej wartości
host_menu.grid(row=1, column=1, padx=5, pady=5, sticky="w")

ttk.Label(input_frame, text="Alias:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
alias_entry = ttk.Entry(input_frame, width=50)
alias_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

# Ramka dla przycisków akcji
buttons_frame = ttk.LabelFrame(root, text="Akcje", padding=(10, 10))
buttons_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

btn_width = 20 # Wspólna szerokość dla przycisków

# Przyciski akcji
btn_generate = ttk.Button(buttons_frame, text="Generuj klucz", command=on_generate, width=btn_width)
btn_generate.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

btn_move_to_ssh = ttk.Button(buttons_frame, text="Przenieś do ~/.ssh", command=on_move_to_ssh, width=btn_width)
btn_move_to_ssh.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

btn_delete = ttk.Button(buttons_frame, text="Usuń klucz", command=on_delete, width=btn_width)
btn_delete.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

btn_show_config = ttk.Button(buttons_frame, text="Pokaż ~/.ssh/config", command=on_show_config, width=btn_width)
btn_show_config.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

btn_show_json_db_btn = ttk.Button(buttons_frame, text="Pokaż bazę kluczy", command=on_show_json, width=btn_width)
btn_show_json_db_btn.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

# Konfiguracja rozciągania kolumn w ramce przycisków, aby przyciski wypełniały dostępną przestrzeń
buttons_frame.columnconfigure(0, weight=1)
buttons_frame.columnconfigure(1, weight=1)
buttons_frame.columnconfigure(2, weight=1)

# Ramka dla listy dostępnych kluczy
keys_display_frame = ttk.LabelFrame(root, text="Dostępne Klucze (z bazy aplikacji)", padding=(10,10))
keys_display_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=10) # "nsew" = rozciągnij we wszystkich kierunkach

# Konfiguracja rozciągania wiersza i kolumny głównego okna, aby ramka z listą kluczy się powiększała
root.grid_rowconfigure(2, weight=1) 
root.grid_columnconfigure(0, weight=1) 

# Listbox do wyświetlania kluczy
keys_listbox = tk.Listbox(keys_display_frame, height=10, font=("Consolas", 9), relief=tk.FLAT, borderwidth=1) 
# Stylizacja Listboxa (jest to standardowy widget tk, więc stylizujemy bezpośrednio)
keys_listbox.configure(bg=ENTRY_BG, fg=LIGHT_FG, selectbackground=SELECT_BG, selectforeground=LIGHT_FG, 
                       highlightthickness=1, highlightbackground=BORDER_COLOR, highlightcolor=BORDER_COLOR, bd=1)

# Paski przewijania dla Listboxa (używamy ttk.Scrollbar dla spójności wyglądu)
scrollbar_y = ttk.Scrollbar(keys_display_frame, orient=tk.VERTICAL, command=keys_listbox.yview)
scrollbar_x = ttk.Scrollbar(keys_display_frame, orient=tk.HORIZONTAL, command=keys_listbox.xview)
keys_listbox.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set) # Powiązanie scrollbarów z Listboxem

# Rozmieszczenie scrollbarów i Listboxa w ramce
scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y) # Scrollbar Y po prawej, wypełnia wysokość
scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X) # Scrollbar X na dole, wypełnia szerokość
keys_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True) # Listbox po lewej, wypełnia resztę przestrzeni

update_keys_display() # Pierwsze załadowanie i wyświetlenie listy kluczy

root.mainloop() # Uruchomienie głównej pętli zdarzeń Tkinter
