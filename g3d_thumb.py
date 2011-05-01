#!/usr/bin/env python

import sys, Image
from OpenGL.GLUT import *
from OpenGL.GL import *
import g3d

default_w,default_h = 200,200 # size in pixels of window (and capture output)
default_pose = (-20,130,0) # angle on x,y,z respectively
default_background = (1.,.9,.9,1.) # rgba 1=0xff
default_out_path = "." # folder (and file prefix) where the frames should be saved to
_glut_init = False

def thumb(filename_in,filename_out,w=default_w,h=default_h,pose=default_pose,background=default_background,flush=None):
    if (flush is None) and _glut_init:
        flush = glutSwapBuffers
    mgr = g3d.Manager()
    print "Loading G3D",filename_in
    model = mgr.load_model(filename_in)
    mgr.init_gl(1)
    glClearColor(*background)
    glMatrixMode(GL_MODELVIEW)
    glRotate(pose[0],1,0,0)
    glRotate(pose[1],0,1,0)
    glRotate(pose[2],0,0,1)
    frames = []
    out_prefix,_ = os.path.splitext(filename_out)
    for i in xrange(model.frame_count):
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        model.draw_gl(i)
        pixels = glReadPixels(0,0,w,h,GL_RGB,GL_UNSIGNED_BYTE)
        png = "%s.%03d.png"%(out_prefix,len(frames))
        img = Image.frombuffer('RGB',(w,h),pixels,'raw','RGB',0,1)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img.save(png)
        frames.append(png)
        if flush is not None: flush()
    # convert to whatever
    cmd = "convert -delay 1x10 -size %sx%s -layers Optimize %s %s"% \
        (w,h," ".join(frames),filename_out)
    print cmd
    if 0 != os.system(cmd):
        print "### conversion failed for",model.filename
    # tidy up
    for frame in frames:
        os.unlink(frame)
        
def make_glut(w=default_w,h=default_w,caption="GlestTools"):
    glutInit([])
    glutInitDisplayMode(GLUT_DOUBLE|GLUT_RGB|GLUT_DEPTH)
    glutInitWindowSize(w,h)
    glutCreateWindow(caption)
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
    global _glut_init
    _glut_init = True

def main(argv):
    
    print "G3D Thumbnail Generator by William Edwards"
    
    import getopt, os
    
    if (len(argv) < 2):
        sys.exit("""usage: python g3d_thumb.py {options} [file1.g3d] ... {fileN.g3d}
options:
    -w width
    -h height
    -b background-colour (rgb as 6 hexadecimal digits e.g. 00ff00 is green)
    -p pose (three rotations - x,y,z - separated by commas; default 0,130,0)
    -o output-path (default is current folder)""")
    
    mgr = g3d.Manager()
    
    # default options
    w,h = default_w,default_h
    pose = default_pose
    background = default_background
    out_path = default_out_path
    
    opts, args = getopt.getopt(argv[1:],'w:h:p:b:o:')

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
            
    make_glut(w,h)
            
    def make_thumb(filename):
        thumb(filename,os.path.join(out_path,os.path.splitext(os.path.split(filename)[1])[0]+".gif"),
            w,h,pose,background)

    for filename in args:
        if os.path.isfile(filename):
            make_thumb(filename)
        else:
            for f in os.walk(filename):
                path = f[0] 
                for f in f[2]:
                    if os.path.splitext(f)[1] == ".g3d":
                        filename = os.path.join(path,f)
                        make_thumb(filename)

if __name__ == "__main__":
    main(sys.argv)

