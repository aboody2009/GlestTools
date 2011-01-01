
import numpy, math, random, sys
from OpenGL.GL import *

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

class IcoMesh:

    DIVIDE_THRESHOLD = 4
    
    def __init__(self,terrain,triangle,recursionLevel):
        self.terrain = terrain
        self.ID = len(terrain.meshes)
        self.boundary = tuple(terrain.points[t] for t in triangle)
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
        for i,f in enumerate(self.faces):
            points, normals = self.terrain.points, self.terrain.normals
            a = _vec_ofs(points[f[2]],points[f[1]])
            b = _vec_ofs(points[f[0]],points[f[1]])
            pn = _vec_normalise(_vec_cross(a,b))            
            for f in f:
                normals[f] += pn
        
    def init_gl(self):
        rnd = random.random
        self.colour = (rnd(),rnd(),rnd(),1)
        for f in self.faces:
            for f in f:
                self.terrain.colours[f] = self.colour
        self.indices = self.terrain._vbo(self.faces,GL_ELEMENT_ARRAY_BUFFER)
        self.num_indices = len(self.faces)*3
        
    def draw_gl_ffp(self):
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,self.indices)
        glDrawElements(GL_TRIANGLES,self.num_indices,GL_UNSIGNED_INT,None)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER,0)

class Terrain:
    
    def __init__(self):
        self.meshes = []
                
    def create_ico(self,recursionLevel):
        t = (1.0 + math.sqrt(5.0)) / 2.0
        self.midpoints = {}
        self.points = numpy.empty((5 * pow(2,2*recursionLevel+3) + 2,3),dtype=numpy.float32)
        self.points_len = 0
        self.adjacency = numpy.empty((len(self.points),6),dtype=numpy.int32)
        self.adjacency.fill(-1)
        self.normals = numpy.zeros((len(self.points),3),dtype=numpy.float32)
        self.colours = numpy.zeros((len(self.points),4),dtype=numpy.float32)
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
            adjust = 0.9 + random.random()*0.1
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
        glColorPointer(4,GL_FLOAT,0,None)
        glBindBuffer(GL_ARRAY_BUFFER,0)
        
        modelview = numpy.matrix(glGetDoublev(GL_MODELVIEW_MATRIX))
        culled = 0
        for mesh in self.meshes:
            # cull those whose outline points away; will need to account for high mountains visible on the horizon etc too of course
            cull = True
            for pt in mesh.boundary:
                pt = (pt[0],pt[1],pt[2],0) * modelview
                if pt[0,2] > -0.1: # this ought to be based on height of highest peaks in that piece of terrain
                    cull = False
                    break
            if cull:
                culled += 1
                continue
            mesh.draw_gl_ffp()
            
        print (len(self.meshes)-culled),"drawn,",culled,"culled."

