
# Bloomin8 integration

Control a Bloomin8 e-ink frame from the command line, and mirror Plex playback onto it
automatically.

The repository contains two things:

- **`pybloomin8`** — a Python package and CLI that wakes the frame over BLE, uploads an
  image over the LAN, and can restore whatever was displayed before.
- **A Plex webhook function app** — an Azure Functions app (runnable with Docker Compose)
  that shows the poster of what is playing and restores the previous image when playback
  stops.

---

## Getting started

```bash
pip install -e .
cp .env.example .env   # then fill in your frame's MAC and IP
```

Every command reads its defaults from `.env` (or the process environment), so most of the
time you only need to pass the image.

---

## CLI

```bash
# Show an image, saving the current display first
python -m pybloomin8 show --image "C:\gamecover.jpg" --gallery games

# Same, but let the current display replace the backup kept if the current image has been changed by the user since the last backup. 
python -m pybloomin8 show --image "C:\gamecover.jpg" --gallery games --overwrite-state

# Put back the image that was displayed before the last `show`
python -m pybloomin8 restore --managed-galleries "media,games"

# Send the frame to sleep now
python -m pybloomin8 sleep

# Delete a gallery and every image in it
python -m pybloomin8 delete-gallery --gallery temp
```

### Options

Every option falls back to its environment variable, so a flag is only needed to override
`.env` for a single run.

| Option | Environment variable | Default | Commands | Description |
| --- | --- | --- | --- | --- |
| `--image` | — | *required* | `show` | Path to the image file to display. |
| `--ip` | `BLOOMIN8_IP` | *required* | all | LAN address of the frame. |
| `--mac` | `BLOOMIN8_MAC` | *required* | `show`, `restore`, `delete-gallery` | BLE MAC address, used to wake the frame. |
| `--gallery` | `BLOOMIN8_GALLERY` | `temp` (first managed gallery) | `show`, `delete-gallery` | Destination gallery on the frame. Must be one of the managed galleries. |
| `--managed-galleries` | `BLOOMIN8_MANAGED_GALLERIES` | `temp,show,games,media` | `show`, `restore`, `delete-gallery` | Comma-separated allowlist of the galleries this tool owns. Anything displayed from outside it counts as a user-set image. |
| `--display-mode` | `BLOOMIN8_DISPLAY_MODE` | `cover` | `show` | How the image is resized to the panel. See [Display modes](#display-modes). |
| `--only-if-idle` / `--no-only-if-idle` | `BLOOMIN8_ONLY_IF_IDLE` | off | `show` | Cancel instead of queueing when the frame is already busy. |
| `--dither` | — | frame default | `show` | `0` for Floyd–Steinberg (often better), `1` for JJN (often faster). |
| `--overwrite-state` | — | off | `show`, `restore` | On `show`, back up and replace a user-set image even though a different backup is still waiting to be restored, losing that backup. On `restore`, put the backup back over a user-set image instead of refusing. |

> **Managed galleries** are the galleries this tool uploads to. Whatever the frame shows
> from anywhere else is a **user-set image**, a picture you chose by hand.
>
> `show` backs a user-set image up and replaces it, unless a different backup is already
> waiting to be restored — saving would discard it, so `show` stops instead. `restore`
> never replaces a user-set image with a backup. `--overwrite-state` overrides both
> refusals. It does not widen the allowlist. `--gallery` must still name a managed
> gallery.

---

## Display modes

Both previews below use square album art on the portrait panel, which is the case where
the modes differ the most.

| Mode | Dark artwork | Bright artwork | Description |
| --- | --- | --- | --- |
| `cover` *(default)* | <img src="display_mode_previews/cover-1765643572.jpg" width="140"> | <img src="display_mode_previews/cover-1785317506.jpg" width="140"> | Scales until the panel is covered, keeping the aspect ratio; the frame crops the overflow. |
| `fit` | <img src="display_mode_previews/fit-1765643572.jpg" width="140"> | <img src="display_mode_previews/fit-1785317506.jpg" width="140"> | Scales and center-crops to exactly the panel size. |
| `pad` | <img src="display_mode_previews/pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/pad-1785317506.jpg" width="140"> | Scales until the whole image fits, leaving the remaining space blank (letterboxing). |
| `border-color-pad` | <img src="display_mode_previews/border-color-pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/border-color-pad-1785317506.jpg" width="140"> | `pad`, with the empty space filled using the image's average border colour. |
| `gradient-pad` | <img src="display_mode_previews/gradient-pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/gradient-pad-1785317506.jpg" width="140"> | `pad`, with the empty space filled by a gradient between the image's four dominant colours. |
| `gradient-popout` | <img src="display_mode_previews/gradient-popout-1765643572.jpg" width="140"> | <img src="display_mode_previews/gradient-popout-1785317506.jpg" width="140"> | `gradient-pad`, with the image floating on a margin, rounded corners and a soft drop shadow. |
| `vibrant-popout` | <img src="display_mode_previews/vibrant-popout-1765643572.jpg" width="140"> | <img src="display_mode_previews/vibrant-popout-1785317506.jpg" width="140"> | Floats the image over a backdrop built from the artwork's most vibrant colours. |
| `blur-pad` | <img src="display_mode_previews/blur-pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/blur-pad-1785317506.jpg" width="140"> | `pad`, with the empty space filled by a blurred enlargement of the image itself. |
| `blur-popout` | <img src="display_mode_previews/blur-popout-1765643572.jpg" width="140"> | <img src="display_mode_previews/blur-popout-1785317506.jpg" width="140"> | Floats the image over a blurred, muted enlargement of itself. |
