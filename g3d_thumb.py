#!/usr/bin/env python

if __name__ == "__main__":
    
    print "G3D Thumbnail Generator by William Edwards"
    
    import sys, getopt, os
    
    if (len(sys.argv) < 2):
        print """usage: python g3d_thumb.py {options} [file1.g3d] ... {fileN.g3d}
options:
    -w width
    -h height
    -b background-colour (rgb as 6 hexadecimal digits e.g. 00ff00 is green)
    -p pose (three rotations - x,y,z - separated by commas; default 0,130,0)
    -o output-path (default is current folder)"""
        sys.exit(1)
    
    from OpenGL.GLUT import *
    from OpenGL.GL import *
    import Image
    import g3d
    
    mgr = g3d.Manager()
    
    # default options
    w,h = 200,200 # size in pixels of window (and capture output)
    pose = (0,130,0) # angle on x,y,z respectively
    background = (1.,.9,.9,1.) # rgba 1=0xff
    out_path = "." # folder (and file prefix) where the frames should be saved to
    
    opts, args = getopt.getopt(sys.argv[1:],'w:h:p:b:o:')

    # parse opts and override defaults
    for opt,val in opts:
        if opt=="-w":
            w = int(val)
        elif opt=="-h":
            h = int(val)
        elif opt=="-p":
            pose = [int(v) for v in val.split(",")]
        elif opt=="-b":
            r,g,b = int(val[:2],16),int(val[2:4],16),int(val[4:],16)
            background = (float(r)/255,float(g)/255,float(b)/255,1.)
        elif opt=="-o":
            out_path = val
        else:
            print "unsupported option:",opt,val
            sys.exit(1)

    for filename in args:
        if os.path.isfile(filename):
            print "Loading",filename
            mgr.load_model(filename)
        else:
            for f in os.walk(filename):
                path = f[0] 
                for f in f[2]:
                    if os.path.splitext(f)[1] == ".g3d":
                        filename = os.path.join(path,f)
                        print "Loading",filename
                        mgr.load_model(filename)
        
    glutInit([])
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(w,h)
    glutCreateWindow("g3d_thumb")
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glDepthFunc(GL_LESS)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE)
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_ALPHA_TEST)
    glAlphaFunc(GL_GREATER,.4)
    glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)
    glFrontFace(GL_CCW)
    glEnable(GL_BLEND)
    glLightfv(GL_LIGHT0,GL_AMBIENT,(.3,.3,.3,1))
    glLightfv(GL_LIGHT0,GL_DIFFUSE,(1,1,1,1))
    glLightfv(GL_LIGHT0,GL_SPECULAR,(.1,.1,.1,1))
    glLightfv(GL_LIGHT0,GL_POSITION,(1.,1.,1.,0.))
    glColorMaterial(GL_FRONT_AND_BACK,GL_AMBIENT_AND_DIFFUSE)
    glEnable(GL_COLOR_MATERIAL)
    mgr.init_gl(1)
    
    glClearColor(*background)
    glMatrixMode(GL_MODELVIEW)
    glRotate(pose[0],1,0,0)
    glRotate(pose[1],0,1,0)
    glRotate(pose[2],0,0,1)
    
    for model in mgr.models.values():
        frames = []
        out_prefix = os.path.join(out_path,
            os.path.splitext(os.path.split(model.filename)[1])[0])
        for i in xrange(model.frame_count):
            glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
            model.draw_gl(i)
            pixels = glReadPixels(0,0,w,h,GL_RGB,GL_UNSIGNED_BYTE)
            png = "%s.%03d.png"%(out_prefix,len(frames))
            img = Image.frombuffer('RGB',(w,h),pixels,'raw','RGB',0,1)
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            img.save(png)
            frames.append(png)
            glutSwapBuffers()
        # convert to whatever
        cmd = "convert -delay 1x10 -size %sx%s -layers Optimize %s %s.gif"% \
            (w,h," ".join(frames),out_prefix)
        print cmd
        if 0 != os.system(cmd):
            print "### conversion failed for",model.filename
        # tidy up
        for frame in frames:
            os.unlink(frame)

