

### Set .env using example or pass ip & mac to the script

## Set image on the display, after backing up the current one
python -m pybloomin8 show --image "C:\gamecover.jpg" --gallery games --dither 0 
Optionally --overwrite-state to force the image change to overwrite the previous image backup

## Restore the image backed up as it was before using pybloomin8 show
python -m pybloomin8 restore
Optionally --overwrite-state to force restore even if the currently displayed image is outside managed galleries

## Put the device to sleep immediately 
python -m pybloomin8 sleep