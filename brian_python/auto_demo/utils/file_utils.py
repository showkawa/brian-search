import os

def load_file(filename: str) -> str:
    """Loads a file into a string."""
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File {filename} not found.")
    f = open(filename, 'r', encoding='utf-8')
    s = f.read()
    f.close()
    return s


def save_file(filename: str, content: str) -> bool:
    """Saves a string into a file."""
    try:
        f = open(filename, 'w', encoding='utf-8')
        f.write(content)
        f.close()
    except Exception as e:
        print(e)
        return False
    return True
