# Torrent GameZip
Designed to be ran by a Torrent client after torrent finishes downloading

Requires 'requests' modules, install with "apt install python3-requests"

Must be configured inside the file, where:
API = Your RAWG API Key

categoryName = Your torrent's games category. Made so the script avoids unnecesary compressing of non-game torrents, like linux ISOs

storeFolder = the folder the script will store compressed and renamed versions of the folders in watchFolder

This script will automatically convert messy names to good names, for example, M.i.n_.e.c.raft gets converted to "Minecraft (2011)" and store them in a .zip file, guided by doCompression if you wanted it compressed or not.

You can choose to use compression (Zip Deflated) or disable (0% compression) by changing doCompression variable (Default: True)

If using Qbittorrent, look for "run external command on torrent finished" and set /usr/bin/python3 main.py %F --category %L --output /desired/output/location/

The parameters are:

-c --category = for the torrent's category

-o --output = Desired output location for compressed file

Made in python 3.11 with 25% of help from AI and my experience from java, this is my first Python script
