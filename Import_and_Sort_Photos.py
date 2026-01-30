import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import threading
from datetime import datetime
import shutil
import re

# Try to import PIL for Exif data
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

class PhotoImporterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo Import & Sort")
        self.root.geometry("600x450")
        
        # Variables
        self.source_path = tk.StringVar()
        self.dest_path = tk.StringVar(value="D:\\Photos")
        self.delete_source = tk.BooleanVar(value=False)
        self.is_running = False

        # GUI Layout
        self.create_widgets()
        
        # Initial scan for source
        self.scan_for_source_drive()

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Source Section
        ttk.Label(main_frame, text="Source Folder:").grid(row=0, column=0, sticky="w", pady=5)
        self.source_entry = ttk.Entry(main_frame, textvariable=self.source_path, width=40)
        self.source_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(main_frame, text="Browse...", command=self.browse_source).grid(row=0, column=2, pady=5)

        # Destination Section
        ttk.Label(main_frame, text="Destination Folder:").grid(row=1, column=0, sticky="w", pady=5)
        self.dest_entry = ttk.Entry(main_frame, textvariable=self.dest_path, width=40)
        self.dest_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(main_frame, text="Browse...", command=self.browse_dest).grid(row=1, column=2, pady=5)

        # Options
        ttk.Checkbutton(main_frame, text="Delete source files after successful transfer", 
                        variable=self.delete_source).grid(row=2, column=0, columnspan=3, sticky="w", pady=15)

        # Action Button
        self.import_btn = ttk.Button(main_frame, text="Import and Sort", command=self.start_import_thread)
        self.import_btn.grid(row=3, column=0, columnspan=3, pady=10, sticky="ew")

        # Log Area
        self.log_area = tk.Text(main_frame, height=10, width=60, state='disabled')
        self.log_area.grid(row=4, column=0, columnspan=3, pady=10, sticky="nsew")
        
        # Grid config
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(4, weight=1)

    def log(self, message):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_path.set(path)

    def browse_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_path.set(path)

    def scan_for_source_drive(self):
        self.log("Scanning drives for DCIM folder...")
        drives = [f"{d}:\\" for d in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{d}:\\")]
        
        found_path = None
        for drive in drives:
            dcim_path = os.path.join(drive, "DCIM")
            if os.path.exists(dcim_path):
                try:
                    # Look for folders matching ###_FUJI
                    for folder in os.listdir(dcim_path):
                        if re.match(r"^\d{3}_FUJI$", folder):
                            found_path = os.path.join(dcim_path, folder)
                            self.log(f"Found source: {found_path}")
                            break
                except OSError:
                    continue
            if found_path:
                break
        
        if found_path:
            self.source_path.set(found_path)
        else:
            self.log("No automatic source folder found.")

    def start_import_thread(self):
        if self.is_running:
            return
        
        source = self.source_path.get()
        dest = self.dest_path.get()
        
        if not source or not os.path.exists(source):
            messagebox.showerror("Error", "Invalid source folder.")
            return
        
        if not dest:
            messagebox.showerror("Error", "Invalid destination folder.")
            return

        self.is_running = True
        self.import_btn.config(state='disabled')
        
        thread = threading.Thread(target=self.run_import_process)
        thread.daemon = True
        thread.start()

    def get_date_taken(self, path):
        if PIL_AVAILABLE:
            try:
                img = Image.open(path)
                exif = img._getexif()
                if exif:
                    for tag, value in exif.items():
                        decoded = TAGS.get(tag, tag)
                        if decoded == 'DateTimeOriginal':
                            # Format: YYYY:MM:DD HH:MM:SS
                            return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
            except Exception:
                pass
        return datetime.fromtimestamp(os.path.getmtime(path))

    def run_import_process(self):
        try:
            source = self.source_path.get()
            dest_root = self.dest_path.get()
            extensions = {'.JPG', '.JPEG', '.RAF', '.HEIF', '.HEIC'}
            
            files_to_process = []
            for root, dirs, files in os.walk(source):
                for file in files:
                    ext = os.path.splitext(file)[1].upper()
                    if ext in extensions:
                        files_to_process.append(os.path.join(root, file))
            
            total_files = len(files_to_process)
            if total_files == 0:
                self.log("No matching files found in source.")
                return

            self.log(f"Found {total_files} files. Starting import...")
            
            processed_count = 0
            errors = 0
            
            for src_file in files_to_process:
                try:
                    # 1. Get Date
                    date_taken = self.get_date_taken(src_file)
                    date_folder = date_taken.strftime('%Y-%m-%d')
                    
                    # 2. Determine Destination
                    ext_folder = os.path.splitext(src_file)[1].upper().lstrip('.')
                    dest_dir = os.path.join(dest_root, date_folder, ext_folder)
                    os.makedirs(dest_dir, exist_ok=True)
                    
                    filename = os.path.basename(src_file)
                    dest_file = os.path.join(dest_dir, filename)
                    
                    # Handle duplicates (Skip if exists)
                    if os.path.exists(dest_file):
                        self.log(f"Skipping duplicate: {filename}")
                        # If we want to be safe, we don't delete source if we skipped copy? 
                        # Or do we assume it's safely there? 
                        # User requirement: "delete source files after succesful transfer".
                        # If it exists, transfer didn't happen NOW, but it is there.
                        # I will verify the existing file size matches source before considering it 'safe'.
                        if os.path.getsize(src_file) == os.path.getsize(dest_file):
                            if self.delete_source.get():
                                os.remove(src_file)
                        processed_count += 1
                        continue

                    # 3. Copy
                    shutil.copy2(src_file, dest_file)
                    
                    # 4. Verify
                    if os.path.exists(dest_file) and os.path.getsize(src_file) == os.path.getsize(dest_file):
                        # 5. Delete if requested
                        if self.delete_source.get():
                            os.remove(src_file)
                            self.log(f"Moved: {filename}")
                        else:
                            self.log(f"Copied: {filename}")
                    else:
                        self.log(f"Verification failed for: {filename}")
                        errors += 1
                        
                except Exception as e:
                    self.log(f"Error processing {src_file}: {e}")
                    errors += 1
                
                processed_count += 1
                if processed_count % 10 == 0:
                    self.root.update_idletasks() # Keep UI responsive

            self.log(f"Import complete. Processed: {processed_count}, Errors: {errors}")
            messagebox.showinfo("Done", f"Import complete.\nProcessed: {processed_count}\nErrors: {errors}")

        except Exception as e:
            self.log(f"Critical Error: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.import_btn.config(state='normal'))

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoImporterApp(root)
    root.mainloop()
