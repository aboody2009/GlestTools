#!/usr/bin/env python

class Model:

    def load(self,filename):
        ext = os.path.splitext(filename)[1].upper()
        if ext == '.OBJ':
            print "Loading",filename,"as Wavefront OBJ"
            self._load_obj(filename)
        elif ext == ".3DW":
            print "Loading",filename,"as internal 3DW format"
            raise Exception("3DW loading not implemented yet")
        else:
            raise Exception("Cannot handle %s files"%ext)
            
    def save(self,filename):
        ext = os.path.splitext(filename)[1].upper()
        if ext == '.OBJ':
            print "Saving",filename,"as Wavefront OBJ"
            self._save_obj(filename)
        elif ext == '.3DW':
            print "Saving",filename,"as internal 3DW format"
            self._save_3dw(filename)
        else:
            raise Exception("Cannot handle %s files"%ext)
            
    def describe(self):
        print len(self.vertices),"vertices"
        print len(self.normals),"normals"
        print len(self.texcoords),"texture coordinates"
        print len(self.objs),"objects"
        for obj_name,obj in self.objs:
            print "\tobject",obj_name,"(%d meshes)"%len(obj)
            for i,mesh in enumerate(obj):
                print "\t\tmesh",i,mesh[0],"(%d faces)"%len(mesh[1])

    def _load_obj(self,filename):
        self.vertices = []
        self.texcoords = []
        self.normals = []
        mesh = []
        mesh_name = None
        mesh_mat = None
        self.objs = []
        obj = []
        obj_name = ""
        def split_opt(x):
            x = x.split()
            if len(x) > 1:
                return x
            else:
                return x[0],0
        with open(filename,"r") as f:
            for line_num,line in enumerate(f.readlines()):
                try:
                    line = line.strip()
                    if line.startswith("#") or (len(line) == 0):
                        continue # ignore comments and empty lines
                    cmd = line.split()[0]
                    if cmd == "v":
                        x, y, z = line[1:].split(None,3)
                        z, w = split_opt(z)
                        self.vertices.append((float(x),float(y),float(z),float(w)))
                    elif cmd == "vt":
                        u, v = line[2:].split(None,2)
                        v, w = split_opt(v)
                        self.texcoords.append((float(u),float(v),float(w)))
                    elif cmd == "vn":
                        x, y, z = line[2:].split()
                        self.normals.append((float(x),float(y),float(z)))
                    elif cmd == "o":
                        if mesh_name is not None:
                            obj.append((mesh_name,mesh,mesh_mat))
                        if len(obj) > 0:
                            self.objs.append((obj_name,obj))
                        obj_name = line[1:].strip()
                        obj, mesh, mesh_name = [],[],""
                    elif cmd == "g":
                        if mesh_name is not None:
                            obj.append((mesh_name,mesh,mesh_mat))
                            mesh, mesh_mat = [], None
                        mesh_name = line[1:].strip()
                    elif cmd == "f":
                        if mesh_name is None:
                            raise Exception("cannot handle faces outside a group")
                        faces = []
                        for face in line[1:].split():
                            indices = []
                            for idx in face.split("/"):
                                if idx == "":
                                    idx = None
                                else:
                                    idx = int(idx)
                                    if idx < 0:
                                        raise Exception("cannot cope with negative indices (yet)")
                                indices.append(idx)
                            faces.append(indices)
                        if len(faces) != 3:
                            raise Exception("cannot handle non-triangles")
                        mesh.append(faces)
                    elif cmd == "usemtl":
                        mesh_mat = line[6:].strip()
                    else:
                        raise Exception("cannot handle: %s"%cmd)
                except:
                    print "Error parsing %s:%d: %s"%(filename,line_num,line)
                    raise
        if mesh_name is not None:
            obj.append((mesh_name,mesh,mesh_mat))
        if len(obj) > 0:
            self.objs.append((obj_name,obj))
            
    def _save_obj(self,filename):
        def trim(f): # we go to this trouble just to make it easily diffable with likely original columns
            f = "%-0.05f"%f
            if not f.startswith("-"): f = " %s"%f
            return f
        with open(filename,"w") as f:
            for x,y,z,w in self.vertices:
                f.write("v %s %s %s"%(trim(x),trim(y),trim(z)))
                if w != 0: f.write(" %s",trim(w))
                f.write('\n')
            for u,v,w in self.texcoords:
                f.write("vt %s %s"%(trim(u),trim(v)))
                if w != 0: f.write(" %s",trim(w))
                f.write('\n')
            for x,y,z in self.normals:
                f.write("vn %s %s %s\n"%(trim(x),trim(y),trim(z)))
            for obj_name,obj in self.objs:
                if obj_name != "": f.write("o %s\n"%obj_name)
                for mesh_name,mesh,mesh_mat in obj:
                    f.write("g %s\n"%mesh_name)
                    if mesh_mat is not None: f.write("usemtl %s\n"%mesh_mat)
                    for faces in mesh:
                        f.write("f");
                        for face in faces:
                            f.write(" %s"%"/".join("%s"%("" if idx is None else idx) for idx in face))
                        f.write("\n")
                        
    def _save_3dw(self,filename):
        from math import sqrt
        def dist(a,b):
            sqrd = (a[0]-b[0])**2 + \
                (a[1]-b[1])**2 + \
                (a[2]-b[2])**2
            if sqrd > 0:
                return sqrt(sqrd)
            return 0
        def feq(a,b):
            return abs(a-b) < 0.000001
        with open(filename,"w") as f:
            for obj_name, obj in self.objs:
                for mesh_name,mesh,mesh_mat in obj:
                    f.write("mesh %s %s\n"%(mesh_name,mesh_mat))
                    triangles = tuple([tuple([face[0]-1 for face in faces]) for faces in mesh])
                    
                    meshes.append((obj_name,mesh_name,triangles,_index(triangles,self.vertices)))
                    dup.append(None)
                    
def confirm(prompt,default=False):
    if default:
        prompt = "\n%s [y]n: "%prompt
    else:
        prompt = "\n%s y[n]: "%prompt
    while True:
        ch = raw_input(prompt)
        if not ch:
            return default
        if ch in "yY":
            return True
        if ch in "nN":
            return False
        print "please answer y or n"

if __name__ == "__main__":
    
    import sys, os
    
    if len(sys.argv) != 3:
        print "Usage: 3D_compress.py infile outfile"
        print "Supported formats:"
        print "\tWavefront OBJ files"
        print "\t3DW (internal 3D format)"
        sys.exit(1)
        
    _, src, dest = sys.argv
        
    if os.path.exists(dest):
        if not os.path.isfile(dest):
            print "Error:",dest,"is not a file"
            sys.exit(1)
        if not confirm("%s exists! overwrite it?"%dest):
            sys.exit(1)
        
    model = Model()
    
    model.load(src)
    
    model.describe()
   
    model.save(dest)
