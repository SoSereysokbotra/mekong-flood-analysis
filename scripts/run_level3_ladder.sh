#!/usr/bin/env bash
# Run every configs/level3/*.yaml that has no metrics_valid.json yet, one at a
# time. Waits while another level3_train.py is running so two trainings never
# share the 4 GB GPU. Safe to launch repeatedly (idempotent).
cd "$(dirname "$0")/.."
PY=.venv/Scripts/python
ORDER="unet_vvvh_ce unet_vv_ce unet_vvvh_cropw unet_vvvh_dice_ce unet_vvvh_focal unet_vvvh_slope unet_vvvh_noaug unet_r18_vvvh"

busy() {
  n=$(powershell -NoProfile -Command "(Get-CimInstance Win32_Process | Where-Object { \$_.Name -eq 'python.exe' -and \$_.CommandLine -like '*level3_train.py*' } | Measure-Object).Count")
  [ "${n//[^0-9]/}" != "0" ]
}

for c in $ORDER; do
  while busy; do sleep 60; done
  if [ -f "results/level3/$c/metrics_valid.json" ]; then echo "skip $c (done)"; continue; fi
  echo "start $c $(date +%H:%M)"
  $PY scripts/level3_train.py "configs/level3/$c.yaml" > "results/level3/_logs/$c.log" 2>&1
  echo "end   $c $(date +%H:%M)"
done
echo LADDER_DONE
