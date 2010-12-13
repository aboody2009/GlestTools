#!/usr/bin/env python

import struct, os, sys, time, numpy, math
from numpy import float_ as precision

def fmt_bytes(b):
    for m in ["B","KB","MB","GB"]:
        if b < 1024:
            return "%1.1f %s"%(b,m)
        b /= 1024.

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
        self.in_vertices = 0
        self.in_indices = 0
        self.out_vertices = 0
        self.out_indices = 0
        self.out_matrices = 0
    def _load_vn(self,f,frameCount,vertexCount):
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
        self.in_vertices = (frameCount*vertexCount)
    def _load_t(self,f,frameCount,vertexCount):
        self.txCoords = numpy.zeros((frameCount,vertexCount,2),dtype=precision)
        for i in xrange(frameCount):
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32())
                self.txCoords[i,v] = pt
    def _load_i(self,f,indexCount):
        assert indexCount % 3 == 0, "incomplete triangles (%s)"%indexCount
        self.indices = numpy.zeros((indexCount/3,3),dtype=numpy.uint32)
        for i in xrange(indexCount/3):
            self.indices[i] = (f.uint32(),f.uint32(),f.uint32())
        self.in_indices = indexCount
    def indentify_immutable(self,verbosity):
        #self.analysis = [None for v in self.vertices]
        #return
        if verbosity > 1: print self.__class__.__name__,len(self.vertices),len(self.vertices[0]),len(self.indices),
        # are all vertices used?
        self.out_vertices = len(self.vertices[0])
        used = numpy.zeros(self.out_vertices,dtype=numpy.bool_)
        for i in self.indices:
            used[i] = True # fun assignment from iterator
        if not all(used):
            u = []
            for i,j in enumerate(used):
                if not j:
                    u.append(str(i))
                    self.out_vertices -= 1
            print "Unused vertices:",",".join(u)
            print "*** this is most unusual; tell Will! ***"
        del used
        # group all vertices in each frame
        def dist(a,b):
            return math.sqrt(
                (a[0]-b[0])**2 +
                (a[1]-b[1])**2 +
                (a[2]-b[2])**2)
        def feq(a,b):
            return abs(a-b) < 0.000002
        self.analysis = [None]
        immutable = True
        count_mutable = 0
        # for each frame
        for f in xrange(1,len(self.vertices)):
            p, n = self.vertices[f-1], self.vertices[f]
            analysis = numpy.zeros(len(self.indices),dtype=numpy.bool_)
            mutable = False
            # for each triangle
            for i,v in enumerate(self.indices):
                if feq(dist(n[v[0]],n[v[1]]),dist(p[v[0]],p[v[1]])) and \
                    feq(dist(n[v[1]],n[v[2]]),dist(p[v[1]],p[v[2]])) and \
                    feq(dist(n[v[2]],n[v[0]]),dist(p[v[2]],p[v[0]])):
                    continue
                analysis[i] = True
                immutable = False
                mutable = True
            self.analysis.append(analysis if mutable else None)
            if verbosity > 2: print "x" if mutable else "y",
            if mutable:
                count_mutable += 1
        if verbosity > 1: print ("IMMUTABLE" if len(self.vertices)>1 else "immutable") if immutable else "mutable"
        if count_mutable > 0:
            self.out_vertices *= count_mutable
        self.out_matrices = len(self.vertices)-1-count_mutable
        self.out_indices = self.in_indices
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
        if self.txCoords is not None:
            i = int((now*5)%len(self.txCoords))
            textures = self.txCoords[i]
        else:
            textures = None
        return (vertices,normals,self.analysis[p],textures)
    def draw_gl(self,now,analyse):
        vertices, normals, analysis, textures = self.interop(now)
        if not analyse: analysis = None
        if (analysis is not None) or (textures is None):
            glBindTexture(GL_TEXTURE_2D,0)
            glColor(0,1,0,1)
            immutable = False
        else:
            glBindTexture(GL_TEXTURE_2D,self.texture)
            glColor(1,1,1,1)
        glBegin(GL_TRIANGLES)
        for j,i in enumerate(self.indices):
            for k in i:
                if analysis is not None:
                    if analysis[j] != immutable:
                        immutable = not immutable
                        glEnd()
                        glColor(1 if immutable else 0,0 if immutable else 1,0,1)
                        glBegin(GL_TRIANGLES)
                elif textures is not None:
                    glTexCoord(*textures[k])
                glNormal(*normals[k])
                glVertex(*vertices[k])
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
        self._load_vn(f,frameCount,vertexCount)
        if self.texture is not None:
            self._load_t(f,texCoordCount,vertexCount)
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
        for t in xrange(5):
            if ((1 << t) & textures) != 0:
                texture = g3d.assign_texture(f.text64())
                if t == 0:
                    self.texture = texture
        self._load_vn(f,frameCount,vertexCount)
        if self.texture is not None:
            self._load_t(f,1,vertexCount)
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
        print self.ver, 
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
    def analyse(self,verbosity):
        if verbosity > 0: print "Analysing G3D",self.filename
        for mesh in self.meshes:
            mesh.indentify_immutable(verbosity);
    def assign_texture(self,texture):
        texture = os.path.join(os.path.split(self.filename)[0],texture)
        return self.mgr.assign_texture(texture)
    def draw_gl(self,now):
        glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)
        glPushMatrix()
        glInitNames(1)
        try:
            glScale(self.scaling[3],self.scaling[3],self.scaling[3])
            glTranslate(self.scaling[0],self.scaling[1],self.scaling[2])
            for mesh in self.meshes:
                if (self.mgr.selection is not None) and (self.mgr.selection != mesh):
                    continue
                glPushName(self.mgr.assign_mesh(mesh))
                mesh.draw_gl(now,self.mgr.selection == mesh)
                glPopName()
        finally:
            glPopMatrix()
        
class Manager:
    def __init__(self,base_folder=os.getcwd()):
        self.base_folder = base_folder
        self.meshes = {}
        self.mesh_reverse = {}
        self.textures = {}
        self.models = {}
        self.selection = None
    def load_model(self,filename):
        filename = os.path.relpath(filename,self.base_folder)
        if filename not in self.models:
            self.models[filename] = G3D(self,filename)
    def analyse(self,verbosity=sys.maxint):
        for model in self.models.values():
            model.analyse(verbosity)
        print "=== Input ==="
        print len(self.models),"models"
        vertices = sum(sum(mesh.in_vertices for mesh in model.meshes) for model in self.models.values())
        print vertices,"vertices in","(%s)"%fmt_bytes(vertices*4*3*2)
        indices = sum(sum(mesh.in_indices for mesh in model.meshes) for model in self.models.values())
        print indices,"indices in","(%s)"%fmt_bytes(indices*4)
        vertices = sum(sum(mesh.out_vertices for mesh in model.meshes) for model in self.models.values())
        print vertices,"vertices out","(%s)"%fmt_bytes(vertices*4*3*2)
        indices = sum(sum(mesh.out_indices for mesh in model.meshes) for model in self.models.values())
        print indices,"indices out","(%s)"%fmt_bytes(indices*4)
        matrices = sum(sum(mesh.out_matrices for mesh in model.meshes) for model in self.models.values())
        print matrices,"matrices out","(%s)"%fmt_bytes(matrices*4*4*4)
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
                try:
                    image = image.tostring("raw","RGBA",0,-1)
                    mode = GL_RGBA
                except:
                    image = image.tostring("raw","RGB",0,-1)
                    mode = GL_RGB
                glPixelStorei(GL_UNPACK_ALIGNMENT,1)
                glBindTexture(GL_TEXTURE_2D,texture)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR)
                glTexParameterf(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR)
                glTexImage2D(GL_TEXTURE_2D,0,mode,w,h,0,mode,GL_UNSIGNED_BYTE,image)
            except Exception,e:
                print "Could not load texture",filename,"->",texture
                print e
        
if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: python g3d_stats.py [model.g3d] {model2.g3d} ... {modelN.g3d}")

    if (len(sys.argv) == 2) and os.path.isfile(sys.argv[1]):        
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
                    self.start = time.time()
                    self._animating = False
                def init(self):
                    GLZPR.init(self)
                    glEnable(GL_TEXTURE_2D)
                    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                    glFrontFace(GL_CCW)
                    glEnable(GL_NORMALIZE)
                    glEnable(GL_BLEND)
                    self.mgr.load_textures()
                    gobject.timeout_add(1,self._animate)
                def _animate(self):
                    if not self._animating:
                        self.queue_draw()
                        self._animating = True
                def draw(self,event):
                    if self._animating:
                        gobject.timeout_add(1,self._animate)
                        self._animating = False
                    now = time.time() - self.start
                    glClearColor(1.,1.,.9,1.)
                    glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
                    for model in self.mgr.models.values():
                        model.draw_gl(now)
                def pick(self,event,nearest,hits):
                    if len(nearest) != 1:
                        self.mgr.selection = None 
                        return
                    self.mgr.selection = self.mgr.resolve_mesh(nearest[0])
                        
            scene = Scene()
            scene.mgr.load_model(sys.argv[1])
            scene.mgr.analyse()
        
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
           
    mgr = Manager()
    models = {}
    for filename in sys.argv[1:]:
        filename = os.path.abspath(filename)
        if os.path.isfile(filename):
            mgr.load_model(filename)
        else:
            for f in os.walk(filename):
                path = f[0] 
                for f in f[2]:
                    if os.path.splitext(f)[1] == ".g3d":
                        filename = os.path.join(path,f)
                        mgr.load_model(filename)
    mgr.analyse()

