"""Generate QR code PNG files from inventory numbers in a text or CSV file."""

import csv
import json
import os
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable


def load_inventory_numbers(input_path: Path) -> list[str]:
    """Read non-empty inventory numbers, one per line."""
    text = input_path.read_text(encoding="utf-8-sig")
    numbers = [line.strip() for line in text.splitlines() if line.strip()]
    if not numbers:
        raise ValueError("Wybrany plik nie zawiera numerów inwentarzowych.")
    return numbers


def make_safe_filename(value: str) -> str:
    """Replace characters that Windows does not allow in file names."""
    safe_name = "".join(
        character if character not in '<>:/\\|?*' and ord(character) >= 32 else "_"
        for character in value
    ).strip(" .")
    return safe_name or "numer_inwentarzowy"


def build_output_names(
    numbers: list[str], output_directory: Path, existing_mode: str
) -> list[str]:
    """Calculate unique output names using the same rules as generation."""
    names = []
    used_names: set[str] = set()
    for number in numbers:
        base_name = make_safe_filename(number)
        filename = f"{base_name}.png"
        suffix = 2
        while filename.casefold() in used_names:
            filename = f"{base_name}_{suffix}.png"
            suffix += 1

        if existing_mode == "rename":
            while (output_directory / filename).exists():
                filename = f"{base_name}_{suffix}.png"
                suffix += 1
                while filename.casefold() in used_names:
                    filename = f"{base_name}_{suffix}.png"
                    suffix += 1

        used_names.add(filename.casefold())
        names.append(filename)
    return names


def build_qr_image(number: str, show_label: bool, box_size: int, border: int):
    """Create the final QR image, including its optional printed label."""
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(number)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    if show_label:
        margin_pixels = border * box_size
        font_size = max(box_size * 2, margin_pixels // 2, 18)
        font_size = min(font_size, max(18, image.width // 8))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            try:
                font = ImageFont.load_default(size=font_size)
            except TypeError:
                font = ImageFont.load_default()
        draw = ImageDraw.Draw(image)
        bounds = draw.textbbox((0, 0), number, font=font)
        label_width = bounds[2] - bounds[0]
        label_height = bounds[3] - bounds[1]
        label_gap = max(box_size, min(margin_pixels // 4, image.width // 10))
        canvas_width = max(image.width, label_width + box_size * 2)
        canvas = Image.new(
            "RGB", (canvas_width, image.height + label_height + label_gap * 2), "white"
        )
        canvas.paste(image, ((canvas_width - image.width) // 2, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text(
            ((canvas_width - label_width) // 2, image.height + label_gap - bounds[1]),
            number,
            fill="black",
            font=font,
        )
        image = canvas
    return image


def get_settings_path() -> Path:
    app_data = Path(os.environ.get("APPDATA", Path.home()))
    return app_data / "GeneratorKodowQR" / "settings.json"


def load_settings() -> dict:
    try:
        settings = json.loads(get_settings_path().read_text(encoding="utf-8"))
        return settings if isinstance(settings, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(*_args) -> None:
    try:
        settings = {
            "input_path": input_path_var.get(),
            "output_directory": output_directory_var.get(),
            "show_label": show_label_var.get(),
            "existing_mode": existing_mode_var.get(),
            "theme": theme_var.get(),
        }
    except tk.TclError:
        return
    settings_path = get_settings_path()
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def preview_input() -> None:
    input_value = input_path_var.get()
    if not input_value:
        messagebox.showwarning("Brak pliku", "Najpierw wybierz plik z numerami.")
        return

    input_path = Path(input_value)
    try:
        content = input_path.read_text(encoding="utf-8-sig")
    except OSError as error:
        messagebox.showerror("Nie można odczytać pliku", str(error))
        return
    show_preview_window(input_path, content)


def preview_label() -> None:
    input_value = input_path_var.get()
    if not input_value:
        messagebox.showwarning("Brak pliku", "Najpierw wybierz plik z numerami.")
        return
    try:
        numbers = load_inventory_numbers(Path(input_value))
        from PIL import ImageTk

        image = build_qr_image(
            numbers[0],
            show_label_var.get(),
            10,
            4,
        )
        image.thumbnail((360, 360))
        photo = ImageTk.PhotoImage(image)
    except (OSError, RuntimeError, ValueError, ImportError) as error:
        messagebox.showerror("Nie można przygotować podglądu", str(error))
        return

    global label_preview_window, label_preview_image
    if label_preview_window is None or not label_preview_window.winfo_exists():
        label_preview_window = tk.Toplevel(root)
        label_preview_window.title("Podgląd etykiety")
        label_preview_window.geometry("420x460")
        label_preview_window.configure(bg="#f4f6fb")
        label_preview_heading = ttk.Label(
            label_preview_window, text="Przykładowa etykieta", style="Header.TLabel"
        )
        label_preview_heading.pack(pady=(20, 12))
        label_preview_display = tk.Label(label_preview_window, bd=0, padx=16, pady=16)
        label_preview_display.pack(expand=True)
        label_preview_window.display = label_preview_display
    label_preview_image = photo
    label_preview_window.display.configure(image=photo)
    label_preview_window.display.image = photo
    label_preview_window.lift()


def generate_qr_codes(
    numbers: list[str],
    output_directory: Path,
    show_label: bool,
    box_size: int,
    border: int,
    existing_mode: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> tuple[int, int, Path]:
    """Create QR PNGs and a CSV report. Return created, skipped and report path."""
    try:
        import qrcode  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError as error:
        raise RuntimeError(
            "Brakuje wymaganej biblioteki. Zainstaluj ją poleceniem:\n"
            "py -m pip install \"qrcode[pil]\""
        ) from error

    output_directory.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    report_rows = []
    output_names = build_output_names(numbers, output_directory, existing_mode)

    for index, (number, filename) in enumerate(zip(numbers, output_names), start=1):
        output_path = output_directory / filename

        if output_path.exists() and existing_mode == "skip":
            skipped += 1
            report_rows.append((number, filename, "pominięto — plik już istnieje"))
            if progress_callback:
                progress_callback(index, len(numbers), filename)
            continue
        image = build_qr_image(number, show_label, box_size, border)
        image.save(output_path)
        created += 1
        report_rows.append((number, filename, "zapisano"))
        if progress_callback:
            progress_callback(index, len(numbers), filename)

    report_path = output_directory / "raport_generowania.csv"
    with report_path.open("w", newline="", encoding="utf-8-sig") as report_file:
        writer = csv.writer(report_file, delimiter=";")
        writer.writerow(["Numer inwentarzowy", "Plik", "Status"])
        writer.writerows(report_rows)

    return created, skipped, report_path


def choose_input_file() -> None:
    selected_path = filedialog.askopenfilename(
        title="Wybierz plik z numerami inwentarzowymi",
        filetypes=[("Pliki tekstowe i CSV", "*.txt *.csv"), ("Wszystkie pliki", "*.*")],
    )
    if selected_path:
        input_path_var.set(selected_path)


def choose_output_directory() -> None:
    selected_path = filedialog.askdirectory(title="Wybierz folder zapisu kodów QR")
    if selected_path:
        output_directory_var.set(selected_path)


def start_generation() -> None:
    input_value = input_path_var.get()
    output_value = output_directory_var.get()
    if not input_value or not output_value:
        messagebox.showwarning("Brak wyboru", "Wskaż plik wejściowy i folder zapisu.")
        return

    generate_button.configure(state="disabled")
    progress_bar.configure(maximum=1, value=0)
    progress_status_var.set("Przygotowywanie...")

    def update_progress(current: int, total: int, filename: str) -> None:
        progress_bar.configure(maximum=total, value=current)
        progress_status_var.set(f"{current}/{total}  •  {filename}")
        root.update_idletasks()

    try:
        numbers = load_inventory_numbers(Path(input_value))
        created, skipped, report_path = generate_qr_codes(
            numbers=numbers,
            output_directory=Path(output_value),
            show_label=show_label_var.get(),
            box_size=10,
            border=4,
            existing_mode=existing_mode_var.get(),
            progress_callback=update_progress,
        )
    except (OSError, RuntimeError, ValueError, tk.TclError) as error:
        progress_status_var.set("Wystąpił błąd podczas generowania")
        generate_button.configure(state="normal")
        messagebox.showerror("Nie udało się wygenerować kodów", str(error))
        return

    generate_button.configure(state="normal")
    progress_status_var.set(f"Zakończono: {created} zapisano, {skipped} pominięto")
    save_settings()
    messagebox.showinfo(
        "Gotowe",
        f"Zapisano kodów QR: {created}\nPominięto: {skipped}\nRaport: {report_path}",
    )


root = tk.Tk()
root.title("Generator kodów QR")
root.resizable(False, False)
root.configure(bg="#f4f6fb")

style = ttk.Style(root)
style.theme_use("clam")
style.configure("Header.TLabel", font=("Segoe UI", 19, "bold"))
style.configure("Subheader.TLabel", font=("Segoe UI", 10))
style.configure("CardTitle.TLabel", font=("Segoe UI", 11, "bold"))
style.configure("CardHint.TLabel", font=("Segoe UI", 9))
style.configure("TLabel", font=("Segoe UI", 10))
style.configure("TButton", font=("Segoe UI", 9), padding=(10, 7), relief="flat")
style.configure(
    "Accent.TButton",
    font=("Segoe UI", 10, "bold"),
    padding=(16, 10),
    relief="flat",
)
style.configure("Theme.TButton", font=("Segoe UI", 9, "bold"), padding=(10, 7))
style.configure("TEntry", padding=8)
style.configure("TSpinbox", padding=5)

saved_settings = load_settings()


input_path_var = tk.StringVar(value=saved_settings.get("input_path", ""))
output_directory_var = tk.StringVar(value=saved_settings.get("output_directory", ""))
show_label_var = tk.BooleanVar(value=saved_settings.get("show_label", True))
existing_mode = saved_settings.get("existing_mode", "skip")
existing_mode_var = tk.StringVar(value=existing_mode if existing_mode in {"skip", "overwrite", "rename"} else "skip")
saved_theme = saved_settings.get("theme", "light")
theme_var = tk.StringVar(value=saved_theme if saved_theme in {"light", "dark"} else "light")
progress_status_var = tk.StringVar(value="Gotowe do pracy")
preview_window = None
preview_text = None
preview_summary_var = None
preview_source_path = None
label_preview_window = None
label_preview_image = None

app = ttk.Frame(root, style="App.TFrame", padding=(24, 20, 24, 22))
app.grid(sticky="nsew")
app.columnconfigure(0, weight=1)

header = ttk.Frame(app, style="App.TFrame")
header.grid(row=0, column=0, sticky="ew")
header.columnconfigure(0, weight=1)
ttk.Label(header, text="Generator kodów QR", style="Header.TLabel").grid(row=0, column=0, sticky="w")
theme_button = ttk.Button(header, text="☾  Tryb ciemny", style="Theme.TButton", command=lambda: toggle_theme())
theme_button.grid(row=0, column=1, sticky="e")
ttk.Label(
    app,
    text="Przygotuj czytelne etykiety z numerów inwentarzowych.",
    style="Subheader.TLabel",
).grid(row=1, column=0, sticky="w", pady=(3, 18))

files_card = ttk.Frame(app, style="Card.TFrame", padding=16)
files_card.grid(row=2, column=0, sticky="ew", pady=(0, 12))
files_card.columnconfigure(0, weight=1)
ttk.Label(files_card, text="Dane wejściowe i miejsce zapisu", style="CardTitle.TLabel").grid(
    row=0, column=0, columnspan=2, sticky="w", pady=(0, 12)
)
ttk.Label(files_card, text="Plik z numerami", style="CardHint.TLabel").grid(
    row=1, column=0, columnspan=2, sticky="w", pady=(0, 4)
)
ttk.Entry(files_card, textvariable=input_path_var, width=55, state="readonly").grid(
    row=2, column=0, sticky="ew", padx=(0, 8)
)
ttk.Button(files_card, text="Wybierz plik", command=choose_input_file).grid(row=2, column=1)
ttk.Label(files_card, text="Folder docelowy", style="CardHint.TLabel").grid(
    row=3, column=0, columnspan=2, sticky="w", pady=(12, 4)
)
ttk.Entry(files_card, textvariable=output_directory_var, width=55, state="readonly").grid(
    row=4, column=0, sticky="ew", padx=(0, 8)
)
ttk.Button(files_card, text="Wybierz folder", command=choose_output_directory).grid(row=4, column=1)

settings_card = ttk.Frame(app, style="Card.TFrame", padding=16)
settings_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
settings_card.columnconfigure(1, weight=1)
ttk.Label(settings_card, text="Wygląd etykiety", style="CardTitle.TLabel").grid(
    row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
)
ttk.Checkbutton(settings_card, text="Umieść numer pod kodem QR", variable=show_label_var).grid(
    row=1, column=0, columnspan=2, sticky="w", pady=(0, 8)
)

existing_card = ttk.Frame(app, style="Card.TFrame", padding=16)
existing_card.grid(row=4, column=0, sticky="ew", pady=(0, 14))
ttk.Label(existing_card, text="Jeśli plik już istnieje", style="CardTitle.TLabel").grid(
    row=0, column=0, sticky="w", pady=(0, 7)
)
for row, (label, value) in enumerate(
    [("Pomiń", "skip"), ("Nadpisz", "overwrite"), ("Zapisz pod nową nazwą", "rename")],
    start=1,
):
    ttk.Radiobutton(existing_card, text=label, variable=existing_mode_var, value=value).grid(
        row=row, column=0, sticky="w", pady=2
    )

actions = ttk.Frame(app, style="App.TFrame")
actions.grid(row=5, column=0, sticky="ew")
ttk.Button(actions, text="Podgląd i edycja danych", command=preview_input).grid(
    row=0, column=0, sticky="w"
)
ttk.Button(actions, text="Podgląd etykiety", command=preview_label).grid(
    row=0, column=1, sticky="e", padx=(8, 8)
)
generate_button = ttk.Button(
    actions, text="Generuj kody QR", style="Accent.TButton", command=start_generation
)
generate_button.grid(
    row=0, column=2, sticky="e"
)
actions.columnconfigure(0, weight=1)

progress_frame = ttk.Frame(app, style="App.TFrame")
progress_frame.grid(row=6, column=0, sticky="ew", pady=(12, 0))
ttk.Label(progress_frame, textvariable=progress_status_var, style="Subheader.TLabel").grid(
    row=0, column=0, sticky="w", pady=(0, 5)
)
progress_bar = ttk.Progressbar(progress_frame, mode="determinate", maximum=1, value=0)
progress_bar.grid(row=1, column=0, sticky="ew")
progress_frame.columnconfigure(0, weight=1)


def apply_theme(theme_name: str) -> None:
    palette = {
        "light": {
            "background": "#f4f6fb",
            "surface": "#ffffff",
            "field": "#f8fafc",
            "text": "#172033",
            "muted": "#64748b",
            "border": "#dce3ef",
            "accent": "#3157d5",
            "accent_active": "#2446b8",
            "selected": "#e8edff",
            "text_selection": "#3157d5",
        },
        "dark": {
            "background": "#181818",
            "surface": "#242424",
            "field": "#1e1e1e",
            "text": "#eeeeee",
            "muted": "#a3a3a3",
            "border": "#3b3b3b",
            "accent": "#505050",
            "accent_active": "#666666",
            "selected": "#353535",
            "text_selection": "#505050",
        },
    }[theme_name]

    root.configure(bg=palette["background"])
    style.configure("App.TFrame", background=palette["background"])
    style.configure("Card.TFrame", background=palette["surface"])
    style.configure(
        "Header.TLabel", background=palette["background"], foreground=palette["text"]
    )
    style.configure(
        "Subheader.TLabel", background=palette["background"], foreground=palette["muted"]
    )
    style.configure(
        "CardTitle.TLabel", background=palette["surface"], foreground=palette["text"]
    )
    style.configure(
        "CardHint.TLabel", background=palette["surface"], foreground=palette["muted"]
    )
    style.configure("TLabel", background=palette["surface"], foreground=palette["text"])
    style.configure(
        "TButton",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["border"],
        focuscolor=palette["accent"],
    )
    style.map(
        "TButton",
        background=[("active", palette["selected"])],
        foreground=[("disabled", palette["muted"])],
    )
    style.configure(
        "Theme.TButton",
        background=palette["surface"],
        foreground=palette["text"],
        bordercolor=palette["border"],
    )
    style.configure(
        "Accent.TButton",
        background=palette["accent"],
        foreground="#ffffff",
        bordercolor=palette["accent"],
    )
    style.map("Accent.TButton", background=[("active", palette["accent_active"])])
    style.configure(
        "TEntry",
        fieldbackground=palette["field"],
        foreground=palette["text"],
        bordercolor=palette["border"],
        insertcolor=palette["text"],
    )
    style.configure(
        "TSpinbox",
        fieldbackground=palette["field"],
        foreground=palette["text"],
        arrowcolor=palette["muted"],
        bordercolor=palette["border"],
    )
    style.configure(
        "TRadiobutton",
        background=palette["surface"],
        foreground=palette["text"],
        indicatorcolor=palette["field"],
    )
    style.map("TRadiobutton", background=[("active", palette["surface"])])
    style.configure(
        "TCheckbutton",
        background=palette["surface"],
        foreground=palette["text"],
        indicatorcolor=palette["field"],
    )
    style.map("TCheckbutton", background=[("active", palette["surface"])])

    theme_button.configure(text="☾  Tryb ciemny" if theme_name == "light" else "☀  Tryb jasny")
    if preview_window is not None and preview_window.winfo_exists():
        preview_window.configure(bg=palette["background"])
        if preview_text is not None:
            preview_text.configure(
                bg=palette["surface"],
                fg=palette["text"],
                insertbackground=palette["text"],
                selectbackground=palette["text_selection"],
            )
    if label_preview_window is not None and label_preview_window.winfo_exists():
        label_preview_window.configure(bg=palette["background"])
        label_preview_window.display.configure(bg=palette["surface"])


def toggle_theme() -> None:
    next_theme = "dark" if theme_var.get() == "light" else "light"
    theme_var.set(next_theme)
    apply_theme(next_theme)


def build_preview_summary(content: str) -> str:
    numbers = [line.strip() for line in content.splitlines() if line.strip()]
    if not numbers:
        return "Brak numerów. Wpisz po jednym numerze w każdym wierszu."

    counts = Counter(numbers)
    duplicates = {number: count for number, count in counts.items() if count > 1}
    output_directory = Path(output_directory_var.get()) if output_directory_var.get() else Path.cwd()
    filenames = build_output_names(numbers, output_directory, existing_mode_var.get())
    lines = [
        f"{len(numbers)} numerów  ·  {len(counts)} unikalnych  ·  "
        f"{sum(count - 1 for count in duplicates.values())} duplikatów",
        "",
        "Przykładowe nazwy plików:",
    ]
    lines.extend(f"{number}  →  {filename}" for number, filename in zip(numbers[:12], filenames[:12]))
    if len(numbers) > 12:
        lines.append(f"… oraz {len(numbers) - 12} kolejnych")
    return "\n".join(lines)


def refresh_preview_summary(_event=None) -> None:
    if preview_text is not None and preview_summary_var is not None:
        preview_summary_var.set(build_preview_summary(preview_text.get("1.0", "end-1c")))


def save_preview_changes() -> bool:
    if preview_text is None or preview_source_path is None:
        return False
    try:
        content = preview_text.get("1.0", "end-1c")
        preview_source_path.write_text(content, encoding="utf-8")
    except OSError as error:
        messagebox.showerror("Nie udało się zapisać pliku", str(error), parent=preview_window)
        return False
    preview_text.edit_modified(False)
    refresh_preview_summary()
    progress_status_var.set("Zapisano zmiany w pliku z numerami")
    return True


def close_preview_window() -> None:
    if preview_text is not None and preview_text.edit_modified():
        should_save = messagebox.askyesnocancel(
            "Niezapisane zmiany",
            "Zapisać zmiany w pliku z numerami przed zamknięciem?",
            parent=preview_window,
        )
        if should_save is None:
            return
        if should_save and not save_preview_changes():
            return
    preview_window.destroy()


def show_preview_window(source_path: Path, content: str) -> None:
    global preview_window, preview_text, preview_summary_var, preview_source_path
    preview_source_path = source_path
    if preview_window is None or not preview_window.winfo_exists():
        preview_window = tk.Toplevel(root)
        preview_window.title("Edytuj numery inwentarzowe")
        preview_window.geometry("760x620")
        preview_window.minsize(600, 450)
        preview_window.protocol("WM_DELETE_WINDOW", close_preview_window)
        dark_mode = theme_var.get() == "dark"
        preview_background = "#181818" if dark_mode else "#f4f6fb"
        text_background = "#1e1e1e" if dark_mode else "#ffffff"
        text_foreground = "#eeeeee" if dark_mode else "#172033"
        preview_window.configure(bg=preview_background)
        preview_frame = ttk.Frame(preview_window, style="App.TFrame", padding=16)
        preview_frame.pack(fill="both", expand=True)
        ttk.Label(preview_frame, text="Lista numerów", style="Header.TLabel").pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Label(
            preview_frame,
            text="Edytuj numery bezpośrednio. Każdy wiersz zostanie zapisany jako osobny kod QR.",
            style="Subheader.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        text_frame = ttk.Frame(preview_frame, style="Card.TFrame", padding=8)
        text_frame.pack(fill="both", expand=True, pady=(0, 10))
        preview_text = tk.Text(
            text_frame,
            wrap="word",
            font=("Segoe UI", 11),
            bg=text_background,
            fg=text_foreground,
            insertbackground=text_foreground,
            selectbackground="#505050" if dark_mode else "#3157d5",
            relief="flat",
            padx=12,
            pady=10,
            undo=True,
        )
        preview_text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=preview_text.yview)
        scrollbar.pack(side="right", fill="y")
        preview_text.configure(yscrollcommand=scrollbar.set)
        preview_text.bind("<KeyRelease>", refresh_preview_summary)
        preview_summary_var = tk.StringVar()
        summary = ttk.Label(
            preview_frame, textvariable=preview_summary_var, style="Subheader.TLabel", justify="left"
        )
        summary.pack(anchor="w", pady=(0, 12))
        footer = ttk.Frame(preview_frame, style="App.TFrame")
        footer.pack(fill="x")
        ttk.Button(footer, text="Zamknij", command=close_preview_window).pack(side="right")
        ttk.Button(footer, text="Zapisz zmiany", style="Accent.TButton", command=save_preview_changes).pack(
            side="right", padx=(0, 8)
        )

    preview_text.delete("1.0", tk.END)
    preview_text.insert("1.0", content)
    preview_text.edit_modified(False)
    refresh_preview_summary()
    preview_window.deiconify()
    preview_window.lift()


for setting_var in (
    input_path_var,
    output_directory_var,
    show_label_var,
    existing_mode_var,
    theme_var,
):
    setting_var.trace_add("write", save_settings)

apply_theme(theme_var.get())
root.mainloop()
