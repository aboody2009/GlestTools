import struct, os, sys, time
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
        
class Mesh4:
    def __init__(self,g3d,f):
        self.g3d = g3d
        self.vertices = []
        self.normals = []
        self.indices = []
        self.txCoords = None
        self.bounds = [sys.maxint,sys.maxint,sys.maxint,-sys.maxint-1,-sys.maxint-1,-sys.maxint-1]
        self.name = f.text64()
        frameCount = f.uint32()
        vertexCount = f.uint32()
        indexCount = f.uint32()
        print "Mesh4",self.name,frameCount,vertexCount,indexCount
        f.read(8*4)
        self.properties = properties = f.uint32()
        self.textures = textures = f.uint32()
        self.texture = None
        if (textures & 1) == 1:
            self.texture = g3d.assign_texture(f.text64())
        for i in xrange(frameCount):
            vertices = []
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                vertices.append(pt)
                for i in xrange(3):
                    self.bounds[i] = min(self.bounds[i],pt[i])
                    self.bounds[i+3] = max(self.bounds[i+3],pt[i])
            self.vertices.append(vertices)
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
        for i in xrange(indexCount):
            self.indices.append(f.uint32())
    def draw(self,now):
        i = int((now*5)%len(self.vertices))
        print now,i
        vertices = self.vertices[i]
        normals = self.normals[i]
        textures = self.txCoords
        if textures is not None:
            glBindTexture(GL_TEXTURE_2D,self.texture)
        glBegin(GL_TRIANGLES)
        for i in self.indices:
            if textures is not None:
                glTexCoord(*textures[i])
            glNormal(*normals[i])
            glVertex(*vertices[i])
        glEnd()
    
class G3D:
    def __init__(self,txMgr,filename):
        self.filename = filename
        self.txMgr = txMgr
        self.meshes = []
        self.bounds = [sys.maxint,sys.maxint,sys.maxint,-sys.maxint-1,-sys.maxint-1,-sys.maxint-1]
        f = BinaryStream(filename)
        if f.read(3) != "G3D":
            raise Exception("%s is not a G3D file"%filename)
        self.ver = f.uint8()
        if self.ver == 4:
            meshCount = f.uint16()
            if f.uint8() != 0:
                raise Exception("%s is not mtMorphMesh!"%filename)
            for mesh in xrange(meshCount):
                mesh = Mesh4(self,f)
                self.meshes.append(mesh)
                for i in xrange(3):
                    self.bounds[i] = min(self.bounds[i],mesh.bounds[i])
                    self.bounds[i+3] = max(self.bounds[i+3],mesh.bounds[i+3])
        else:
            raise Exception("%s unsupported G3D version: %s"%(filename,self.ver))
        w = self.bounds[3]-self.bounds[0]
        h = self.bounds[4]-self.bounds[1]
        d = self.bounds[5]-self.bounds[2]
        x = -self.bounds[0] - (w/2.)
        y = -self.bounds[1] - (h/2.)
        z = -self.bounds[2] - (d/2.)
        s = 1.8/max(w,h,d)
        self.scaling = (x,y,z,s)
    def assign_texture(self,texture):
        texture = os.path.join(os.path.split(self.filename)[0],texture)
        return self.txMgr.assign_texture(texture)
    def draw(self,now):
        glPushMatrix()
        glScale(self.scaling[3],self.scaling[3],self.scaling[3])
        glTranslate(self.scaling[0],self.scaling[1],self.scaling[2])
        for mesh in self.meshes:
            mesh.draw(now)
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
    def init(self):
        GLZPR.init(self)
        glEnable(GL_TEXTURE_2D)
        self.txMgr.load_textures()
        import gobject
        gobject.timeout_add(100,lambda: self.queue_draw() or True)
    def add(self,filename):
        self.models.append(G3D(self.txMgr,filename))
    def draw(self,event):
        now = time.time() - self.start
        glClearColor(1.,1.,.9,1.)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        for model in self.models:
            model.draw(now)
        
if __name__ == "__main__":
    import pygtk; pygtk.require('2.0')
    import gtk, gtk.gdk as gdk, gtk.gtkgl as gtkgl, gtk.gdkgl as gdkgl
    from OpenGL.GL import *
    from OpenGL.GLU import *
    from OpenGL.GLUT import *
    glutInit(sys.argv)

    if len(sys.argv) != 2:
        sys.exit("Usage: python g3d_stats.py [model.g3d]")

    scene = Scene()
    scene.add(sys.argv[1])

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

