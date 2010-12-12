#!/usr/bin/env python

import struct, os, sys, time, numpy, math
from numpy import float_ as precision

class BinaryStream:
    def __init__(self,filename):
        self.filename = filename
        self.f = file(filename,"rb")
    def read(self,bytes):
        return self.f.read(bytes)
    def text64(self):
        t = self.read(64)
        t = t[:t.find('\0')]
        return t.strip()
    def unpack(self,fmt):
        return struct.unpack(fmt,self.read(struct.calcsize(fmt)))[0]
    def uint8(self):
        return ord(self.read(1))
    def uint16(self):
        return self.unpack("<H")
    def uint32(self):
        return self.unpack("<I")
    def float32(self):
        return self.unpack("f") 
        
class Bounds:
    def __init__(self):
        self.bounds = [sys.maxint,sys.maxint,sys.maxint,-sys.maxint-1,-sys.maxint-1,-sys.maxint-1]
    def add_xyz(self,x,y,z):
        self.bounds[0] = min(self.bounds[0],x)
        self.bounds[1] = min(self.bounds[1],y)
        self.bounds[2] = min(self.bounds[2],z)
        self.bounds[3] = max(self.bounds[3],x)
        self.bounds[4] = max(self.bounds[4],y)
        self.bounds[5] = max(self.bounds[5],z)
    def add_bounds(self,bounds):
        self.bounds[0] = min(self.bounds[0],bounds.bounds[0])
        self.bounds[1] = min(self.bounds[1],bounds.bounds[1])
        self.bounds[2] = min(self.bounds[2],bounds.bounds[2])
        self.bounds[3] = max(self.bounds[3],bounds.bounds[3])
        self.bounds[4] = max(self.bounds[4],bounds.bounds[4])
        self.bounds[5] = max(self.bounds[5],bounds.bounds[5])
    def size(self):
        w = self.bounds[3]-self.bounds[0]
        h = self.bounds[4]-self.bounds[1]
        d = self.bounds[5]-self.bounds[2]
        return (w,h,d)
    def centre(self):
        w,h,d = self.size()
        x = -self.bounds[0]-(w/2.)
        y = -self.bounds[1]-(h/2.)
        z = -self.bounds[2]-(d/2.)
        return (x,y,z)
        
class Mesh(object):
    def __init__(self,g3d):
        self.g3d = g3d
        self.txCoords = None
        self.texture = None
        self.bounds = []
    def _load_vnt(self,f,frameCount,vertexCount):
        self.vertices = []
        for i in xrange(frameCount):
            vertices = numpy.zeros((vertexCount,3),dtype=precision)
            bounds = Bounds()
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                vertices[v] = pt
                bounds.add_xyz(*pt)
            self.vertices.append(vertices)
            self.bounds.append(bounds)
        self.normals = []
        for i in xrange(frameCount):
            normals = numpy.zeros((vertexCount,3),dtype=precision)
            for n in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                normals[n] = pt
            self.normals.append(normals)
        if self.texture is not None:
            self.txCoords = numpy.zeros((vertexCount,2),dtype=precision)
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32())
                self.txCoords[v] = pt
    def _load_i(self,f,indexCount):
        self.indices = numpy.zeros(indexCount,dtype=numpy.uint32)
        for i in xrange(indexCount):
            self.indices[i] = f.uint32()
    def analyse(self):
        print self.__class__.__name__,len(self.vertices),len(self.vertices[0]),len(self.indices),
        # are all vertices used?
        used = numpy.zeros(len(self.vertices[0]),dtype=numpy.bool_)
        for i in self.indices:
            used[i] = True
        if not all(used):
            print "Unused vertices:",used
            print "*** this is most unusual; tell Will! ***"
        del used
        # group all vertices in each frame
        def dist(a,b):
            return math.sqrt(
                (a[0]-b[0])**2 +
                (a[1]-b[1])**2 +
                (a[2]-b[2])**2)
        def feq(a,b):
            if precision == numpy.double:
                return abs(a-b) < 0.00000001
            return abs(a-b) < 0.000001
        self.analysis = [None]
        i = self.indices
        immutable = True
        for f in xrange(1,len(self.vertices)):
            p, n = self.vertices[f-1], self.vertices[f]
            analysis = numpy.zeros(len(i),dtype=numpy.bool_)
            mutable = False
            # for each triangle
            for t in xrange(0,len(i),3):
                for v in xrange(3):
                    if feq(dist(n[i[t]],n[i[t+1]]),dist(p[i[t]],p[i[t+1]])) and \
                        feq(dist(n[i[t+1]],n[i[t+2]]),dist(p[i[t+1]],p[i[t+2]])) and \
                        feq(dist(n[i[t+2]],n[i[t]]),dist(p[i[t+2]],p[i[t]])):
                        continue
                    analysis[t:t+3] = (True,True,True)
                    immutable = False
                    mutable = True
            self.analysis.append(analysis if mutable else None)
            print "x" if mutable else "y",
        print "IMMUTABLE" if immutable else "mutable"
    def interop(self,now):
        i = (now*5)%len(self.vertices)
        p = int(i)
        n = (p+1)%len(self.vertices)
        f = i%1.
        def inter(a,b):
            ret = numpy.zeros((len(a),3),dtype=precision)
            for i in xrange(len(a)):
                ax,ay,az = a[i]
                bx,by,bz = b[i]
                ret[i,0] = ax-(ax-bx)*f
                ret[i,1] = ay-(ay-by)*f
                ret[i,2] = az-(az-bz)*f
            return ret
        vertices = inter(self.vertices[p],self.vertices[n])
        normals = inter(self.normals[p],self.normals[n])
        return (vertices,normals,self.analysis[p])
    def draw(self,now):
        vertices, normals, analysis = self.interop(now)
        textures = self.txCoords
        if (analysis is not None) or (textures is None):
            glBindTexture(GL_TEXTURE_2D,0)
            glColor(0,1,0,1)
            immutable = False
        else:
            glBindTexture(GL_TEXTURE_2D,self.texture)
            glColor(1,1,1,1)
        glBegin(GL_TRIANGLES)
        for j,i in enumerate(self.indices):
            if analysis is not None:
                if analysis[j] != immutable:
                    assert j % 3 == 0
                    immutable = not immutable
                    glEnd()
                    glColor(1 if immutable else 0,0 if immutable else 1,0,1)
                    glBegin(GL_TRIANGLES)
            elif textures is not None:
                glTexCoord(*textures[i])
            glNormal(*normals[i])
            glVertex(*vertices[i])
        glEnd()
        
class Mesh3(Mesh):
    def __init__(self,g3d,f):
        Mesh.__init__(self,g3d)
        frameCount = f.uint32()
        normalCount = f.uint32()
        texCoordCount = f.uint32()
        colorCount = f.uint32()
        vertexCount = f.uint32()
        indexCount = f.uint32()
        properties = f.uint32()
        texture = f.text64()
        if 0 == (properties & 1):
            self.texture = g3d.assign_texture(texture)
        self._load_vnt(f,frameCount,vertexCount)
        f.read(16)
        f.read(16*(colorCount-1))
        self._load_i(f,indexCount)   
        
class Mesh4(Mesh):
    def __init__(self,g3d,f):
        Mesh.__init__(self,g3d)
        self.name = f.text64()
        frameCount = f.uint32()
        vertexCount = f.uint32()
        indexCount = f.uint32()
        f.read(8*4)
        self.properties = properties = f.uint32()
        self.textures = textures = f.uint32()
        if (textures & 1) == 1:
            self.texture = g3d.assign_texture(f.text64())
        self._load_vnt(f,frameCount,vertexCount)
        self._load_i(f,indexCount)
    
class G3D:
    def __init__(self,mgr,filename):
        print "Loading G3D",filename
        self.filename = filename
        self.mgr = mgr
        self.meshes = []
        f = BinaryStream(filename)
        if f.read(3) != "G3D":
            raise Exception("%s is not a G3D file"%filename)
        self.ver = f.uint8()
        if self.ver == 3:
            meshCount = f.uint32()
            for mesh in xrange(meshCount):
                self.meshes.append(Mesh3(self,f))
        elif self.ver == 4:
            meshCount = f.uint16()
            if f.uint8() != 0:
                raise Exception("%s is not mtMorphMesh!"%filename)
            for mesh in xrange(meshCount):
                self.meshes.append(Mesh4(self,f))
        else:
            raise Exception("%s unsupported G3D version: %s"%(filename,self.ver))
        bounds = Bounds()
        for mesh in self.meshes:
            for frame in mesh.bounds:
                bounds.add_bounds(frame)
        x,y,z = bounds.centre()
        s = 1.8/max(*bounds.size())
        self.scaling = (x,y,z,s)
    def analyse(self):
        print "Analysing G3D",self.filename
        for mesh in self.meshes:
            mesh.analyse();
    def assign_texture(self,texture):
        texture = os.path.join(os.path.split(self.filename)[0],texture)
        return self.mgr.assign_texture(texture)
    def draw(self,now):
        glPushMatrix()
        glInitNames(1)
        try:
            glScale(self.scaling[3],self.scaling[3],self.scaling[3])
            glTranslate(self.scaling[0],self.scaling[1],self.scaling[2])
            for mesh in self.meshes:
                if (self.mgr.selection is not None) and (self.mgr.selection != mesh):
                    continue
                glPushName(self.mgr.assign_mesh(mesh))
                mesh.draw(now)
                glPopName()
        finally:
            glPopMatrix()
        
class Manager:
    def __init__(self):
        self.meshes = {}
        self.mesh_reverse = {}
        self.textures = {}
        self.selection = None
    def assign_texture(self,texture):
        if texture not in self.textures:
            v = len(self.textures)+1
            self.textures[texture] = v
            print "Assigning texture",texture,"->",v
        return self.textures[texture]
    def assign_mesh(self,mesh):
        if mesh not in self.meshes:
            v = len(self.meshes)+1
            self.meshes[mesh] = v
            self.mesh_reverse[v] = mesh
        return self.meshes[mesh]
    def resolve_mesh(self,v):
        return self.mesh_reverse[v]
    def load_textures(self):
        import Image
        for filename,texture in self.textures.iteritems():
            try:
                image = Image.open(filename)
                w, h = image.size
                image = image.tostring("raw","RGB",0,-1)
                glPixelStorei(GL_UNPACK_ALIGNMENT,1)
                glBindTexture(GL_TEXTURE_2D,texture)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR)
                glTexImage2D(GL_TEXTURE_2D,0,GL_RGB,w,h,0,GL_RGB,GL_UNSIGNED_BYTE,image)
            except Exception,e:
                print "Could not load texture",filename,"->",texture
                print e
        
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python g3d_stats.py [model.g3d] {model2.g3d} ... {modelN.g3d}")

    if len(sys.argv) == 2:        
        try:
            import pygtk; pygtk.require('2.0')
            import gtk, gtk.gdk as gdk, gtk.gtkgl as gtkgl, gtk.gdkgl as gdkgl, gobject
            from OpenGL.GL import *
            from OpenGL.GLU import *
            from OpenGL.GLUT import *
            from zpr import GLZPR
            glutInit(())
        
            class Scene(GLZPR):
                def __init__(self):
                    GLZPR.__init__(self)
                    self.mgr = Manager()
                    self.models = []
                    self.start = time.time()
                    self._animating = False
                def init(self):
                    GLZPR.init(self)
                    glEnable(GL_TEXTURE_2D)
                    self.mgr.load_textures()
                    gobject.timeout_add(1,self._animate)
                def analyse(self):
                    for model in self.models:
                        model.analyse()
                def _animate(self):
                    if not self._animating:
                        self.queue_draw()
                        self._animating = True
                def add(self,filename):
                    self.models.append(G3D(self.mgr,filename))
                def draw(self,event):
                    if self._animating:
                        gobject.timeout_add(1,self._animate)
                        self._animating = False
                    now = time.time() - self.start
                    glClearColor(1.,1.,.9,1.)
                    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
                    for model in self.models:
                        model.draw(now)
                def pick(self,event,nearest,hits):
                    if len(nearest) != 1:
                        self.mgr.selection = None 
                        return
                    self.mgr.selection = self.mgr.resolve_mesh(nearest[0])
                        
            scene = Scene()
            scene.add(sys.argv[1])
            scene.analyse()
        
            gtk.gdk.threads_init()
            window = gtk.Window(gtk.WINDOW_TOPLEVEL)
            window.set_title("G3D Stats")
            window.set_size_request(640,480)
            window.connect("destroy",lambda event: gtk.main_quit())
            vbox = gtk.VBox(False, 0)
            window.add(vbox)
            vbox.pack_start(scene,True,True)
            window.show_all()
            gtk.main()
            sys.exit(0)
        except Exception,e:
            import traceback; traceback.print_exc()
            print "Could not display 3D using OpenGL and GTK with ZPR"
           
    print sys.argv
    mgr = Manager()
    models = []
    for filename in sys.argv[1:]:
        models.append(G3D(mgr,filename))
    for model in models:
        model.analyse()
