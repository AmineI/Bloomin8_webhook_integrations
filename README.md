

### Set .env using example or pass ip & mac to the script

## Set image on the display, after backing up the current one
python -m pybloomin8 show --image "C:\gamecover.jpg" --gallery games --dither 0 
Optionally --overwrite-state to force the image change to overwrite the previous image backup

## Restore the image backed up as it was before using pybloomin8 show
python -m pybloomin8 restore

## Put the device to sleep immediately 
python -m pybloomin8 sleep