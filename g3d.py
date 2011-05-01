
import struct, os, sys, time, numpy, math, traceback, ctypes

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
        self.bounds = numpy.array(\
            [sys.maxint,sys.maxint,sys.maxint,-sys.maxint-1,-sys.maxint-1,-sys.maxint-1],
            dtype=numpy.float32)
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
    def diag(self):
        return math.sqrt(sum((self.bounds[i]-self.bounds[i+3])**2 for i in xrange(3)))
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

def repack(array):
    h,w = array.shape
    new = numpy.zeros(w*h,dtype=array.dtype)
    for i in xrange(w*h):
        new[i] = array[i//w,i%w]
    return new
        
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
        self.using_shaders = None
    def _load_vn(self,f,frameCount,vertexCount):
        self.vertices = []
        for i in xrange(frameCount):
            vertices = numpy.zeros((vertexCount,3),dtype=numpy.float32)
            bounds = Bounds()
            for v in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                vertices[v] = pt
                bounds.add_xyz(*pt)
            self.vertices.append(vertices)
            self.bounds.append(bounds)
        self.normals = []
        for i in xrange(frameCount):
            normals = numpy.zeros((vertexCount,3),dtype=numpy.float32)
            for n in xrange(vertexCount):
                pt = (f.float32(),f.float32(),f.float32())
                normals[n] = pt
            self.normals.append(normals)
        self.in_vertices = (frameCount*vertexCount)
    def _load_t(self,f,frameCount,vertexCount):
        self.txCoords = numpy.zeros((frameCount,vertexCount,2),dtype=numpy.float32)
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
    def interop(self,now):
        i = (now*self.g3d.mgr.render_speed)%len(self.vertices)
        p = int(i)
        n = (p+1)%len(self.vertices)
        f = i%1.
        def inter(a,b):
            ret = numpy.zeros((len(a),3),dtype=numpy.float32)
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
            i = int((now*self.g3d.mgr.render_speed)%len(self.txCoords))
            textures = self.txCoords[i]
        else:
            textures = None
        return (vertices,normals,textures)
    def draw_gl(self,now):
        if self.using_shaders is not None:
            try:
                self.draw_gl_vbos(now)
            except Exception as e:
                traceback.print_exc()
                self.draw_gl_ffp(now)
        else:
            self.draw_gl_ffp(now)
    def init_gl(self):
        if not self.g3d.mgr.use_shaders:
            return
        try:
            vbo = self.g3d.mgr.make_vbo
            verts = [vbo(v,GL.GL_ARRAY_BUFFER) for v in self.vertices]
            norms = [vbo(n,GL.GL_ARRAY_BUFFER) for n in self.normals]
            # indices is actually a list of trianGL.gles, so unpack it
            indices = repack(self.indices)
            self.num_indices = len(indices)
            assert self.num_indices == len(self.indices)*3 
            indices = vbo(indices,GL.GL_ELEMENT_ARRAY_BUFFER)
            txCoords = vbo(self.txCoords,GL.GL_ARRAY_BUFFER) if self.texture is not None else None
            self.using_shaders = (indices,verts,norms,txCoords)
        except Exception as e:
            traceback.print_exc()
    def draw_gl_shaders(self,now):
        indices,verts,norms,txCoords = self.using_shaders
        i = (now*self.g3d.mgr.render_speed)%len(verts)
        p = int(i)
        n = (p+1)%len(verts)
        f = i%1.
        if txCoords is None:
            GL.glBindTexture(GL.GL_TEXTURE_2D,0)
            GL.glColor(0,1,0,1)
        else:
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER,txCoords)
            GL.glTexCoordPointer(2,GL.GL_FLOAT,0,None)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D,self.texture)
            GL.glColor(1,1,1,1)
            if self.g3d.mgr.shaders:
                GL.glUniform1i(self.g3d.mgr.uniform_tex,0)
        GL.glUniform1f(self.g3d.mgr.uniform_lerp,f)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER,verts[p])
        GL.glVertexPointer(3,GL.GL_FLOAT,0,None)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER,norms[p])
        GL.glNormalPointer(GL.GL_FLOAT,0,None)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER,verts[n])
        GL.glColorPointer(3,GL.GL_FLOAT,0,None)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER,indices)
        GL.glDrawElements(GL.GL_TRIANGLES,self.num_indices,GL.GL_UNSIGNED_INT,None)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER,0)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER,0)
    def draw_gl_ffp(self,now):
        def draw():
            GL.glBegin(GL.GL_TRIANGLES)
            for j,i in enumerate(self.indices):
                for k in i:
                    if textures is not None:
                        GL.glTexCoord(*textures[k])
                    if normals is not None:
                        GL.glNormal(*normals[k])
                    GL.glVertex(*vertices[k])
            GL.glEnd()
        vertices, normals, textures = self.interop(now)
        if not self.g3d.mgr.render_normals: normals = None
        GL.glBindTexture(GL.GL_TEXTURE_2D,self.texture if textures is not None else 0)
        (GL.glDisable if self.twoSided else GL.glEnable)(GL.GL_CULL_FACE)
        if self.customColor:
            GL.glColor(1,0,0,1)
            GL.glTexEnvi(GL.GL_TEXTURE_ENV,GL.GL_TEXTURE_ENV_MODE,GL.GL_DECAL)
        else:
            GL.glColor(1,1,1,1)
            GL.glTexEnvi(GL.GL_TEXTURE_ENV,GL.GL_TEXTURE_ENV_MODE,GL.GL_BLEND)
        draw()
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glBindTexture(GL.GL_TEXTURE_2D,0)
        
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
        self.customColor = (properties & 4) == 4
        self.twoSided = (properties & 2) == 2
        texture = f.text64()
        if 0 == (properties & 1):
            self.texture = g3d.assign_texture(texture)
            bumpmap = texture[:-4]+"_normal"+texture[-4:]
            if os.path.isfile(bumpmap):
                print "***v3 normals bumpmap:",bumpmap,"***"
                self.bumpmap = g3d.assign_texture(bumpmap)
        self._load_vn(f,frameCount,vertexCount)
        if self.texture is not None:
            self._load_t(f,texCoordCount,vertexCount)
        if texCoordCount > 1:
            print "***v3: ",g3d.filename,texCoordCount,"texture frames! ***"
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
        self.customColor = (properties & 1) == 1
        self.twoSided = (properties & 2) == 2
        self.textures = textures = f.uint32()
        for t in xrange(5):
            if ((1 << t) & textures) != 0:
                texture = g3d.assign_texture(f.text64())
                if t == 0:
                    self.texture = texture
                elif t == 2:
                    print "*** v4 normals bumpmap:",texture,"***"
                    self.bumpmap = g3d.assign_texture(texture)                   
        self._load_vn(f,frameCount,vertexCount)
        if self.texture is not None:
            self._load_t(f,1,vertexCount)
        self._load_i(f,indexCount)
    
class G3D:
    def __init__(self,mgr,filename):
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
        #### this scaling really needs working out
        x,y,z = bounds.centre()
        s = 2./bounds.diag()
        self.scaling = (x,y,z,s)
        self.frame_count = len(self.meshes[0].vertices)
        for mesh in self.meshes[1:]:
            assert len(mesh.vertices) == self.frame_count
    def assign_texture(self,texture):
        while texture.startswith("\\") or texture.startswith("/"):
            texture = texture[1:]
        texture = os.path.join(os.path.split(self.filename)[0],texture)
        return self.mgr.assign_texture(texture)
    def init_gl(self):
        for mesh in self.meshes:
            mesh.init_gl()
    def draw_gl(self,now):
        GL.glBlendFunc(GL.GL_SRC_ALPHA,GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glPushMatrix()
        GL.glInitNames(1)
        try:
            GL.glScale(self.scaling[3],self.scaling[3],self.scaling[3])
            GL.glTranslate(self.scaling[0],self.scaling[1],self.scaling[2])
            for mesh in self.meshes:
                GL.glPushName(self.mgr.assign_mesh(mesh))
                mesh.draw_gl(now)
                GL.glPopName()
        finally:
            GL.glPopMatrix()
        
class Manager:
    def __init__(self,base_folder=os.getcwd(),use_shaders=False):
        self.base_folder = base_folder
        self.meshes = {}
        self.mesh_reverse = {}
        self.textures = {}
        self.models = {}
        self.opaque_textures = set()
        self._seq = 0
        self.use_shaders = use_shaders
    def load_model(self,filename):
        filename = os.path.relpath(filename,self.base_folder)
        if filename not in self.models:
            self.models[filename] = G3D(self,filename)
        return self.models[filename]
    def assign_texture(self,texture):
        if texture not in self.textures:
            v = self.assign_object()
            self.textures[texture] = v
            #print "Assigning texture",texture,"->",v
        return self.textures[texture]
    def make_vbo(self,array,target):
        obj = self.assign_object()
        GL.glBindBuffer(target,obj)
        GL.glBufferData(target,array,GL.GL_STATIC_DRAW)
        GL.glBindBuffer(target,0)
        return obj
    def assign_object(self):
        self._seq += 1
        return self._seq
    def assign_mesh(self,mesh):
        if mesh not in self.meshes:
            v = len(self.meshes)+1
            self.meshes[mesh] = v
            self.mesh_reverse[v] = mesh
        return self.meshes[mesh]
    def resolve_mesh(self,v):
        return self.mesh_reverse[v]
    def init_gl(self,render_speed = 10):
        self.render_speed = render_speed
        global GL
        GL = __import__('OpenGL',globals(),locals()).GL
        self.render_normals = True
        self._load_textures_gl()
        for model in self.models.values():
            model.init_gl()
        GL.glMaterialfv(GL.GL_FRONT,GL.GL_AMBIENT_AND_DIFFUSE,(1.,0.,0.,1.))
    def _load_textures_gl(self):
        import Image
        for filename,texture in self.textures.iteritems():
            try:
                image = Image.open(filename)
                w, h = image.size
                try:
                    img = image.tostring("raw","RGBA",0,-1)
                    mode = GL.GL_RGBA
                except Exception as e:
                    img = image.tostring("raw","RGB",0,-1)
                    mode = GL.GL_RGB
                    self.opaque_textures.add(texture)
                image = img
                GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT,1)
                GL.glBindTexture(GL.GL_TEXTURE_2D,texture)
                GL.glTexParameterf(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_WRAP_S,GL.GL_CLAMP)
                GL.glTexParameterf(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_WRAP_T,GL.GL_CLAMP)
                GL.glTexParameterf(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_MAG_FILTER,GL.GL_LINEAR)
                GL.glTexParameterf(GL.GL_TEXTURE_2D,GL.GL_TEXTURE_MIN_FILTER,GL.GL_LINEAR)
                GL.glTexImage2D(GL.GL_TEXTURE_2D,0,mode,w,h,0,mode,GL.GL_UNSIGNED_BYTE,image)
            except Exception,e:
                print "Could not load texture",filename,"->",texture
                print e
