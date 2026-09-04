import asyncio
import os
import subprocess
import tkinter as tk
import tkinter.messagebox as msgbox

from function.config import CLOSE_LIVE_CAPTIONS_ON_EXIT
from function.livecaptions import close_live_captions, ensure_live_captions
from function.save import choose_save_dir, close_file, prepare_output_file
from function.texthook import hook


exit_event = asyncio.Event()
hook_task = None


async def stop_capture_session():
    """Stop the active hook and finish writing its transcript."""
    global hook_task

    exit_event.set()
    active_task = hook_task
    if active_task is not None:
        try:
            await active_task
        except Exception as exc:
            print(f"Capture task ended with an error: {exc}")
        finally:
            if hook_task is active_task:
                hook_task = None
    await close_file()


def dashboard(loop):
    window = tk.Tk()
    window.title("Save Live Captions")
    window.geometry("372x224+24+24")
    window.resizable(False, False)
    window.overrideredirect(True)
    window.wm_attributes("-topmost", True)

    colors = {
        "background": "#111827",
        "surface": "#1F2937",
        "border": "#334155",
        "primary": "#F43F5E",
        "primary_hover": "#FB7185",
        "recording": "#DC2626",
        "recording_hover": "#EF4444",
        "text": "#F8FAFC",
        "muted": "#94A3B8",
        "ready": "#22C55E",
        "link": "#60A5FA",
        "link_hover": "#93C5FD",
    }

    window.configure(background=colors["border"])
    card = tk.Frame(window, background=colors["background"], padx=1, pady=1)
    card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    header = tk.Frame(card, background=colors["background"], height=42)
    header.pack(fill=tk.X, padx=14, pady=(8, 0))
    header.pack_propagate(False)

    title_label = tk.Label(
        header,
        text="实时字幕保存",
        background=colors["background"],
        foreground=colors["text"],
        font=("Microsoft YaHei UI", 11, "bold"),
    )
    title_label.pack(side=tk.LEFT)

    close_button = tk.Button(
        header,
        text="×",
        command=lambda: request_close(),
        background=colors["background"],
        foreground=colors["muted"],
        activebackground=colors["surface"],
        activeforeground=colors["text"],
        borderwidth=0,
        relief=tk.FLAT,
        font=("Segoe UI", 14),
        cursor="hand2",
        padx=8,
        pady=0,
    )
    close_button.pack(side=tk.RIGHT)

    status_row = tk.Frame(card, background=colors["background"])
    status_row.pack(fill=tk.X, padx=18, pady=(0, 10))

    status_dot = tk.Label(
        status_row,
        text="●",
        background=colors["background"],
        foreground=colors["ready"],
        font=("Segoe UI", 9),
    )
    status_dot.pack(side=tk.LEFT)

    status_label = tk.Label(
        status_row,
        text="字幕已就绪",
        background=colors["background"],
        foreground=colors["muted"],
        font=("Microsoft YaHei UI", 9),
        anchor="w",
    )
    status_label.pack(side=tk.LEFT, padx=(7, 0), fill=tk.X, expand=True)

    file_panel = tk.Frame(
        card,
        background=colors["surface"],
        highlightbackground=colors["border"],
        highlightthickness=1,
    )
    file_panel.pack(fill=tk.X, padx=18, pady=(0, 10))

    file_header = tk.Frame(file_panel, background=colors["surface"])
    file_header.pack(fill=tk.X, padx=10, pady=(7, 0))

    file_title = tk.Label(
        file_header,
        text="当前文件",
        background=colors["surface"],
        foreground=colors["muted"],
        font=("Microsoft YaHei UI", 8),
    )
    file_title.pack(side=tk.LEFT)

    folder_link = tk.Label(
        file_header,
        text="打开目录",
        background=colors["surface"],
        foreground=colors["muted"],
        font=("Microsoft YaHei UI", 8),
        cursor="arrow",
    )
    folder_link.pack(side=tk.RIGHT)

    file_link = tk.Label(
        file_panel,
        text="尚未开始录制",
        background=colors["surface"],
        foreground=colors["muted"],
        font=("Microsoft YaHei UI", 9),
        anchor="w",
        cursor="arrow",
    )
    file_link.pack(fill=tk.X, padx=10, pady=(2, 8))

    toggle_button = tk.Button(
        card,
        text="●  开始录制",
        command=lambda: toggle_capture(),
        background=colors["primary"],
        foreground="#FFFFFF",
        activebackground=colors["primary_hover"],
        activeforeground="#FFFFFF",
        disabledforeground="#CBD5E1",
        borderwidth=0,
        relief=tk.FLAT,
        font=("Microsoft YaHei UI", 10, "bold"),
        cursor="hand2",
        pady=10,
    )
    toggle_button.pack(fill=tk.X, padx=18, pady=(0, 16))

    window.withdraw()
    captions_ready, microphone_enabled = ensure_live_captions()
    if not captions_ready:
        msgbox.showerror(
            "无法打开实时字幕",
            "无法打开 Windows 实时字幕。\n\n"
            "请确认系统为 Windows 11 22H2 或更高版本，并已安装实时字幕语言包。",
        )
        window.destroy()
        return

    window.deiconify()
    if microphone_enabled is False:
        msgbox.showwarning(
            "麦克风音频",
            "实时字幕已经打开，但未能自动启用麦克风音频。\n\n"
            "请在实时字幕窗口中打开：设置 > 首选项 > 包含麦克风音频。",
        )

    session_filename = None
    is_closing = False
    finish_task = None

    async def close_application_window():
        if CLOSE_LIVE_CAPTIONS_ON_EXIT:
            await asyncio.to_thread(close_live_captions)
        if window.winfo_exists():
            window.destroy()

    def set_file_link(filename=None):
        if not filename:
            file_link.config(
                text="尚未开始录制",
                foreground=colors["muted"],
                font=("Microsoft YaHei UI", 9),
                cursor="arrow",
            )
            folder_link.config(foreground=colors["muted"], cursor="arrow")
            return

        file_link.config(
            text=os.path.basename(filename),
            foreground=colors["link"],
            font=("Microsoft YaHei UI", 9, "underline"),
            cursor="hand2",
        )
        folder_link.config(foreground=colors["link"], cursor="hand2")

    def open_current_file(_event=None):
        if not session_filename:
            return
        try:
            os.startfile(os.path.normpath(session_filename))
        except OSError as exc:
            msgbox.showerror("无法打开文件", f"无法打开字幕文件：\n{exc}", parent=window)

    def show_current_file_in_folder(_event=None):
        if not session_filename:
            return
        try:
            subprocess.Popen(
                ["explorer.exe", f"/select,{os.path.normpath(session_filename)}"]
            )
        except OSError as exc:
            msgbox.showerror("无法打开目录", f"无法打开保存目录：\n{exc}", parent=window)

    def set_idle_status(message="字幕已就绪"):
        toggle_button.config(
            text="●  开始录制",
            state=tk.NORMAL,
            background=colors["primary"],
            activebackground=colors["primary_hover"],
        )
        status_dot.config(foreground=colors["ready"])
        status_label.config(text=message, foreground=colors["muted"])

    def set_recording_status():
        toggle_button.config(
            text="■  停止录制",
            state=tk.NORMAL,
            background=colors["recording"],
            activebackground=colors["recording_hover"],
        )
        status_dot.config(foreground=colors["primary"])
        status_label.config(text="正在录制字幕…", foreground=colors["text"])

    def set_stopping_status():
        toggle_button.config(text="正在保存…", state=tk.DISABLED)
        status_dot.config(foreground=colors["muted"])
        status_label.config(text="正在停止并整理字幕…", foreground=colors["muted"])

    def start_capture():
        global hook_task
        nonlocal session_filename

        exit_event.clear()
        selected_filename = choose_save_dir(window)
        try:
            prepare_output_file(selected_filename)
        except OSError as exc:
            msgbox.showerror(
                "无法创建文件",
                f"无法在所选位置创建字幕文件：\n{exc}",
                parent=window,
            )
            set_idle_status("未能开始录制")
            return

        session_filename = selected_filename
        set_file_link(session_filename)
        hook_task = loop.create_task(hook(session_filename, exit_event))
        hook_task.add_done_callback(capture_task_finished)
        set_recording_status()

    async def finish_capture(close_after=False):
        nonlocal finish_task, session_filename

        await stop_capture_session()

        if close_after:
            await close_application_window()
            return

        if session_filename:
            saved_name = os.path.basename(session_filename)
            set_idle_status(f"已保存：{saved_name}")
        else:
            set_idle_status()
        finish_task = None

    async def handle_unexpected_capture_end(completed_task):
        global hook_task

        if hook_task is not completed_task:
            return
        try:
            completed_task.result()
        except Exception as exc:
            print(f"Capture task failed: {exc}")
        hook_task = None
        await close_file()
        set_idle_status("录制意外结束，请重试")

    def capture_task_finished(completed_task):
        if not exit_event.is_set():
            loop.create_task(handle_unexpected_capture_end(completed_task))

    async def close_after_finish(active_finish_task):
        await active_finish_task
        await close_application_window()

    def begin_finish(close_after=False):
        nonlocal finish_task

        if finish_task is not None and not finish_task.done():
            if close_after:
                loop.create_task(close_after_finish(finish_task))
            return
        set_stopping_status()
        finish_task = loop.create_task(finish_capture(close_after=close_after))

    def toggle_capture():
        if hook_task is not None and not hook_task.done():
            begin_finish()
        else:
            start_capture()

    def request_close():
        nonlocal is_closing

        if is_closing:
            return
        is_closing = True
        close_button.config(state=tk.DISABLED)
        begin_finish(close_after=True)

    def start_move(event):
        window.drag_x = event.x_root - window.winfo_x()
        window.drag_y = event.y_root - window.winfo_y()

    def do_move(event):
        x = event.x_root - window.drag_x
        y = event.y_root - window.drag_y
        window.geometry(f"+{x}+{y}")

    for draggable in (header, title_label, status_row, status_dot, status_label):
        draggable.bind("<ButtonPress-1>", start_move)
        draggable.bind("<B1-Motion>", do_move)

    def toggle_enter(_event):
        if str(toggle_button["state"]) != tk.NORMAL:
            return
        if hook_task is not None and not hook_task.done():
            toggle_button.config(background=colors["recording_hover"])
        else:
            toggle_button.config(background=colors["primary_hover"])

    def toggle_leave(_event):
        if hook_task is not None and not hook_task.done():
            toggle_button.config(background=colors["recording"])
        else:
            toggle_button.config(background=colors["primary"])

    toggle_button.bind("<Enter>", toggle_enter)
    toggle_button.bind("<Leave>", toggle_leave)
    file_link.bind("<Button-1>", open_current_file)
    file_link.bind(
        "<Enter>",
        lambda _event: session_filename
        and file_link.config(foreground=colors["link_hover"]),
    )
    file_link.bind(
        "<Leave>",
        lambda _event: session_filename and file_link.config(foreground=colors["link"]),
    )
    folder_link.bind("<Button-1>", show_current_file_in_folder)
    folder_link.bind(
        "<Enter>",
        lambda _event: session_filename
        and folder_link.config(foreground=colors["link_hover"]),
    )
    folder_link.bind(
        "<Leave>",
        lambda _event: session_filename
        and folder_link.config(foreground=colors["link"]),
    )
    close_button.bind(
        "<Enter>",
        lambda _event: close_button.config(foreground=colors["text"]),
    )
    close_button.bind(
        "<Leave>",
        lambda _event: close_button.config(foreground=colors["muted"]),
    )
    window.bind("<Escape>", lambda _event: request_close())
    window.protocol("WM_DELETE_WINDOW", request_close)

    def poll_loop():
        loop.call_soon(loop.stop)
        loop.run_forever()
        try:
            if window.winfo_exists():
                window.after(10, poll_loop)
        except tk.TclError:
            pass

    window.after(10, poll_loop)
    window.mainloop()


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        dashboard(loop)
    finally:
        loop.close()


if __name__ == "__main__":
    main()
