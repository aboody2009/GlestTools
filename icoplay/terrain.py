
import numpy, math, random, sys
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

def _vec_cross(a,b):
    return ( \
        (a[1]*b[2]-a[2]*b[1]),
        (a[2]*b[0]-a[0]*b[2]),
        (a[0]*b[1]-a[1]*b[0]))
def _vec_ofs(v,ofs):
    return (v[0]-ofs[0],v[1]-ofs[1],v[2]-ofs[2])
def _vec_normalise(v):
    l = math.sqrt(sum(d**2 for d in v))
    if l > 0:
        return (v[0]/l,v[1]/l,v[2]/l)
    return v
    
def _ray_triangle(R,T):
    # http://softsurfer.com/Archive/algorithm_0105/algorithm_0105.htm#intersect_RayTriangle%28%29
    # get triangle edge vectors and plane normal
    u = T[1]-T[0]
    v = T[2]-T[0]
    n = numpy.cross(u,v) ### cross product
    if n[0]==0 and n[1]==0 and n[2]==0:            # triangle is degenerate
        raise Exception("%s %s %s %s %s"%(R,T,u,v,n))
        return (-1,None)                 # do not deal with this case
    d = R[1]-R[0]             # ray direction vector
    w0 = R[0]-T[0]
    a = -numpy.dot(n,w0)
    b = numpy.dot(n,d)
    if math.fabs(b) < 0.00000001:     # ray is parallel to triangle plane
        if (a == 0):              # ray lies in triangle plane
            return (2,None)
        return (0,None)             # ray disjoint from plane
    # get intersect point of ray with triangle plane
    r = a / b
    if (r < 0.0):                   # ray goes away from triangle
        return (0,None)                  # => no intersect
    # for a segment, also test if (r > 1.0) => no intersect

    I = R[0] + r * d           # intersect point of ray and plane
    
    # is I inside T?
    uu = numpy.dot(u,u)
    uv = numpy.dot(u,v)
    vv = numpy.dot(v,v)
    w = I - T[0]
    wu = numpy.dot(w,u)
    wv = numpy.dot(w,v)
    D = uv * uv - uu * vv
    # get and test parametric coords
    s = (uv * wv - vv * wu) / D
    if (s < 0.0 or s > 1.0):        # I is outside T
        return (0,None)
    t = (uv * wu - uu * wv) / D
    if (t < 0.0 or (s + t) > 1.0):  # I is outside T
        return (0,None)
    return (1,I)                      # I is in T

def _ray_sphere(ray_origin,ray_dir,sphere_centre,sphere_radius_sqrd): # ray, sphere-centre, radius
    a = sum(_**2 for _ in ray_dir)
    assert a > 0.
    b = 2. * (numpy.dot(ray_dir,ray_origin) - numpy.dot(sphere_centre,ray_dir))
    c = sum(_**2 for _ in (sphere_centre - ray_origin)) - sphere_radius_sqrd
    disc = b * b - 4 * a * c
    return (disc >= 0.)
    
class Bounds:
    _Unbound = [[sys.maxint,sys.maxint,sys.maxint],[-sys.maxint,-sys.maxint,-sys.maxint]]
    def __init__(self):
        self._state = 0
        self.bounds = numpy.array(self._Unbound,dtype=numpy.float32)
    def add(self,pt):
        assert self._state in (0,1)
        self._state = 1
        for i in xrange(3):
            self.bounds[0,i] = min(self.bounds[0,i],pt[i])
            self.bounds[1,i] = max(self.bounds[1,i],pt[i])
    def fix(self):
        assert self._state == 1
        self._state = 2
        self.sphere_centre = numpy.array([a+(b-a)/2 for a,b in zip(self.bounds[0],self.bounds[1])],dtype=numpy.float32)
        self.sphere_radius_sqrd = sum(((a-b)/2)**2 for a,b in zip(self.bounds[0],self.bounds[1]))        
    def ray_intersects_sphere(self,ray_origin,ray_dir):
        return _ray_sphere(ray_origin,ray_dir,self.sphere_centre,self.sphere_radius_sqrd)

class IcoMesh:

    DIVIDE_THRESHOLD = 4
    
    def __init__(self,terrain,triangle,recursionLevel):
        self.terrain = terrain
        self.ID = len(terrain.meshes)
        self.boundary = numpy.array( \
            [(x,y,z,0) for x,y,z in [terrain.points[t] for t in triangle]],
            dtype=numpy.float32)
        self.bounds = Bounds()
        self._projection = numpy.empty((len(triangle),4),dtype=numpy.float32)
        assert recursionLevel <= self.DIVIDE_THRESHOLD
        def num_points(recursionLevel):
            Nc = (15,45,153,561,2145,8385)
            return Nc[recursionLevel-1]
        assert len(triangle) == 3
        self.faces = (triangle,)
        # refine triangles
        for i in xrange(recursionLevel+1):
            faces = numpy.empty((len(self.faces)*4,3),dtype=numpy.int32)
            faces_len = 0
            for tri in self.faces:
                # replace triangle by 4 triangles
                a = terrain._midpoint(tri[0],tri[1])
                b = terrain._midpoint(tri[1],tri[2])
                c = terrain._midpoint(tri[2],tri[0])
                faces[faces_len+0] = (tri[0],a,c)
                faces[faces_len+1] = (tri[1],b,a)
                faces[faces_len+2] = (tri[2],c,b)
                faces[faces_len+3] = (a,b,c)
                faces_len += 4
            assert faces_len == len(faces)
            self.faces = faces
        # make adjacency map
        def add_adjacency_faces(f,p):
            f |= (self.ID << Terrain.FACE_BITS)
            a = terrain.adjacency_faces[p]
            for i in xrange(6):
                if a[i] in (f,-1):
                    a[i] = f
                    return
            assert False, "%s %s"%(a,f)
        def add_adjacency_points(a,b):
            p = terrain.adjacency_points[a]
            for i in xrange(6):
                if p[i] in (b,-1):
                    p[i] = b
                    return
            assert False, "%s %s %s"%(a,p,b)
        for f,(a,b,c) in enumerate(self.faces):
            add_adjacency_faces(f,a)
            add_adjacency_faces(f,b)
            add_adjacency_faces(f,c)
            # assert f == (terrain.find_face(a,b,c) & Terrain.FACE_IDX)
            add_adjacency_points(a,b)
            add_adjacency_points(b,a)
            add_adjacency_points(a,c)
            add_adjacency_points(c,a)
            add_adjacency_points(b,c)
            add_adjacency_points(c,b)
            
    def _calc_normals(self):
        # do normals for all faces
        points, normals = self.terrain.points, self.terrain.normals
        for i,f in enumerate(self.faces):
            a = _vec_ofs(points[f[2]],points[f[1]])
            b = _vec_ofs(points[f[0]],points[f[1]])
            pn = _vec_normalise(_vec_cross(a,b))            
            for f in f:
                normals[f] += pn
                self.bounds.add(points[f])
        self.bounds.fix()
                
    def project(self,modelview):
        for i,pt in enumerate(self.boundary):
            pt = (pt * modelview)
            self._projection[i] = pt[0]
        # cull those whose outline points away; will need to account for high mountains visible on the horizon etc too of course
        if all(pt[2]<0. for pt in self._projection): return
        return self._projection
        
    def ray_intersection(self,R):
        T = numpy.empty((3,3),dtype=numpy.float32)
        def test(a,b,c):
            T[:] = a,b,c
            ret,I = _ray_triangle(R,T)
            if ret == 1:
                return I
        P = self.terrain.points
        for a,b,c in self.faces:
            I = test(P[a],P[b],P[c])
            if I is not None:
                return I
        
    def init_gl(self):
        rnd = random.random
        self.indices = self.terrain._vbo(self.faces,GL_ELEMENT_ARRAY_BUFFER)
        self.num_indices = len(self.faces)*3
        
    def draw_gl_ffp(self):
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.indices)
        glDrawElements(GL_TRIANGLES,self.num_indices,GL_UNSIGNED_INT,None)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0)

class Terrain:
    
    WATER_LEVEL = 0.9
    
    FACE_BITS = 18
    FACE_IDX = (1<<FACE_BITS)-1
    
    def __init__(self):
        self.meshes = []
        self._selection = self._selection_point = None
                
    def create_ico(self,recursionLevel):
        t = (1.0 + math.sqrt(5.0)) / 2.0
        self.midpoints = {}
        self.points = numpy.empty((5 * pow(2,2*recursionLevel+3) + 2,3),dtype=numpy.float32)
        self.points_len = 0
        self.adjacency_faces = numpy.empty((len(self.points),6),dtype=numpy.int32)
        self.adjacency_faces.fill(-1)
        self.adjacency_points = numpy.empty((len(self.points),6),dtype=numpy.int32)
        self.adjacency_points.fill(-1)
        for p in ( \
                (-1, t, 0),( 1, t, 0),(-1,-t, 0),( 1,-t, 0),
                ( 0,-1, t),( 0, 1, t),( 0,-1,-t),( 0, 1,-t),
                ( t, 0,-1),( t, 0, 1),(-t, 0,-1),(-t, 0, 1)):
            self._addpoint(p,True)
        for triangle in ( \
            (0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),
            (1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),
            (3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),
            (4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1)):
            def divide(tri,depth):
                if (recursionLevel-depth) < IcoMesh.DIVIDE_THRESHOLD:
                    self.meshes.append(IcoMesh(self,tri,recursionLevel-depth))
                else:
                    depth += 1
                    a = self._midpoint(tri[0],tri[1])
                    b = self._midpoint(tri[1],tri[2])
                    c = self._midpoint(tri[2],tri[0])
                    divide((tri[0],a,c),depth) 
                    divide((tri[1],b,a),depth)
                    divide((tri[2],c,b),depth)
                    divide((a,b,c),depth)
            divide(triangle,0)
            
        print len(self.meshes),"meshes,",len(self.points),"points",
        print sum(len(mesh.faces) for mesh in self.meshes),"faces",
        print "at",len(self.meshes[0].faces),"each."
        
        for p in self.points:
            p *= Terrain.WATER_LEVEL
        
        old = len(self.points)
        
        # quick test; make the map noisy
        self._rnd_ridge(int(random.random()*len(self.points)),15,1)
        
        assert(self.points_len == len(self.points))
        
        # meshes apply their face normals to our vertices
        self.normals = numpy.zeros((len(self.points),3),dtype=numpy.float32)
        for mesh in self.meshes:
            mesh._calc_normals()
        # average vertex normals
        for i in xrange(len(self.points)):
            f = sum(1 if a != -1 else 0 for a in self.adjacency_points[i])
            assert self.adjacency_points[i,1] != -1,"%s %s %s"%(i,self.adjacency_points[i],f)
            np = self.normals[i] / f 
            self.normals[i] = _vec_normalise(np)
            
        # apply colour-scheme
        self.colours = numpy.zeros((len(self.points),3),dtype=numpy.uint8)
        heights = ( \
            (1.,0xff,0xff,0xff),
            (.8,0xdc,0xdc,0xdc),
            (.5,0x00,0x7c,0x00),
            (.3,0x22,0x8b,0x22),
            (.1,0x00,0xff,0x00),
            (0.,0x00,0x00,0xff))
        for i,p in enumerate(self.points):
            if i > old:
                r,g,b = 0,0,0
            else:
                height = math.sqrt(sum(d**2 for d in p))
                height -= Terrain.WATER_LEVEL
                height *= 1./(1.-Terrain.WATER_LEVEL)
                r,g,b = heights[0][1:] 
                for val,r,g,b in heights[1:]:
                    if height > val:
                        break
            self.colours[i] = (r,g,b)
            
    def _rnd_ridge(self,start,L,height):
        pos = start
        walk = (random.random(),random.random(),random.random())
        for i in xrange(L):
            # find two adjacent points that are nearest to direction
            neighbours = []
            for p in self.adjacency_points[pos]:
                if p == -1:
                    assert len(neighbours) >= 2, neighbours
                    break
                neighbours.append((-sum((a-b)**2 for a,b in zip(self.points[p],walk)),p))
            neighbours.sort()
            a,b,c = pos,neighbours[0][1],neighbours[1][1]
            face = self._split(self.find_face(a,b,c))
            pos = self.midpoints[self._midpoint_key(b,c)]
            pos = self.find_other_common_point(b,c,pos)
            print a,b,c, pos
            continue
            for j in xrange(3):
                h = math.sqrt(sum(_**2 for _ in self.points[pos]))
                adjust = height/h
                self.points[pos] *= adjust
            pos = self.adjacency_points[pos,int(random.random()*3)]
            
    def pick(self,x,y):
        glScale(.8,.8,.8)
        modelview = numpy.matrix(glGetDoublev(GL_MODELVIEW_MATRIX))
        projection = numpy.matrix(glGetDoublev(GL_PROJECTION_MATRIX))
        viewport = glGetIntegerv(GL_VIEWPORT)
        self._selection = self._selection_point = None
        R = numpy.array([gluUnProject(x,y,10,modelview,projection,viewport),
            gluUnProject(x,y,-10,modelview,projection,viewport)],
            dtype=numpy.float32)
        ray_origin, ray_dir = R[0], R[1]-R[0]
        candidates = []
        for mesh in self.meshes:
            if mesh.bounds.ray_intersects_sphere(ray_origin,ray_dir):
                candidates.append(( \
                    -sum((a-b)**2 for a,b in zip(mesh.bounds.sphere_centre,ray_origin)), # distance from ray
                    mesh))
        candidates.sort() # sort by distance, nearest first
        for _,mesh in candidates:
            I = mesh.ray_intersection(R)
            if I is not None:
                self._selection = mesh
                self._selection_point = I
                break
        return ([],[])
            
    def _vbo(self,array,target):
        handle = glGenBuffers(1)
        assert handle > 0
        glBindBuffer(target,handle)
        glBufferData(target,array,GL_STATIC_DRAW)
        glBindBuffer(target,0)
        return handle

    def _addpoint(self,point,normalise):
        slot = self.points_len
        self.points_len += 1
        if normalise:
            dist = math.sqrt(sum(_**2 for _ in point))
            for i in xrange(3): self.points[slot,i] = point[i]/dist
        else:
            self.points[slot] = point
        return slot
        
    def _midpoint_key(self,a,b):
        return (min(a,b) << 32) + max(a,b)

    def _midpoint(self,a,b,extend=False):
        key = self._midpoint_key(a,b)
        if key not in self.midpoints:
            a = self.points[a]
            b = self.points[b]
            mid = tuple((p1+p2)/2. for p1,p2 in zip(a,b))
            if extend:
                assert self.points_len == len(self.points)
                self.points = numpy.resize(self.points,(self.points_len+1,3))
                self.adjacency_faces = numpy.resize(self.adjacency_faces,(self.points_len+1,6))
                self.adjacency_faces[-1].fill(-1)
                self.adjacency_points = numpy.resize(self.adjacency_points,(self.points_len+1,6))
                self.adjacency_points[-1].fill(-1)
            self.midpoints[key] = self._addpoint(mid,not extend)
        return self.midpoints[key]
        
    def find_face(self,a,b,c):
        face = set(self.adjacency_faces[a])
        face &= set(self.adjacency_faces[b])
        face &= set(self.adjacency_faces[c])
        f = face.pop()
        if f == -1:
            f = face.pop()
        assert len(face) == 0
        return f
        
    def find_other_common_point(self,a,b,c):
        points = set(self.adjacency_points[a])
        points &= set(self.adjacency_points[b])
        while True:
            p = points.pop()
            if p in (-1,c): continue
            return p
        
    def _split(self,tri):
        ID = tri >> Terrain.FACE_BITS
        face = tri & Terrain.FACE_IDX
        mesh = self.meshes[ID]
        tri = mesh.faces[face]
        print ID,face,tri
        def rewrite(array,a,b,c):
            for i in xrange(6):
                if array[a,i] == b:
                    array[a,i] = c
                    return
                assert array[a,i] != -1
            assert False, "%s %s %s %s"%(a,array[a],b,c)
        def split_point(a,b):
            c = self._midpoint(a,b,True)
            if c == self.points_len-1:
                self.adjacency_points[-1,0] = a
                self.adjacency_points[-1,1] = b
                rewrite(self.adjacency_points,a,b,c)
                rewrite(self.adjacency_points,b,a,c)
            return c
        def rewrite_face(a,x):
            rewrite(self.adjacency_faces,a,(ID << Terrain.FACE_BITS)|face,(ID << Terrain.FACE_BITS)|(len(mesh.faces)-x))
        def add_adjacency_faces(a):
            def add(b):
                b |= (ID << Terrain.FACE_BITS)
                for i in xrange(6):
                    if self.adjacency_faces[a,i] in (b,-1):
                        self.adjacency_faces[a,i] = b
                        return
                assert False, "%s %s %s"%(a,self.adjacency_faces[a],b)
            add(face)
            add(len(mesh.faces)-3)
            add(len(mesh.faces)-2)
            add(len(mesh.faces)-1)
        a = split_point(tri[0],tri[1])
        b = split_point(tri[1],tri[2])
        c = split_point(tri[2],tri[0])
        mesh.faces = numpy.resize(mesh.faces,(len(mesh.faces)+3,3))
        mesh.faces[-3] = (tri[0],a,c)
        rewrite_face(tri[0],-3)
        mesh.faces[-2] = (tri[1],b,a)
        rewrite_face(tri[1],-2)
        mesh.faces[-1] = (tri[2],c,b)
        rewrite_face(tri[2],-1)
        abc = (a,b,c)
        mesh.faces[face] = abc
        for _ in abc:
            add_adjacency_faces(_)
        return abc
        
    def init_gl(self):
        for mesh in self.meshes:
            mesh.init_gl()
        self._vbo_vertices = self._vbo(self.points,GL_ARRAY_BUFFER)
        self._vbo_normals = self._vbo(self.normals,GL_ARRAY_BUFFER)
        self._vbo_colours = self._vbo(self.colours,GL_ARRAY_BUFFER)
            
    def draw_gl_ffp(self,event):
        glClearColor(1,1,1,1)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glScale(.8,.8,.8)
        glEnable(GL_CULL_FACE)
        glEnableClientState(GL_VERTEX_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER,self._vbo_vertices)
        glVertexPointer(3,GL_FLOAT,0,None)
        glEnableClientState(GL_NORMAL_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER,self._vbo_normals)
        glNormalPointer(GL_FLOAT,0,None)
        glEnableClientState(GL_COLOR_ARRAY)
        glBindBuffer(GL_ARRAY_BUFFER,self._vbo_colours)
        glColorPointer(3,GL_UNSIGNED_BYTE,0,None)
        glBindBuffer(GL_ARRAY_BUFFER,0)
        modelview = numpy.matrix(glGetDoublev(GL_MODELVIEW_MATRIX))
        culled = 0
        for mesh in self.meshes:
            if mesh.project(modelview) is None:
                culled += 1
                continue
            if mesh == self._selection:
                glDisableClientState(GL_COLOR_ARRAY)
                glColor(1,0,0,1)
            mesh.draw_gl_ffp()
            if mesh == self._selection:
                glEnableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_NORMAL_ARRAY)
        if self._selection_point is not None:
            glColor(0,0,1,1)
            glTranslate(*self._selection_point)
            glutSolidSphere(0.03,20,20)
        glDisable(GL_CULL_FACE)
        #print (len(self.meshes)-culled),"drawn,",culled,"culled."

