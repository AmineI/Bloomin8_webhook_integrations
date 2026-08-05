
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
python -m pip install -e .
cp .env.example .env   # then fill in your frame's MAC and IP
```

The Azure Functions and plain Python webhook hosts each have their own extra
requirements files: `azure-functions-requirements.txt` and `server-requirements.txt`.

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
| `--eink-optimization-preset` | `BLOOMIN8_PYTHON_EINK_PRESET` | `1` | `show` | E-ink optimization preset applied before upload: `off` or `1` (brighter, more saturated Bloomin8 JPEG-upload tuning). |
| `--only-if-idle` / `--no-only-if-idle` | `BLOOMIN8_ONLY_IF_IDLE` | off | `show` | Cancel instead of queueing when the frame is already busy. |
| `BLOOMIN8_DEBUG_REQUESTS` | `BLOOMIN8_DEBUG_REQUESTS` | `false` | env | When `true`, enables verbose HTTP client logs (`requests`). Otherwise they are forced to warning only. |
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
| `cover` *(default)* | <img src="display_mode_previews/cover-1765643572.jpg" width="140"> | <img src="display_mode_previews/cover-1785317506.jpg" width="140"> | Scales until the panel is covered, keeping aspect ratio; the frame crops the overflow. |
| `fit` | <img src="display_mode_previews/fit-1765643572.jpg" width="140"> | <img src="display_mode_previews/fit-1785317506.jpg" width="140"> | Scales and center-crops to exactly the panel size. |
| `pad` | <img src="display_mode_previews/pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/pad-1785317506.jpg" width="140"> | Scales until the whole image fits, leaving the remaining space blank (letterboxing). |
| `border-color-pad` | <img src="display_mode_previews/border-color-pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/border-color-pad-1785317506.jpg" width="140"> | `pad`, with the empty space filled using the image's average border colour. |
| `gradient-pad` | <img src="display_mode_previews/gradient-pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/gradient-pad-1785317506.jpg" width="140"> | `pad`, with the empty space filled by a gradient between the image's four dominant colours. |
| `gradient-popout` | <img src="display_mode_previews/gradient-popout-1765643572.jpg" width="140"> | <img src="display_mode_previews/gradient-popout-1785317506.jpg" width="140"> | `gradient-pad`, with the image floating on a margin, rounded corners and a soft drop shadow. |
| `vibrant-popout` | <img src="display_mode_previews/vibrant-popout-1765643572.jpg" width="140"> | <img src="display_mode_previews/vibrant-popout-1785317506.jpg" width="140"> | Floats the image over a backdrop built from the artwork's most vibrant colours. |
| `blur-pad` | <img src="display_mode_previews/blur-pad-1765643572.jpg" width="140"> | <img src="display_mode_previews/blur-pad-1785317506.jpg" width="140"> | `pad`, with the empty space filled by a blurred enlargement of the image itself. |
| `blur-popout` | <img src="display_mode_previews/blur-popout-1765643572.jpg" width="140"> | <img src="display_mode_previews/blur-popout-1785317506.jpg" width="140"> | Floats the image over a blurred, muted enlargement of itself. |

---

## Plex webhook function app

### Plain Python server

For hosts where the Azure Functions runtime is awkward, install the same requirements and
run the webhook as a regular ASGI server:

```bash
python -m pip install -r server-requirements.txt
uvicorn webhook_server:app --host 0.0.0.0 --port 7072
```

Or build the Starlette server image:

```bash
docker build -f Dockerfile.starlette -t bloomin8-webhook-starlette .
docker run --rm --env-file .env -p 7072:7072 bloomin8-webhook-starlette
```

The server exposes the same Azure-style routes documented below, plus short aliases:
`POST /webhook`, `POST /restore`, `POST /show-image` and `GET /healthz`.

### Run it

```bash
docker compose up --build
```

Compose builds the Azure Functions image from `Dockerfile.azure-functions`.

The container publishes port `57071`. Point the Plex webhook at
`http://<host>:57071/api/plex_webhook_trigger`.

### Endpoints

| Method & route | Purpose | Query parameters |
| --- | --- | --- |
| `POST /api/plex_webhook_trigger` | Plex webhook target: shows the poster on play, restores on stop. | — |
| `POST /api/http_show_image_trigger` | Displays an image sent as the raw body or as a multipart `image` field (max 16 MB). | `name`, `gallery`, `display_mode`, `overwrite_state` |
| `POST /api/http_restore_trigger` | Restores the saved state immediately, bypassing the stop debounce. | `overwrite_state` |

### Manual Webhooks

`restore_trigger` restores the frame state saved by the previous temporary display. Use
`POST /api/http_restore_trigger` on the Azure Functions host, or `POST /restore` on the
plain Python server. Add `?overwrite_state=true` to force the restore even when the
frame is currently showing an image this workflow did not put there.

```bash
curl -X POST "http://<host>:57071/api/http_restore_trigger"
curl -X POST "http://<host>:57071/api/http_restore_trigger?overwrite_state=true"
```

`show_image_trigger` displays an image supplied either as the raw request body or as a
multipart form field named `image`. Use `POST /api/http_show_image_trigger` on the Azure
Functions host, or `POST /show-image` on the plain Python server. Query parameters are:
`name`, `gallery`, `display_mode` and `overwrite_state`.

```bash
curl -X POST "http://<host>:57071/api/http_show_image_trigger?name=cover.jpg&gallery=media" \
  --data-binary "@cover.jpg" \
  -H "Content-Type: image/jpeg"

curl -X POST "http://<host>:57071/api/http_show_image_trigger?gallery=media&display_mode=cover" \
  -F "image=@cover.jpg"
```

`name` becomes a filename on the frame, so anything outside letters, digits, dots, dashes
and underscores is replaced with an underscore. It falls back to the upload filename, and
the request is rejected only when neither is supplied.

> The routes are anonymous. Keep the app on a trusted network, or put it behind a reverse
> proxy that handles authentication.

### Configuration

Frame settings (`BLOOMIN8_MAC`, `BLOOMIN8_IP`, `BLOOMIN8_MANAGED_GALLERIES`, …) are shared
with the CLI. Posters always go to the `media` gallery, so it must stay in the managed
gallery allowlist. The webhook adds:

| Variable | Default | Description |
| --- | --- | --- |
| `WEBHOOK_PLEX_SERVER_URL` | — | Base URL of the Plex server, used to download posters. |
| `WEBHOOK_PLEX_TOKEN` | — | Plex [authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/). |
| `WEBHOOK_PROCESS_OWNER_PLAYBACK_ONLY` | `true` | Ignore events where `Account.owner` is false. |
| `WEBHOOK_PROCESS_LOCAL_PLAYBACK_ONLY` | `true` | Ignore events where `Player.local` is false. |
| `WEBHOOK_SKIP_TRACKS` | `false` | Ignore track playback events. |
| `WEBHOOK_DEFAULT_OVERWRITE_STATE` | `false` | Let the webhook take over a frame showing an image it did not set. |
| `WEBHOOK_ACTION_ONLY_IF_IDLE` | `true` | Skip the poster instead of queueing behind an in-progress update. Overrides `BLOOMIN8_ONLY_IF_IDLE` for webhook-driven displays. |
| `WEBHOOK_SHOW_DEBOUNCE_SECONDS` | `5` | Wait before uploading, so skipping between items replaces the pending image instead of sending one slow upload per event. |
| `WEBHOOK_RESTORE_DEBOUNCE_SECONDS` | `25` | Wait after a stop event before restoring; a new play in that window cancels the restore. |
| `WEBHOOK_BLE_WAKE_DEBOUNCE_SECONDS` | `0` | Minimum time between pre-debounce BLE wake attempts; `0` wakes for every webhook action. The final show/restore action still performs its normal wake. |
| `TRACK_DISPLAY_MODE` | `vibrant-popout` | Display mode for music tracks, whose square album art does not fill the panel. Posters always use `cover`. |


## Playnite scripts
The scripts call the webhook server over HTTP. Pass your own server address with
`-BaseUrl "http://<host>:<port>"`. Use these in Playnite script events:

- Post-start script (show game cover):
	`& "REPO_PATH\Playnite\Playnite_ShowCover.ps1" -BaseUrl "http://<host>:<port>"`

- Post-game/exit script (restore backup):
	`& "REPO_PATH\Playnite\Playnite_Restore.ps1" -BaseUrl "http://<host>:<port>"`

### Parameters

| Parameter | Default | Scripts | Description |
| --- | --- | --- | --- |
| `-BaseUrl` | *required* | both | Root URL of the webhook server, e.g. `http://192.168.1.10:57071`. |
| `-Gallery` | `games` | `ShowCover` | Destination gallery on the frame. Must be a managed gallery. |
| `-DisplayMode` | server default | `ShowCover` | Display mode such as `cover` or `vibrant-popout`. See [Display modes](#display-modes). |
| `-OverwriteState` | off | both | back up and replace a user-set image even though a different backup is still waiting to be restored, losing that backup. On `restore`, put the backup back over a user-set image instead of refusing. |
| `-TimeoutSec` | `120` | both | HTTP timeout. The server debounces and uploads before replying, so keep it generous. |

The request runs on a background runspace, so neither game launch nor Playnite is blocked
while the frame updates. Both scripts log the endpoint they call and the HTTP status and
response body; Playnite writes those entries to `%appdata%\Playnite\playnite.log`.
