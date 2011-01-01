
import numpy, math, random
from OpenGL.GL import *

class Terrain:
    
    def __init__(self):
        self.faces = ()
        self.points = ()
        self.adjacency = ()
        
    def create_ico(self,recursionLevel):
        def num_points(recursionLevel):
            return 5 * pow(2,2*recursionLevel+3) + 2 
        # a point is xyz and dist from centre cached
        self.points = numpy.zeros((num_points(recursionLevel),4),dtype=numpy.float32)
        self.points_len = 0
        midpoints = {}
        def add(point):
            slot = self.points_len
            self.points_len += 1
            dist = 0
            for i in xrange(3): dist += point[i]**2
            dist = math.sqrt(dist)
            for i in xrange(3): self.points[slot,i] = point[i]/dist
            self.points[slot,3] = dist
            return slot
        def midpoint(a,b):
            key = (min(a,b) << 32) + max(a,b)
            if key not in midpoints:
                a = self.points[a]
                b = self.points[b]
                mid = tuple((p1+p2)/2. for p1,p2 in zip(a,b))
                midpoints[key] = add(mid)
            return midpoints[key]
        t = (1.0 + math.sqrt(5.0)) / 2.0
        [add(p) for p in ( \
                (-1, t, 0),( 1, t, 0),(-1,-t, 0),( 1,-t, 0),
                ( 0,-1, t),( 0, 1, t),( 0,-1,-t),( 0, 1,-t),
                ( t, 0,-1),( t, 0, 1),(-t, 0,-1),(-t, 0, 1))]
        # create 20 triangles of the icosahedron
        self.faces = []
        # 5 self.faces around point 0
        [self.faces.append(t) for t in ((0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11))]
        # 5 adjacent self.faces 
        [self.faces.append(t) for t in ((1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8))]
        # 5 self.faces around point 3
        [self.faces.append(t) for t in ((3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9))]
        # 5 adjacent self.faces 
        [self.faces.append(t) for t in ((4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1))]
        # refine triangles
        for i in xrange(recursionLevel+1):
            faces = []
            for tri in self.faces:
                # replace triangle by 4 triangles
                a = midpoint(tri[0],tri[1])
                b = midpoint(tri[1],tri[2])
                c = midpoint(tri[2],tri[0])
                faces.append((tri[0],a,c))
                faces.append((tri[1],b,a))
                faces.append((tri[2],c,b))
                faces.append((a,b,c))
            self.faces = faces
        assert len(self.points) == self.points_len
        del self.points_len
        # make adjacency map
        self.adjacency = numpy.empty((len(self.points),6),dtype=numpy.int32)
        self.adjacency.fill(-1)
        def add_adjacency(f,p):
            a = self.adjacency[p]
            for i in xrange(6):
                if a[i] in (f,-1):
                    a[i] = f
                    return
            assert False
        for f,(a,b,c) in enumerate(self.faces):
            add_adjacency(f,a)
            add_adjacency(f,b)
            add_adjacency(f,c)
        for j,i in enumerate(self.adjacency): assert i[4] != -1, "%s,%s,%s"%(j,len(self.adjacency),i)
        # do normals for all faces
        self.normal_faces = numpy.empty((len(self.faces),3),dtype=numpy.float32)
        def vec_cross(a,b):
            return ( \
                (a[1]*b[2]-a[2]*b[1]),
                (a[2]*b[0]-a[0]*b[2]),
                (a[0]*b[1]-a[1]*b[0]))
        def vec_ofs(v,ofs):
            return (v[0]-ofs[0],v[1]-ofs[1],v[2]-ofs[2])
        def vec_normalise(v):
            l = math.sqrt(sum(d**2 for d in v))
            if l > 0:
                return (v[0]/l,v[1]/l,v[2]/l)
            return v
        for i,f in enumerate(self.faces):
            a = vec_ofs(self.points[f[2]],self.points[f[1]])
            b = vec_ofs(self.points[f[0]],self.points[f[1]])
            pn = vec_cross(a,b)
            self.normal_faces[i] = vec_normalise(pn)
        # do normals for all vertices
        self.normal_vertices = numpy.empty((len(self.points),3),dtype=numpy.float32)
        norm = numpy.empty(3,dtype=numpy.float32)
        for i in xrange(len(self.points)):
            norm.fill(0)
            for f,a in enumerate(self.adjacency[i]):
                if a == -1: break
                norm += self.normal_faces[a]
            norm /= (f+1)
            self.normal_vertices[i] = norm #vec_normalise(norm)
        
    def draw_gl_ffp(self,event):
        glClearColor(1,1,1,1)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glScale(.8,.8,.8)
        glColor(0,0,1,1)
        def plot(i):
            glNormal(*self.normal_vertices[i])
            glVertex(self.points[i,0:3])
        glBegin(GL_TRIANGLES)
        for i,(a,b,c) in enumerate(self.faces):
            plot(a)
            plot(b)
            plot(c)
        glEnd()
        

terrain = Terrain()
terrain.create_ico(3)

