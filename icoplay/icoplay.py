#!/usr/bin/env python

print "Creating terrain..."
from terrain import Terrain
terrain = Terrain()
terrain.create_ico(3)
print "ok"

import pygtk; pygtk.require('2.0')
import gtk, gtk.gdk as gdk, gtk.gtkgl as gtkgl, gtk.gdkgl as gdkgl, gobject
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from zpr import GLZPR
glutInit(())
gtk.gdk.threads_init()
window = gtk.Window(gtk.WINDOW_TOPLEVEL)
window.set_title("IcoPlay")
window.set_size_request(640,480)
window.connect("destroy",lambda event: gtk.main_quit())
vbox = gtk.VBox(False, 0)
window.add(vbox)
zpr = GLZPR()
zpr.draw = terrain.draw_gl_ffp
zpr._pick = lambda *args: ([],[])
zpr.pick = lambda *args: False
vbox.pack_start(zpr,True,True)
window.show_all()
gtk.main()
