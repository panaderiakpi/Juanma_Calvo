#!/bin/bash
cd ~/storage/downloads/ruta/
rm -f -- test.log
python ~/storage/downloads/ruta/movistar_live.py >> test.log 2>&1   
var=$(< resultado.txt)  
termux-notification -c "$var" -t "Movistar_live Ok"
