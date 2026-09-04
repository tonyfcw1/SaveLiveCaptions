import sys
import os
import asyncio
import tkinter as tk
from tkinter import filedialog
import time
import aiofiles
from difflib import SequenceMatcher
import re
from function.transformation import word_to_number

saved_captions: list[tuple[float, str]] = [] # time, caption
save_dir = ""


def get_default_save_dir() -> str:
    """Return the executable directory, or the project root when run as source."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))

    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def normalize_sentence(s: str) -> str:
    s = s.strip()
    # space
    s = re.sub(r'\s+', ' ', s)
    # lower letter
    s = s.lower()
    # "twenty twenty six" -> "2026"
    s = word_to_number(s)
    # symbol
    s = re.sub(r'\s+([.,!?])', r'\1', s)
    return s

def similarity_ratio(s1: str, s2: str) -> float:
    """calculate the similarity"""
    norm1 = normalize_sentence(s1)
    norm2 = normalize_sentence(s2)
    return SequenceMatcher(None, norm1, norm2).ratio()

def choose_save_dir(parent=None):
    global save_dir
    
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())  

    if not save_dir:
        dialog_parent = parent
        owns_root = dialog_parent is None
        if owns_root:
            dialog_parent = tk.Tk()
            dialog_parent.withdraw()

        save_dir = filedialog.askdirectory(
            title="选择字幕保存目录",
            initialdir=get_default_save_dir(),
            parent=dialog_parent,
        )
        if owns_root:
            dialog_parent.destroy()

        if not save_dir:
            save_dir = get_default_save_dir()
            os.makedirs(save_dir, exist_ok=True)
    
    filename = os.path.join(save_dir, f"{timestamp}_captions.txt")
    suffix = 2
    while os.path.exists(filename):
        filename = os.path.join(save_dir, f"{timestamp}_captions_{suffix}.txt")
        suffix += 1
    
    return filename


def prepare_output_file(filename: str) -> None:
    """Create the selected output file so it can be opened immediately."""
    parent_dir = os.path.dirname(os.path.abspath(filename))
    os.makedirs(parent_dir, exist_ok=True)
    with open(filename, "a", encoding="utf-8"):
        pass


async def save_replace_txt(filename,old_caption: tuple[float, str], new_caption: tuple[float, str]):
    ''' Replace old caption with new caption '''
    t_old, cap_old = old_caption
    _, cap_new = new_caption
    t_formatted = time.strftime("%H:%M:%S", time.localtime(t_old))
    
    # read file and replace line
    async with aiofiles.open(filename, "r", encoding="utf-8") as f:
        lines = await f.readlines()
    
    for idx, line in enumerate(lines):
        if t_formatted in line and cap_old in line:
            lines[idx] = f"[{t_formatted}] {cap_new}\n"
            print(f"[REPLACE] Replaced:\n  OLD: {cap_old}\n  NEW: {cap_new}")
            break
    
    # write back to file
    async with aiofiles.open(filename, "w", encoding="utf-8") as f:
        await f.writelines(lines)

async def save_txt(filename,new_caption: tuple[float, str]):
    ''' Add new caption '''
    t, cap = new_caption
    t_formatted = time.strftime("%H:%M:%S", time.localtime(t))
    
    # write file
    async with aiofiles.open(filename, "a", encoding="utf-8") as f:
        await f.write(f"[{t_formatted}] {cap}\n")

async def close_file():
    # Kept as part of the capture lifecycle API. Writes use scoped handles, so
    # there is no persistent file handle to close.
    return None
