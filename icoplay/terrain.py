
import numpy, math, random, sys
from OpenGL.GL import *
from OpenGL.GLU import *

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

class IcoMesh:

    DIVIDE_THRESHOLD = 4
    
    def __init__(self,terrain,triangle,recursionLevel):
        self.terrain = terrain
        self.ID = len(terrain.meshes)
        self.boundary = numpy.array( \
            [(x,y,z,0) for x,y,z in [terrain.points[t] for t in triangle]],
            dtype=numpy.float32)
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
        def add_adjacency(f,p):
            f |= (self.ID << 32)
            a = terrain.adjacency[p]
            for i in xrange(6):
                if a[i] in (f,-1):
                    a[i] = f
                    return
            assert False, "%s %s"%(a,f)
        for f,(a,b,c) in enumerate(self.faces):
            add_adjacency(f,a)
            add_adjacency(f,b)
            add_adjacency(f,c)
            
    def _calc_normals(self):
        # do normals for all faces
        points, normals = self.terrain.points, self.terrain.normals
        bounds = self.bounds = numpy.array([[-1,-1,-1],[1,1,1]],dtype=numpy.float32)
        for i,f in enumerate(self.faces):
            a = _vec_ofs(points[f[2]],points[f[1]])
            b = _vec_ofs(points[f[0]],points[f[1]])
            pn = _vec_normalise(_vec_cross(a,b))            
            for f in f:
                normals[f] += pn
                for i in xrange(3):
                    bounds[0,i] = max(bounds[0,i],points[f,i])
                    bounds[1,i] = min(bounds[1,i],points[f,i])
                
    def project(self,modelview):
        for i,pt in enumerate(self.boundary):
            pt = (pt * modelview)
            self._projection[i] = pt[0]
        # cull those whose outline points away; will need to account for high mountains visible on the horizon etc too of course
        if all(pt[2]<0. for pt in self._projection): return
        return self._projection
        
    def contains_point(self,R,fast):
        T = numpy.empty((3,3),dtype=numpy.float32)
        def test(a,b,c):
            T[:] = a,b,c
            ret,I = _ray_triangle(R,T)
            if ret == 1:
                return I
        if fast:
            def bounds(x,y,z):
                return (self.bounds[x,0],self.bounds[y,1],self.bounds[z,2])
            tl,tr,br,bl,trb,brb,tlb,blb = ( \
                (0,0,0),(1,0,0),(1,1,0),(0,1,0),
                (0,0,1),(1,0,1),(1,1,1),(0,1,1))
            intersects_bounds = False
            for a,b,c,d in ((tl,tr,br,bl),(tr,trb,brb,br),(tl,tlb,blb,bl)):
                a,b,c,d = bounds(*a),bounds(*b),bounds(*c),bounds(*d)
                I = test(a,b,c)
                if I is not None:
                    intersects_bounds = True
                    break
                I = test(a,c,d)
                if I is not None:
                    intersects_bounds = True
                    break
            if not intersects_bounds:
                return
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
    
    def __init__(self):
        self.meshes = []
        self._selection = None
                
    def create_ico(self,recursionLevel):
        t = (1.0 + math.sqrt(5.0)) / 2.0
        self.midpoints = {}
        self.points = numpy.empty((5 * pow(2,2*recursionLevel+3) + 2,3),dtype=numpy.float32)
        self.points_len = 0
        self.adjacency = numpy.empty((len(self.points),6),dtype=numpy.int32)
        self.adjacency.fill(-1)
        self.normals = numpy.zeros((len(self.points),3),dtype=numpy.float32)
        for p in ( \
                (-1, t, 0),( 1, t, 0),(-1,-t, 0),( 1,-t, 0),
                ( 0,-1, t),( 0, 1, t),( 0,-1,-t),( 0, 1,-t),
                ( t, 0,-1),( t, 0, 1),(-t, 0,-1),(-t, 0, 1)):
            self._addpoint(p)
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
        
        # quick test; make the map noisy
        for p in self.points:
            adjust = Terrain.WATER_LEVEL + random.random()*(1.-Terrain.WATER_LEVEL)
            p *= adjust

        # meshes apply their face normals to our vertices
        for mesh in self.meshes:
            mesh._calc_normals()
        # average vertex normals
        for i in xrange(len(self.points)):
            assert self.adjacency[i,4] != -1,"%s %s"%(i,self.adjacency[i])
            f = 5 if self.adjacency[i,5] == -1 else 6
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
            height = math.sqrt(sum(d**2 for d in p))
            height -= Terrain.WATER_LEVEL
            height *= 1./(1.-Terrain.WATER_LEVEL)
            for val,r,g,b in heights:
                if height > val:
                    break
            self.colours[i] = (r,g,b)
            
    def pick(self,x,y):
        glScale(.8,.8,.8)
        modelview = numpy.matrix(glGetDoublev(GL_MODELVIEW_MATRIX))
        projection = numpy.matrix(glGetDoublev(GL_PROJECTION_MATRIX))
        viewport = glGetIntegerv(GL_VIEWPORT)
        R = numpy.array([gluUnProject(x,y,10,modelview,projection,viewport),
            gluUnProject(x,y,-10,modelview,projection,viewport)],
            dtype=numpy.float32)
        def find(fast):
            best = (-1000,None,None)
            for mesh in self.meshes:
                pt = mesh.contains_point(R,fast)
                if pt is not None:
                    ptz = (pt[0],pt[1],pt[2],0)
                    z = (ptz * modelview)[0,2]
                    if z > best[0]:
                        best = (z,mesh,pt)                
            return best
        best = find(True)
        self._selection = best[1]
        # try and narrow down a bug in the bounds code
        if self._selection is None:
            best = find(False)
            self._selection = best[1]
            if self._selection is not None:
                print "FAILURE!",best
        return ([],[])
            
    def _vbo(self,array,target):
        handle = glGenBuffers(1)
        assert handle > 0
        glBindBuffer(target,handle)
        glBufferData(target,array,GL_STATIC_DRAW)
        glBindBuffer(target,0)
        return handle

    def _addpoint(self,point):
        slot = self.points_len
        self.points_len += 1
        dist = 0
        for i in xrange(3): dist += point[i]**2
        dist = math.sqrt(dist)
        for i in xrange(3): self.points[slot,i] = point[i]/dist
        return slot

    def _midpoint(self,a,b):
        key = (min(a,b) << 32) + max(a,b)
        if key not in self.midpoints:
            a = self.points[a]
            b = self.points[b]
            mid = tuple((p1+p2)/2. for p1,p2 in zip(a,b))
            self.midpoints[key] = self._addpoint(mid)
        return self.midpoints[key]
        
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
            
        #print (len(self.meshes)-culled),"drawn,",culled,"culled."

