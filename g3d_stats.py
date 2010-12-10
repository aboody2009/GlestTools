import struct, os, sys, time, numpy, math
from zpr import GLZPR

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
        self.vertices = []
        self.normals = []
        self.indices = []
        self.txCoords = None
        self.texture = None
        self.bounds = []
    def _load_vnt(self,f,frameCount,vertexCount):
        for i in xrange(frameCount):
            vertices = []
            bounds = Bounds()
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                vertices.append(pt)
                bounds.add_xyz(*pt)
            self.vertices.append(vertices)
            self.bounds.append(bounds)
        for i in xrange(frameCount):
            normals = []
            for n in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                normals.append(pt)
            self.normals.append(normals)
        if self.texture is not None:
            self.txCoords = []
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32())
                self.txCoords.append(pt)
    def _load_i(self,f,indexCount):
        for i in xrange(indexCount):
            self.indices.append(f.uint32())
    def analyse(self):
        print self.__class__.__name__,len(self.vertices),len(self.vertices[0]),len(self.indices),
        # calculate internal distances
        def internal_distances(centre,v):
            ret = numpy.zeros((len(v),),dtype=numpy.double)
            for i,a in enumerate(v):
                r = (a[0]*centre[0]+a[1]*centre[1]+a[2]*centre[2])
                if r > 0:
                    r = math.sqrt(r)
                ret[i] = r
            return ret
        self.analysis = [None]
        immutable = True
        a = internal_distances(self.bounds[0].centre(),self.vertices[0])
        for i in xrange(1,len(self.vertices)):
            b = internal_distances(self.bounds[i].centre(),self.vertices[i])
            analysis = []
            mutable = False
            for j in xrange(len(a)):
                if abs(a[j]-b[j])>0.0001:
                    immutable = False
                    mutable = True
                    analysis.append(False)
                analysis.append(True)
            print "x" if mutable else "y",
            a = b
            self.analysis.append(analysis if mutable else None)
        print "IMMUTABLE" if immutable else "mutable"
    def interop(self,now):
        i = (now*5)%len(self.vertices)
        p = int(i)
        n = (p+1)%len(self.vertices)
        f = i%1.
        vertices = []
        for a,b in zip(self.vertices[p],self.vertices[n]):
            ax,ay,az = a
            bx,by,bz = b
            x = ax-(ax-bx)*f
            y = ay-(ay-by)*f
            z = az-(az-bz)*f
            vertices.append((x,y,z))
        normals = []
        for a,b in zip(self.normals[p],self.normals[n]):
            ax,ay,az = a
            bx,by,bz = b
            x = ax-(ax-bx)*f
            y = ay-(ay-by)*f
            z = az-(az-bz)*f
            normals.append((x,y,z))
        return (vertices,normals,self.analysis[p])
    def draw(self,now):
        vertices, normals, analysis = self.interop(now)
        textures = self.txCoords
        if (analysis is not None) or (textures is None):
            glBindTexture(GL_TEXTURE_2D,0)
            glColor(0,0,0,1)
        else:
            glBindTexture(GL_TEXTURE_2D,self.texture)
            glColor(1,1,1,1)
        glBegin(GL_TRIANGLES)
        for i in self.indices:
            if analysis is not None:
                glColor(1 if analysis[i] else 0,0,0,1)
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
    def __init__(self,txMgr,filename):
        self.filename = filename
        self.txMgr = txMgr
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
        for mesh in self.meshes:
            try:
                mesh.analyse();
            except Exception as e:
                import traceback
                traceback.print_exc()
                sys.exit(e)
    def assign_texture(self,texture):
        texture = os.path.join(os.path.split(self.filename)[0],texture)
        return self.txMgr.assign_texture(texture)
    def draw(self,now):
        glPushMatrix()
        try:
            glScale(self.scaling[3],self.scaling[3],self.scaling[3])
            glTranslate(self.scaling[0],self.scaling[1],self.scaling[2])
            for mesh in self.meshes:
                mesh.draw(now)
        except Exception as e:
            print e           
        glPopMatrix()
        
class TextureManager:
    def __init__(self):
        self.textures = {}
    def assign_texture(self,texture):
        if texture not in self.textures:
            v = len(self.textures)+1
            self.textures[texture] = v
            print "Assigning texture",texture,"->",v
        return self.textures[texture]
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
            except Exception as e:
                print "Could not load texture",filename,"->",texture
                print e

class Scene(GLZPR):
    def __init__(self):
        GLZPR.__init__(self)
        self.txMgr = TextureManager()
        self.models = []
        self.start = time.time()
        self._animating = False
    def init(self):
        GLZPR.init(self)
        glEnable(GL_TEXTURE_2D)
        self.txMgr.load_textures()
        gobject.timeout_add(1,self._animate)
    def analyse(self):
        for model in self.models:
            model.analyse()
    def _animate(self):
        if not self._animating:
            self.queue_draw()
            self._animating = True
    def add(self,filename):
        self.models.append(G3D(self.txMgr,filename))
    def draw(self,event):
        if self._animating:
            gobject.timeout_add(1,self._animate)
            self._animating = False
        now = time.time() - self.start
        glClearColor(1.,1.,.9,1.)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        for model in self.models:
            model.draw(now)
        
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python g3d_stats.py [model.g3d]")

    if len(sys.argv) == 2:
        
        import pygtk; pygtk.require('2.0')
        import gtk, gtk.gdk as gdk, gtk.gtkgl as gtkgl, gtk.gdkgl as gdkgl, gobject
        from OpenGL.GL import *
        from OpenGL.GLU import *
        from OpenGL.GLUT import *
        glutInit(())
    
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

