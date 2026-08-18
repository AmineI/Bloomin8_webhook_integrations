
# Bloomin8 integrations

Control a Bloomin8 e-ink frame from the CLI, Plex playback events, Playnite events, and more through the HTTP webhook.

The repository contains multiple tools:

- **`pybloomin8`** — a Python package and CLI that wakes the frame over BLE, uploads an
  image over the LAN, and can restore whatever was displayed before. This is the basis of other integrations in the repo.
- **A Plex-compatible webhook server** — A webhook server runnable locally (& with Docker Compose)
  Can be triggered on demand to show/restore an image and restore the previous state afterwards.
  Can also be triggered by a plex webhook call to show the poster of what is playing and optionally restore the previous image when playback stops. Uses the pybloomin8 package provided.
- **A Playnite start/stop script** - A Playnite script to display the game poster when starting a game,
  and restore the previous poster afterwards. Calls the webhook server to do this.

## Contents

- [Requirements](#requirements)
- [Docker webhook quick start](#quick-start-docker-webhook)
- [Local setup](#local-setup)
- [Webhook server](#webhook-server)
- [Plex integration](#use-with-plex)
- [Configuration](#configuration)
- [Display modes](#display-modes)
- [Playnite script](#playnite-script)
- [CLI Examples](#cli-usage-examples)

---

### Requirements

- A Bloomin8 frame in bluetooth range of the host, with a reachable IP address.
- A host machine with a Bluetooth Low Energy (BLE) compatible adapter configured. The adapter can be
  built-in or connected over USB, but Bluetooth must be enabled and available to the
  operating system. For linux, you may need a variant of `apt install -y bluetooth`
- Docker; or Python >=3.10 for non-Docker use.

### Quick Start (Docker webhook)

1. Clone the project.
2. Create and fill your .env file, based on [.env.example](.env.example) :
   - Frame MAC and IP address shown in the Bloomin8 app.
   - For Plex, provide the Server URL and [Plex authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
   - See the [webhook configuration](#configuration) for all available settings options.
4. Start the webhook:
```bash
docker compose up --build
```

You can then 
- [Integrate with Plex](#use-with-plex)
- [Integrate with Playnite](#playnite-script)
- Trigger changes manually or within scripts with the [HTTP endpoints](#endpoints).

---
### Local setup
Without docker, you need to :

1. Fill your `.env` file based on the values in `.env.example` and [configuration docs](#configuration).
2. Install the pybloomin8 package:

```bash
python -m pip install -r server-requirements.txt # or requirements.txt if you only need CLI
python -m pip install -e .
```

Every command reads its defaults from env variables & `.env`, so most of the
time you only need to pass the image.

You can then use the CLI. See [examples](#cli-usage-examples), [options](#configuration), 
or self documentation by calling `python -m pybloomin8`
You can also start the [webhook server](#webhook-server)

---

## Webhook server


**Run with Docker**

```bash
docker compose up --build
```
The webhook container listens on port `7072` by default. 

**Or locally**

```bash
python -m pip install -r server-requirements.txt
uvicorn webhook_server:app --host 0.0.0.0 --port 7072
```

Check that it runs correctly at `http://localhost:7072/health`.


The webhook can be used on its own for HTTP image display and restore operations, or
connected to Plex to mirror playback posters.

### Use with Plex

Plex integration is optional. A Plex-compatible webhook endpoint is provided.
It listens for `media.play` events for configured media types (shows and movies by default),
downloads the poster, and restores the previous image after `media.stop` (configurable).

In Plex, open **Settings > Webhooks**, choose **Add Webhook**,
and enter the URL:
```text
http://localhost:7072/api/plex_webhook_trigger
```

Use `localhost` when Plex runs on the same machine. Otherwise use the webhook host's
LAN IP or a reachable HTTPS authenticated reverse proxy.

### Endpoints

The plain server provides `/http_show_image_trigger`, `http_restore_trigger` and `/health`  the deployment routes
are listed below. The routes are anonymous, so keep the server on a trusted network or
behind an authenticated reverse proxy.

For parameter values, see the [Webhook configuration](#configuration) tables below 
| Method & route | Purpose | Query parameters |
| --- | --- | --- |
| `POST /api/http_show_image_trigger` | Display a raw or multipart image. | `name`, `gallery`, `display_mode`, `overwrite_state`|
| `POST /api/http_restore_trigger` | Restore the saved state immediately. | `overwrite_state` |
| `POST /api/plex_webhook_trigger` | Plex poster webhook. | — |

Examples:

```bash
curl -X POST "http://<host>:7072/api/http_restore_trigger"
```
```
curl -X POST "http://<host>:7072/api/http_show_image_trigger?name=cover.jpg&gallery=media" \
  --data-binary "@cover.jpg" -H "Content-Type: image/jpeg"
```


### Configuration

Every option falls back to its environment variable, so a flag is only needed to override
`.env` for a single run.

| CLI Option | Environment variable | Required/Default | Commands | Description |
| --- | --- | --- | --- | --- |
| `--image` | — | **required** | `show` | Path to the image file to display. |
| `--ip` | `BLOOMIN8_IP` | **required** | all | LAN address of the frame. |
| `--mac` | `BLOOMIN8_MAC` | **required** | `show`, `restore`, `delete-gallery` | BLE MAC address, used to wake the frame. |
| `--gallery` | `BLOOMIN8_GALLERY` | `temp` (first managed gallery) | `show`, `delete-gallery` | Destination gallery on the frame. Must be one of the managed galleries. |
| `--managed-galleries` | `BLOOMIN8_MANAGED_GALLERIES` | `temp,games,media,music` | `show`, `restore`, `delete-gallery` | Comma-separated allowlist of the galleries this tool owns. Anything displayed from outside it counts as a user-set image. |
| `--display-mode` | `BLOOMIN8_DISPLAY_MODE` | `cover` | `show` | How the image is resized to the panel. See [Display modes](#display-modes). |
| `--only-if-idle` / `--no-only-if-idle` | `BLOOMIN8_ONLY_IF_IDLE` | off | `show` | Cancel instead of queueing when the frame is already busy. |
| `--dither` | — | frame default | `show` | `0` for Floyd–Steinberg (often better), `1` for JJN (often faster). |
| `--overwrite-state` | — | off | `show`, `restore` | On `show`, back up and replace a user-set image even though a different backup is still waiting to be restored, losing that backup. On `restore`, put the backup back over a user-set image instead of refusing. |
| `--eink-optimization-preset` | `BLOOMIN8_PYTHON_EINK_PRESET` | `off` | `show` | EXPERIMENTAL e-ink optimization preset applied before upload: `off` or `1` (brighter, more saturated Bloomin8 JPEG-upload tuning). It produces bad results right now but contributions are welcome. |
| — | `BLOOMIN8_PYTHON_DEBUG_REQUESTS` | `false` | env | When `true`, enables verbose HTTP client logs (`requests`). Otherwise they are forced to warning only. |

#### Managed galleries & overwrite state
> **Managed galleries** are the galleries this tool uploads to. Whatever the frame shows
> from anywhere else is a **user-set image**, a picture you chose by hand.
>
> `show` triggers a backup of the previous image if it was *user-set*, before replacing it, unless a different backup is already
> waiting to be restored. It would discard the previous backup, so `show` errors instead. 
> `restore` also never replaces a user-set image with a backup.
> `--overwrite-state` overrides both error scenario and lets you discard a user-set image that was displayed or backed up.
> The new image's `--gallery` must still name a managed gallery.

---

### Webhook specific configuration

Frame settings above (`BLOOMIN8_MAC`, `BLOOMIN8_IP`, `BLOOMIN8_MANAGED_GALLERIES`, …) are shared
with the CLI and needed for the Webhook as well. 
Posters always go to the `media` & `music` gallery (if tracks are enabled),
so they must stay in the managed gallery allowlist.

The webhook adds:

| Variable | Default | Description |
| --- | --- | --- |
| `WEBHOOK_PLEX_SERVER_URL` | — | Base URL of the Plex server, used to download posters. |
| `WEBHOOK_PLEX_TOKEN` | — | Plex [authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/). |
| `WEBHOOK_PLEX_PROCESS_OWNER_PLAYBACK_ONLY` | `true` | Ignore events where the user playing is not the server owner. |
| `WEBHOOK_PLEX_PROCESS_LOCAL_PLAYBACK_ONLY` | `true` | Ignore events where the device playing is not in the local plex server network. |
| `WEBHOOK_PLEX_PROCESS_MEDIA_TYPES` | `movie,episode` | Comma-separated Plex media types to process, such as `movie`, `episode`, and `track`. |
| `WEBHOOK_PLEX_PROCESS_MEDIA_STOP` | `true` | Restore the previous image after a `media.stop` event. When false, stop events are ignored, and play events always replace the current image, even if it was manually set through the Bloomin8 app for example. |
| `WEBHOOK_DEFAULT_OVERWRITE_STATE` | `false` | Let the webhook take over a frame showing an image set manually that is not the backed up image. This would replace the backup image and state saved for the "restore" action. |
| `WEBHOOK_ACTION_ONLY_IF_IDLE` | `true` | Skip the poster instead of queueing behind an in-progress update. Overrides `BLOOMIN8_ONLY_IF_IDLE` for webhook-driven displays. |
| `WEBHOOK_SHOW_DEBOUNCE_SECONDS` | `5` | Wait after a play event before showing an image.Skipping quickly between media will replaces a pending image that was in queued in the last `WEBHOOK_SHOW_DEBOUNCE_SECONDS`. |
| `WEBHOOK_RESTORE_DEBOUNCE_SECONDS` | `25` | Wait after a stop event before restoring the previous image. A new play in that window cancels the restore. |
| `WEBHOOK_TRACK_DISPLAY_MODE` | `vibrant-popout` | Display mode override for music tracks, whose square album art does not fill the panel. Other media uses `BLOOMIN8_DISPLAY_MODE`. |

### Display modes

Both previews below use square album art on the portrait panel, which is the case where
the modes differ the most.

| Mode | Sample 1 | Sample 2 | Description |
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

## Playnite script
`playnite_scripts\Playnite_Bloomin8.ps1` calls the webhook server over HTTP. Pass your own server
address with `-BaseUrl "http://<host>:<port>"` and choose -ShowCover or -Restore.

- Post-start script (show game cover):
  `& "REPO_PATH\playnite_scripts\Playnite_Bloomin8.ps1" -ShowCover -BaseUrl "http://<host>:<port>"`

- Post-game/exit script (restore cover displayed before the game):
  `& "REPO_PATH\playnite_scripts\Playnite_Bloomin8.ps1" -Restore -BaseUrl "http://<host>:<port>"`

Add them in Playnite, in Main menu > Settings… > Scripts. Add the `-ShowCover` command under
**Before game starts**, and add the `-Restore` command under **After game ends**.
Additional details available on Playnite's [Game Scripts documentation](https://api.playnite.link/docs/manual/features/scriptingSupport/scriptingSupportOverview.html#configuring-scripts).


### Parameters

| Parameter | Default | Actions | Description |
| --- | --- | --- | --- |
| `-ShowCover` | *required* | `ShowCover` | Display the current game's cover. Mutually exclusive with `-Restore`. |
| `-Restore` | *required* | `Restore` | Restore the previous display. Mutually exclusive with `-ShowCover`. |
| `-BaseUrl` | *required* | both | Root URL of the webhook server, e.g. `http://192.168.1.10:7072`. |
| `-Gallery` | `games` | `ShowCover` | Destination gallery on the frame. Must be a managed gallery. |
| `-DisplayMode` | server default | `ShowCover` | Display mode such as `cover` or `vibrant-popout`. See [Display modes](#display-modes). |
| `-OverwriteState` | off | both | back up and replace a user-set image even though a different backup is still waiting to be restored, losing that backup. On `restore`, put the backup back over a user-set image instead of refusing. |
| `-HTTPTimeoutSec` | `120` | both | HTTP timeout. The server debounces, wakes the device, and uploads before replying, so keep it generous. |

The request runs on a background runspace, so neither game launch nor Playnite is blocked
while the frame updates. The script logs the endpoint it calls and the HTTP status and
response body; Playnite writes those entries to `%appdata%\Playnite\playnite.log`.


## CLI usage examples

```bash
# Show an image, saving the current display first
python -m pybloomin8 show --image ".\gamecover.jpg" --gallery games

# Same, but lets the current display replace the backup kept if the current image has been changed by the user since the last backup. 
python -m pybloomin8 show --image ".\gamecover.jpg" --gallery games --overwrite-state

# Restores the image that was displayed before the last `show` command
python -m pybloomin8 restore --managed-galleries "media,games"

# Send the frame to sleep now
python -m pybloomin8 sleep

# Delete a gallery and every image in it
python -m pybloomin8 delete-gallery --gallery temp
```