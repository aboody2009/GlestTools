#!/usr/bin/env python

import sys, os
from g3d_thumb import *

make_glut()

if len(sys.argv) < 2:
    sys.exit("usage: [path_to_techtree] {output_suffix}")
path = sys.argv[1]
path = os.path.realpath(path)
if path[-1] in ('\\','/'): path = path[:-1]
techtree = os.path.split(path)[1]

suffix = sys.argv[2]if len(sys.argv) > 2 else ""

page = open("%s%s.html"%(techtree,suffix),"w")
page.write("<html><head><title>%s</title></head><body>"%techtree)

for faction in os.listdir("%s/factions/"%path):
    if not os.path.exists("%s/factions/%s/units"%(path,faction)): continue
    page.write("<h1>%s</h1><table>"%faction)
    for unit in os.listdir("%s/factions/%s/units"%(path,faction)):
        model_dir = "%s/factions/%s/units/%s/models/"%(path,faction,unit)
        if not os.path.exists(model_dir): continue
        page.write("<tr><th>%s"%unit)
        for model in os.listdir(model_dir):
            filename_in = model_dir+model
            filename,ext = os.path.splitext(model)
            if ext.lower() != ".g3d": continue
            filename_out = ("%s%s_"%(faction,suffix))+os.path.split(model)[1]+".gif"
            if not os.path.exists(filename_out) or \
                (os.path.getmtime(filename_out) < os.path.getmtime(filename_in)):
                # avoid recreating thumbnails from previous runs unnecessarily
                thumb(filename_in,filename_out)
            page.write("<td><img src=\"%s\"/>"%filename_out)
    page.write("</table>")

page.write("</body></html>")
