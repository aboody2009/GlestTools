#!/usr/bin/env python

import sys, os
from g3d_thumb import *

make_glut()

path = sys.argv[1]
if path[-1] in ('\\','/'): path = path[:-1]
techtree = os.path.split(path)[1]

page = open("%s.html"%techtree,"w")
page.write("<html><head><title>%s</title></head><body>"%techtree)

for faction in os.listdir("%s/factions/"%path):
    page.write("<h1>%s</h1><table>"%faction)
    for unit in os.listdir("%s/factions/%s/units"%(path,faction)):
        model_dir = "%s/factions/%s/units/%s/models/"%(path,faction,unit)
        if not os.path.exists(model_dir): continue
        page.write("<tr><th>%s"%unit)
        for model in os.listdir(model_dir):
            filename_in = model_dir+model
            filename,ext = os.path.splitext(model)
            if ext.lower() != ".g3d": continue
            filename_out = ("%s_"%faction)+os.path.split(model)[1]+".gif"
            thumb(filename_in,filename_out)
            page.write("<td><img src=\"%s\"/>"%filename_out)
    page.write("</table>")

page.write("</body></html>")
