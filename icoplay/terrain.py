
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
    def __init__(self,terrain,triangle,recursionLevel):
        self.terrain = terrain
        def num_points(recursionLevel):
            # return 5 * pow(2,2*recursionLevel+3) + 2
            # 3 = 153
            return 153
        def add(point):
            slot = self.points_len
            self.points_len += 1
            dist = 0
            for i in xrange(3): dist += point[i]**2
            dist = math.sqrt(dist)
            for i in xrange(3): self.points[slot,i] = point[i]/dist
            return slot
        def midpoint(a,b):
            key = (min(a,b) << 32) + max(a,b)
            if key not in midpoints:
                a = self.points[a]
                b = self.points[b]
                mid = tuple((p1+p2)/2. for p1,p2 in zip(a,b))
                midpoints[key] = add(mid)
            return midpoints[key]
        self.points = numpy.empty((num_points(recursionLevel),3),dtype=numpy.float32)
        assert len(triangle) == 3
        self.points_len = 0
        for i,p in enumerate(triangle):
            add(p)
        self.points_len = 3
        midpoints = {}
        self.faces = ((0,1,2),)
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
        assert len(self.points) == self.points_len, "%s %s"%(len(self.points),self.points_len)
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
            assert False, "%s %s"%(a,f)
        for f,(a,b,c) in enumerate(self.faces):
            add_adjacency(f,a)
            add_adjacency(f,b)
            add_adjacency(f,c)
        # note those edges
        self.outline = []
        for i,a in enumerate(self.adjacency):
            if a[4] == -1:
                self.outline.append(i)
        # do normals for all faces
        self.normal_faces = numpy.empty((len(self.faces),3),dtype=numpy.float32)
        for i,f in enumerate(self.faces):
            a = _vec_ofs(self.points[f[2]],self.points[f[1]])
            b = _vec_ofs(self.points[f[0]],self.points[f[1]])
            pn = _vec_cross(a,b)
            self.normal_faces[i] = _vec_normalise(pn)
        
    def _get_edge_normals(self,pt,norm):
        for i in self.outline:
            if all(a==b for a,b in zip(self.points[i],pt)):
                for f,a in enumerate(self.adjacency[i]):
                    if a == -1: break
                    norm += self.normal_faces[a]
                return f+1
            
    def init2(self):
        # do normals for all vertices
        self.normal_vertices = numpy.empty((len(self.points),3),dtype=numpy.float32)
        norm = numpy.empty(3,dtype=numpy.float32)
        for i in xrange(len(self.points)):
            norm.fill(0)
            for f,a in enumerate(self.adjacency[i]):
                if a == -1: 
                    if f < 4:
                        for mesh in self.terrain.meshes:
                            if mesh == self: continue
                            join = mesh._get_edge_normals(self.points[i],norm)
                            if join is not None:
                                f += join
                    break
                norm += self.normal_faces[a]
            norm /= (f+1)
            self.normal_vertices[i] = _vec_normalise(norm)
        rnd = random.random
        self.colour = (rnd(),rnd(),rnd(),1)
        
    def draw_gl_ffp(self):
        def plot(i):
            glNormal(*self.normal_vertices[i])
            glVertex(self.points[i,0:3])
        glBegin(GL_TRIANGLES)
        glColor(*self.colour)
        for i,(a,b,c) in enumerate(self.faces):
            plot(a)
            plot(b)
            plot(c)
        glEnd()

class Terrain:
    
    def __init__(self):
        self.meshes = []
                
    def create_ico(self,recursionLevel):
        t = (1.0 + math.sqrt(5.0)) / 2.0
        p = ( \
                (-1, t, 0),( 1, t, 0),(-1,-t, 0),( 1,-t, 0),
                ( 0,-1, t),( 0, 1, t),( 0,-1,-t),( 0, 1,-t),
                ( t, 0,-1),( t, 0, 1),(-t, 0,-1),(-t, 0, 1))
        for a,b,c in ( \
            (0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),
            (1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),
            (3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),
            (4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1)):
            self.meshes.append(IcoMesh(self,(p[a],p[b],p[c]),recursionLevel))
            
        for mesh in self.meshes:
            mesh.init2()
            
    def draw_gl_ffp(self,event):
        glClearColor(1,1,1,1)
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
        glScale(.8,.8,.8)
        for mesh in self.meshes:
            mesh.draw_gl_ffp()
