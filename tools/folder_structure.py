import os

def generate_folder_structure(directory, output_file):
    def walk_dir(directory, prefix=""):
        excluded_folders = {".git", "venv", "__pycache__", "build", "dist"}
        excluded_extensions = {".ttf"}
        folder_structure = []
        items = sorted(os.listdir(directory))  # Sort for consistent output
        for i, item in enumerate(items):
            path = os.path.join(directory, item)

            # Skip excluded folders or files with excluded extensions
            if item in excluded_folders or os.path.splitext(item)[1].lower() in excluded_extensions:
                continue

            is_last = i == len(items) - 1
            folder_structure.append(f"{prefix}{'└── ' if is_last else '├── '}{item}")
            if os.path.isdir(path):
                sub_prefix = prefix + ("    " if is_last else "│   ")
                folder_structure.extend(walk_dir(path, sub_prefix))
        return folder_structure

    try:
        folder_structure = walk_dir(directory)
        with open(output_file, "w", encoding="utf-8") as f:  # Explicitly set UTF-8 encoding
            f.write("\n".join(folder_structure))
        print(f"Folder structure written to {output_file}")
    except Exception as e:
        print(f"Error: {e}")

# Entry point for the script
if __name__ == "__main__":
    # Resolve the directory where `main.py` resides (two levels up)
    base_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    output_file = os.path.join(base_directory, "folder_structure.txt")
    generate_folder_structure(base_directory, output_file)
