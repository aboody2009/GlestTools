#!/usr/bin/env python

if __name__ == "__main__":
    
    import sys, getopt
	from OpenGL.GLUT import *
	import g3d
	
	mgr = g3d.Manager()

    glutInit([])
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(200,200)
    glutCreateWindow("g3d_thumb")
    
    opts, args = getopts(sys.argv,'')

    for arg in args:
        mgr.load_model(arg)
        
    mgr.init_gl(1)
    
    for model in mgr.models.values():
        for i in xrange(model.frame_count):
            glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
            model.draw_gl(i)
            


