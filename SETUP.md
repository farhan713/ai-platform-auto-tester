# Skylar IQ QA Tool — Quick Setup (No Git Required)

> **Read time: 5 minutes. One-time setup, then double-click to launch every day.**

You don't need git, GitHub, or any developer experience. Just follow the steps for your operating system.

---

## What you need before starting

- A computer running **Mac**, **Windows**, or **Linux**
- **Python 3.10 or newer** ([download here](https://www.python.org/downloads/) if you don't have it)
- About **5 minutes** of time and **200 MB** of free disk space
- An internet connection (one-time, for downloads)

To check if Python is already installed, open a terminal and type:

```
python3 --version
```

You should see something like `Python 3.11.6`. If you see "command not found" or a version below 3.10, install Python first from the link above.

---

## Mac / Linux setup

### 1. Unzip the tool

Double-click the `skylar-qa-tool.zip` file you received. It will create a folder called `skylar-qa-tool` (or similar). Drag this folder somewhere convenient — for example your **Desktop** or **Documents** folder.

### 2. Open Terminal in that folder

- Open the **Terminal** app (Applications → Utilities → Terminal, or press `Cmd+Space` and type "Terminal")
- Type `cd ` (with a space) — DON'T press Enter yet
- Drag the `skylar-qa-tool` folder from Finder onto the Terminal window. The path appears automatically.
- Now press **Enter**

You should see your prompt change to show that folder. Confirm by typing:

```
ls
```

You should see files like `app`, `data`, `README.md`, `requirements.txt`, `run-server.sh`.

### 3. Install Python packages (one-time)

Copy and paste this into the Terminal, then press Enter:

```
python3 -m pip install -r requirements.txt
```

Wait ~30 seconds. You'll see lines like `Successfully installed playwright-1.49.0 flask-3.1.0 ...` when it finishes.

> **If you see permission errors:** prefix the command with `sudo` (you'll be asked for your Mac password):
> ```
> sudo python3 -m pip install -r requirements.txt
> ```

### 4. Download the headless browser (one-time)

Copy, paste, press Enter:

```
python3 -m playwright install chromium
```

Wait ~30 seconds for the ~150 MB download. You'll see a progress bar reach 100%.

### 5. Launch the tool

```
./run-server.sh
```

> **First time only:** If Mac says "permission denied", run this once:
> ```
> chmod +x run-server.sh
> ```
> Then try `./run-server.sh` again.

Your browser will open automatically to **http://127.0.0.1:5050/**. You're done with setup. ✅

---

## Windows setup

### 1. Unzip the tool

Right-click the `skylar-qa-tool.zip` you received → **Extract All…** → pick a folder (e.g. **Desktop**) → click **Extract**. You'll get a `skylar-qa-tool` folder.

### 2. Open Command Prompt in that folder

- Open the `skylar-qa-tool` folder in File Explorer
- Click the address bar at the top, type `cmd`, and press **Enter**
- A black Command Prompt window opens, already in the right folder

Confirm by typing:

```
dir
```

You should see files like `app`, `data`, `README.md`, `requirements.txt`.

### 3. Install Python packages (one-time)

Copy, paste, press Enter:

```
python -m pip install -r requirements.txt
```

Wait ~30 seconds.

### 4. Download the headless browser (one-time)

```
python -m playwright install chromium
```

Wait ~30 seconds.

### 5. Launch the tool

```
python -m app.server
```

Your browser will open automatically to **http://127.0.0.1:5050/**. You're done. ✅

---

## How to use the tool (after setup)

Open **http://127.0.0.1:5050/** in your browser if it isn't already open.

Fill in the form:

| Field | What to enter |
|---|---|
| **Login URL** | The full Skylar IQ login URL of the client you want to test |
| **Username / Password** | The Skylar IQ login for that client |
| **Machine ID** | Leave at `100` |
| **Questions Excel** | Click "Choose File" and pick your `.xlsx` file |

Click **Start QA Run**. Watch the live progress page. When the run finishes, click **Open final report ↗** to see the results.

📖 **For full instructions** — read `USER_GUIDE.md` (or open `Skylar_IQ_QA_Tool_User_Guide.docx` in Word).

---

## To re-launch the tool tomorrow

You only do steps 1–4 **once**. After that, every time you want to use the tool:

### On Mac/Linux:

1. Open Terminal
2. Drag the `skylar-qa-tool` folder onto Terminal after typing `cd ` (or `cd ~/Desktop/skylar-qa-tool` if it's on your Desktop)
3. Type `./run-server.sh` and press Enter

### On Windows:

1. Open the `skylar-qa-tool` folder in File Explorer
2. Click the address bar, type `cmd`, press Enter
3. Type `python -m app.server` and press Enter

The browser opens to the tool. Done.

---

## Troubleshooting

**"python3: command not found" (Mac/Linux) or "python is not recognized" (Windows)**

Python isn't installed, or isn't in your PATH. Re-install from [python.org/downloads](https://www.python.org/downloads/) and tick **"Add Python to PATH"** during install (Windows). On Mac, the python.org installer handles this automatically.

**"pip: command not found"**

Run `python3 -m ensurepip` (Mac/Linux) or `python -m ensurepip` (Windows).

**"Permission denied" when running `./run-server.sh`**

Once: `chmod +x run-server.sh`, then retry.

**"Address already in use" / "Port 5050 in use"**

Another program is using port 5050. Either close it, or run on a different port:
- Mac/Linux: `python3 -m app.server --port 5051`
- Windows: `python -m app.server --port 5051`

Then open **http://127.0.0.1:5051/** instead.

**The browser doesn't open automatically**

Manually open your browser and go to **http://127.0.0.1:5050/**.

**"ModuleNotFoundError: No module named 'playwright'"**

You skipped step 3. Re-run the `pip install` command.

**"playwright._impl._errors.Error: Executable doesn't exist"**

You skipped step 4. Re-run the `python3 -m playwright install chromium` command.

---

## Stopping the tool

In the terminal/command prompt where the tool is running, press **`Ctrl+C`** (works on all OSes). The server stops; the browser tab still works for viewing past reports.

---

## Updating the tool to a newer version

When you receive a new `skylar-qa-tool.zip`:

1. **Save your existing reports** — copy your `runs/` folder out of the old skylar-qa-tool folder to somewhere safe (e.g. your Desktop)
2. Delete the old `skylar-qa-tool` folder
3. Unzip the new `skylar-qa-tool.zip`
4. Drag your saved `runs/` folder back inside the new `skylar-qa-tool` folder (so past run history is preserved)
5. Re-run step 3 (`pip install -r requirements.txt`) to pick up any new dependencies
6. Launch as usual (step 5)

You don't need to re-run the Playwright browser install (step 4) — it's stored in your home folder, not the tool folder.

---

## Need help?

Contact the person who sent you this tool.
