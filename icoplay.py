#!/usr/bin/env python

import math, numpy, random
import pygtk; pygtk.require('2.0')
import gtk, gtk.gdk as gdk, gtk.gtkgl as gtkgl, gtk.gdkgl as gdkgl, gobject
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
from zpr import GLZPR

glutInit(())
    
def create(recursionLevel):
    def num_points(recursionLevel):
        return 5 * pow(2,2*recursionLevel+3) + 2 
    points = numpy.zeros((num_points(recursionLevel),3),dtype=numpy.float32)
    point_len = [0]
    midpoints = {}
    def add(point):
        slot = point_len[0]
        point_len[0] += 1
        dist = math.sqrt(sum(p**2 for p in point))
        points[slot] = [p/dist for p in point]
        return slot
    def midpoint(a,b):
        key = (min(a,b) << 32) + max(a,b)
        if key not in midpoints:
            a = points[a]
            b = points[b]
            mid = tuple((p1+p2)/2. for p1,p2 in zip(a,b))
            midpoints[key] = add(mid)
        return midpoints[key]
    t = (1.0 + math.sqrt(5.0)) / 2.0
    [add(p) for p in ( \
            (-1, t, 0),( 1, t, 0),(-1,-t, 0),( 1,-t, 0),
            ( 0,-1, t),( 0, 1, t),( 0,-1,-t),( 0, 1,-t),
            ( t, 0,-1),( t, 0, 1),(-t, 0,-1),(-t, 0, 1))]
    # create 20 triangles of the icosahedron
    faces = []
    # 5 faces around point 0
    [faces.append(t) for t in ((0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11))]
    # 5 adjacent faces 
    [faces.append(t) for t in ((1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8))]
    # 5 faces around point 3
    [faces.append(t) for t in ((3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9))]
    # 5 adjacent faces 
    [faces.append(t) for t in ((4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1))]
    # refine triangles
    for i in xrange(recursionLevel):
        faces2 = []
        for tri in faces:
            # replace triangle by 4 triangles
            a = midpoint(tri[0],tri[1])
            b = midpoint(tri[1],tri[2])
            c = midpoint(tri[2],tri[0])
            faces2.append((tri[0],a,c))
            faces2.append((tri[1],b,a))
            faces2.append((tri[2],c,b))
            faces2.append((a,b,c))
        faces = faces2
        print i, point_len[0], len(midpoints), len(faces), "%0.2f"%(float(len(faces))/float(point_len[0]))
    return faces, points
    
triangles, points = create(4)

def draw_ico(event):
    random.seed(1)
    rnd = random.random
    glClearColor(1,1,1,1)
    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
    for i,(a,b,c) in enumerate(triangles):
        glColor(rnd(),rnd(),rnd(),1)
        glBegin(GL_TRIANGLES)        
        glVertex(points[a])
        glVertex(points[b])
        glVertex(points[c])
        glEnd()

gtk.gdk.threads_init()
window = gtk.Window(gtk.WINDOW_TOPLEVEL)
window.set_title("Zoom Pan Rotate")
window.set_size_request(640,480)
window.connect("destroy",lambda event: gtk.main_quit())
vbox = gtk.VBox(False, 0)
window.add(vbox)
zpr = GLZPR()
zpr.draw = draw_ico
vbox.pack_start(zpr,True,True)
window.show_all()
gtk.main()
