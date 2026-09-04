# Save Live Captions

**Tired of losing live captions on Windows?**  This is a simple tool to save the content of live captions! The saved text document is like following:
><img width="1187" height="477" alt="image" src="https://github.com/user-attachments/assets/78f3a0df-80f3-4e40-bc0e-9137910352c6" />

###  Features

---
- ✨Save live captions to a text file.
- 😃Minimalist floating dashboard.
- **😎Customizable save options. (save location and quality option in `config.py`)**
- Automatically opens Windows Live Captions when needed and tries to include microphone audio.

###  Installation
### Option 1: Quick Start (Executable)
You can download the latest version from the [Releases](../../releases) page.

> [!IMPORTANT]
> **Note on Antivirus Alerts:** If you encounter a malware warning for the `.exe` file, it is likely a **false positive** due to the lack of a digital signature. If you worry about this, try option 2 as follows. 

### Option 2: Run from Source (Recommended for Security)
If you prefer to run the code directly, follow these steps in your bash/PowerShell/cmd:

1. **Clone this repo**:
   ```bash
   git clone https://github.com/LiveCaptionsHelper/SaveLiveCaptions.git
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Run the tool**:
   ```bash
   python src/main.py
   ```
   > **Good News, You can now edit the `src/function/config.py` to modify the quality of saving on your own.**

### Guidelines

---

1. Double click `SaveLiveCaptions.exe`. If Windows Live Captions is not open, the tool starts it through PowerShell and waits for it to become ready. It also tries to enable **Settings > Preferences > Include microphone audio**. A small dashboard will then appear in the top-left corner of your screen. You can drag the background to move this window.

   > Windows does not remember the microphone option and turns it off whenever Live Captions starts. If automatic enablement is unavailable on your Windows build, the tool shows a reminder so you can enable it manually.

2. The dashboard has one recording button. Select **Start recording** to begin, then select the same button again when it changes to **Stop recording**. Stopping saves and cleans the current transcript without closing the dashboard, so another recording can be started immediately.

   The current transcript filename is shown in the dashboard. Click the filename to open the text file, or select **Open folder** to locate it in File Explorer. The link remains available after recording stops.

3. **Start saving:** When you click the circle button, a file dialog will open at the executable's directory. If you cancel the dialog, the captions file is saved beside the executable. When running from source, the project root is used instead.

4. **Stop or exit:** Select **Stop recording** to finish the current transcript. Use the **×** button or press **Esc** to exit; an active recording is saved before the dashboard closes, and Windows Live Captions is closed with it by default. You can find the captions file `YYYY-MM-DD_HH-MM-SS_captions.txt` in the chosen location.

   Set `CLOSE_LIVE_CAPTIONS_ON_EXIT = False` in `src/function/config.py` if you prefer to leave Windows Live Captions running after this tool exits.

![Captions File Example](./assets/captionsFile.png)

## License

This project is licensed under the MIT License.


