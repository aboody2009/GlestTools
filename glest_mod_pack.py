#!/usr/bin/env python

# glest_mod_pack is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

help_modname = """
*** Illegal mod folder-name; these are the rules: ***
The name is made of elements separated by periods.
The name of a mod containing a tech-tree is the first name, e.g. Military
The version of the mod then follows e.g. Military.1.2
If this is an extension and does not contain a tech-tree, then
the name of the extension follows e.g. Military.1.2.CyberStorm
These extensions also need version numbers e.g. Military.1.2.CyberStorm.0.3
Extensions can themselves be extended..."""

legal_path_chars = "abcdefghijklmnopqrstuvwxyz1234567890._-/"

import os, sys, string
import xml.dom.minidom as minidom
from struct import unpack
from itertools import chain
import zipfile, time

class File:
    """a file (type and path)"""
    MAP = "map"
    SCENARIO = "scenario"
    FRACTION = "faction"
    TILESET = "tileset"
    TEXTURE = "texture"
    TECH_TREE = "tech-tree"
    UNIT = "unit"
    FACTION = "faction"
    MODEL = "model"
    SOUND = "sound"
    PARTICLE = "particle"
    UPGRADE = "upgrade"
    RESOURCE = "resource"
    LANGUAGE = "language"
    def __init__(self,mod,typ,path):
        self.mod = mod
        self.typ = typ           
        self.references = {}
        self.referenced_by = set()
        self.broken = False
        self.inited = False
        self.path = path
        self.modpath = os.path.relpath(path,mod.base_folder).replace("\\","/").lower();
        if not os.path.isfile(self.path):
            self.error("Does not exist")
        elif self.modpath.startswith("..") or self.modpath.startswith("/"):
            self.error("external dependency not yet supported")
        else:
            for ch in self.modpath:
                if ch not in legal_path_chars:
                    self.error("name contains illegal characters")
        self.filesize = filesize = 0 if self.broken else os.path.getsize(path)
        if not self.broken and os.path.splitext(self.path)[1] == ".xml":
            try:
                self.xml = mod._init_xml(self)
            except Exception,e:
                self.error(("Error reading xml",str(e)))
                raise
    def error(self,*args):
        self.broken = True
        broken = self.mod.broken
        if self not in broken:
            broken[self] = []
        for prev in broken[self]:
            if prev == args:
                break
        else:
            broken[self].append(args)
    def optimised_body(self):
        if hasattr(self,"xml"):
            return self.xml.toxml("utf-8")
        elif hasattr(self,"_g3d_body"):
            return buffer(self._g3d_body)
    def get_bytes(self):
        if self.broken: return
        if not hasattr(self,"_bytes"):
            self._bytes = file(self.path,"rb").read()
        return self._bytes
    def g3d_body(self):
        assert os.path.splitext(self.path)[1] == ".g3d"
        if not hasattr(self,"_g3d_body"):
            body = self._g3d_body = bytearray(self.get_bytes())
        return self._g3d_body
    def subpath(self,r):
        return os.path.abspath(os.path.dirname(self.path)+"/"+r)
    def __repr__(self):
        references = ", ".join(["%s %s"%(r.typ,r.modpath) for r in self.references])
        referenced_by = ", ".join(["%s %s"%(r.typ,r.modpath) for r in self.referenced_by])
        return "%s%s %s%s%s%s"%(self.typ,
            " BROKEN" if self.broken else "",
            self.modpath,
            " (references: %s)"%references if references is not "" else "",
            " (referenced by: %s)"%referenced_by if referenced_by is not "" else "",
            " %s"%fmt_bytes(self.filesize) if not self.broken else "")
    def sortorder(self,other):
        # don't override __cmp__ because we want to be hashable
        assert isinstance(other,File)
        if other.typ == self.typ:
            return -cmp(other.path,self.path)
        return -cmp(other.typ,self.typ)

class Files:
    def __init__(self,mod):
        self.mod = mod
        self.files = {}
        self.ignored = set()
        self.typ = {}
    def ref(self,typ,path,referenced_by,ref_info):
        assert isinstance(referenced_by,File)
        f = self.add(typ,path)
        f.referenced_by.add(referenced_by)
        if f not in referenced_by.references:
            referenced_by.references[f] = []
        referenced_by.references[f].append(ref_info)
        return f
    def realpath(self,path):
        assert os.path.isabs(path)
        rel = os.path.relpath(path,self.mod.base_folder)
        assert not rel.startswith(".."),path
        if not os.path.isfile(path):
            found = self.mod.base_folder
            while True:
                remaining = path[len(found)+1:]
                if remaining == "":
                    path = found # success
                    break
                split = remaining.find("/")
                if -1 == split:
                    split = remaining.find("\\")
                if -1 == split:
                    split = len(remaining)
                part = remaining[:split].lower()
                candidate = None
                for f in os.listdir(found):
                    if f.lower() == part:
                        assert candidate is None,("AMBIGUOUS PATH!",path,found,f)
                        candidate = f
                if candidate is None:
                    break
                found = os.path.join(found,candidate)
        return path.replace("\\","/")
    def get(self,typ,path):
        path = path.lower()
        if path in self.files:
            f = self.files[path]
            assert f.typ == typ,"Expecting "+path+" to be of type "+typ+", but it is a "+f.typ
            return f
    def add(self,typ,path):
        path = path.replace("\\","/")
        f = self.get(typ,path)
        if f is None:
            f = self.files[path.lower()] = File(self.mod,typ,self.realpath(path))
        if typ not in self.typ:
            self.typ[typ] = set()
        self.typ[typ].add(f)
        return f
        
class FilterExt:
    def __init__(self,*ext):
        assert len(ext) > 0
        self.ext = ext
    def __call__(self,f):
        ext = os.path.splitext(f)[1].lower()
        return ext in self.ext
        
def parse_mod_name(name):
    modname = []
    ver = []
    for i,part in enumerate(name.split(".")):
        if part.isdigit():
            if (len(modname)==0) or not isinstance(modname[-1],(str,unicode)):
                return
            ver.append(int(part))
        else:
            if part.strip() == "":
                return
            elif (len(modname) != 0):
                if (len(ver) == 0) or not isinstance(modname[-1],str):
                    return
            if len(ver) > 0:
                modname.append(tuple(ver))
            ver = []
            modname.append(part)
    if (len(modname)==0) or (len(ver)==0):
        return
    modname.append(tuple(ver))
    return modname
    
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
                    
def query(prompt,*choices):
    prompt = "\n%s (%s): "%(prompt,", ".join(c[0] for c in choices))
    while True:
        ch = raw_input(prompt)
        if ch:
            ch = ch.lower()
            for c in choices:
                if ch in c[1].lower():
                    return c[1].lower()[0]
        print "Please answer the question!"

class Mod:
    def __init__(self,base_folder,external):
        self.base_folder = base_folder
        self.external = external
        if not os.path.isdir(self.base_folder):
            sys.exit("Error! mod folder does not exist")
        self.name = parse_mod_name(os.path.split(self.base_folder)[1])
        if self.name is None:
            print help_modname
            if not confirm("would you like to continue just to check your content anyway?"):
                sys.exit(1)
            self.name = (os.path.split(self.base_folder)[1],"1")
            self.is_extension = True
            self.bad_name = True
        else:
            part = []
            for x in xrange(len(self.name),0,-2):
                part.append("%s %s"%(self.name[x-2],".".join(str(v) for v in self.name[x-1])))
            print "=== Mod"," extends ".join(part),"==="
            self.is_extension = (len(self.name) > 2)
            self.bad_name = False
        self.maps = set()
        self.scenarios = set()
        self.factions = set()
        self.tilesets = set()
        self.tech_trees = set()
        self.external = {}
        self.files = Files(self)
        self.broken = {}
        self.broken_msg = []
        self._init_tech_trees()
        self._init_maps()
        self._init_tilesets()
        self._init_scenarios()
        self._init_ignored()
        if not self.is_extension:
            if len(self.tech_trees) == 0:
                print "Error! mod does not contain any tech-trees!"
                sys.exit(1)
            if len(self.factions) == 0:
                print "Error! mod does not contain any factions!"
                sys.exit(1)
    def _init_maps(self):
        for f in self._listdir("maps",os.path.isfile,FilterExt(".mgm",".gbm")):
            self.files.add(File.MAP,f)
            self.maps.add(os.path.splitext(os.path.split(f)[1])[0])
    def _init_tilesets(self):
        for f in self._listdir("tilesets",os.path.isdir):
            name = os.path.split(f)[1]
            self.tilesets.add(name)
            f = os.path.join(f,"%s.xml"%name)
            f = self.files.add(File.TILESET,f)
            assert f.broken or (f.xml.documentElement.tagName == "tileset"), f
    def _init_tech_trees(self):
        for f in self._listdir("techs",os.path.isdir):
            name = os.path.split(f)[1]
            self.tech_trees.add(name)
            f = self.files.realpath(os.path.join(f,"%s.xml"%name))
            if self.is_extension:
                if os.path.exists(f):
                    self.broken_msg.append("an extension should not contain "+f)
            else:
                self.files.add(File.TECH_TREE,f)
            for f in self._listdir("techs/%s/factions"%name,os.path.isdir):
                self._init_faction(f)
            for f in self._listdir("techs/%s/resources"%name,os.path.isdir):
                self._init_resource(f)
    def _init_faction(self,f):
        name = os.path.split(f)[1]
        self.factions.add(name)
        self.files.add(File.FACTION,os.path.join(f,"%s.xml"%name))
        for unit in self._listdir(os.path.join(f,"units"),os.path.isdir):
            self._init_unit(unit)
        for upgrade in self._listdir(os.path.join(f,"upgrades"),os.path.isdir):
            self._init_upgrade(upgrade)
    def _init_xml(self,f):
        if hasattr(f,"inited") and f.inited:
            return
        f.inited = True
        if not os.path.isfile(f.path):
            return
        f.xml = xml = minidom.parse(f.path)
        f.xml_ref = {}
        def extract(x,typ):
            path = None
            if x.hasAttribute("value") and x.getAttribute("value") != "true":
                return
            if x.hasAttribute("enabled") and x.getAttribute("enabled") != "true":
                return
            r = None
            if x.hasAttribute("path"):
                r = self.files.ref(typ,f.subpath(x.getAttribute("path")),f,x)
            elif (typ == File.TEXTURE) and x.hasAttribute("image-path"):
                r = self.files.ref(typ,f.subpath(x.getAttribute("image-path")),f,x)
            if r is not None:
                if r not in f.xml_ref:
                    f.xml_ref[r] = []
                f.xml_ref[r].append(x)
                return r
        for sound in chain(xml.getElementsByTagName("sound"),
            xml.getElementsByTagName("music"),
            xml.getElementsByTagName("sound-file")):
            extract(sound,File.SOUND)
        for image in chain(xml.getElementsByTagName("image"),
            xml.getElementsByTagName("texture"),
            xml.getElementsByTagName("image-cancel")):
            extract(image,File.TEXTURE)
        for image in xml.getElementsByTagName("meeting-point"):
            extract(image,File.TEXTURE)
        for model in chain(xml.getElementsByTagName("animation"),
            xml.getElementsByTagName("model")):
            model = extract(model,File.MODEL)
            if model is not None:
                self._init_model(model)
        for particle in chain(xml.getElementsByTagName("particle"),
            xml.getElementsByTagName("particle-file")):
            particle = extract(particle,File.PARTICLE)
            if particle is not None:
                self._init_particle(particle)
        for sound in xml.getElementsByTagName("ambient-sounds"):
            for sound in [c for c in sound.childNodes if c.nodeType == c.ELEMENT_NODE]:
                extract(sound,File.SOUND)
        return xml
    def _init_unit(self,f):
        name = os.path.split(f)[1]
        f = self.files.add(File.UNIT,os.path.join(f,"%s.xml"%name))
        f.name = name
        if f.broken: return
        xml = f.xml
        assert xml.documentElement.tagName == "unit", f
        for unit in chain(xml.documentElement.getElementsByTagName("unit"),
            xml.documentElement.getElementsByTagName("produced-unit")):
            unit = unit.attributes["name"].value
            self.files.ref(File.UNIT,f.subpath("../%s/%s.xml"%(unit,unit)),f,unit)
        return f
    def _init_upgrade(self,f):
        name = os.path.split(f)[1]
        f = self.files.add(File.UPGRADE,os.path.join(f,"%s.xml"%name))
        f.name = name
        assert f.broken or (f.xml.documentElement.tagName == "upgrade"), f
    def _init_resource(self,f):
        name = os.path.split(f)[1]
        f = self.files.add(File.RESOURCE,os.path.join(f,"%s.xml"%name))
        f.name = name
        assert f.broken or (f.xml.documentElement.tagName == "resource"), f
    def _init_particle(self,f):
        assert f.broken or (f.xml.documentElement.tagName.endswith("-particle-system")),"%s %s"%(f,f.xml.documentElement.tagName)
    def _init_scenarios(self):
        for f in self._listdir("scenarios",os.path.isdir):
            name = os.path.split(f)[1]
            self.scenarios.add(name)
            f = os.path.join(f,"%s.xml"%name)
            f = self.files.add(File.SCENARIO,f)
            if f.broken: continue
            xml = f.xml
            assert xml.documentElement.tagName == "scenario", f
            factions = set()
            for player in xml.getElementsByTagName("player"):
                try:
                    if player.attributes["control"].value != "closed":
                        factions.add(player.attributes["faction"].value)
                except Exception,e:
                    print player.toxml(),e
            def unresolved(f,typ,name):
                if self.is_extension:
                    if typ not in self.external:
                        self.external[typ] = []
                    self.external[typ].append(name)
                else:
                    f.error("References missing "+typ+" "+name)
            for faction in factions.difference(self.factions):
                unresolved(f,File.FACTION,faction)
            for m in xml.getElementsByTagName("map"):
                m = m.attributes["value"].value
                if m not in self.maps:
                    unresolved(f,File.MAP,m)
            for tileset in xml.getElementsByTagName("tileset"):
                tileset = tileset.attributes["value"].value
                if tileset not in self.tilesets:
                    unresolved(f,File.TILESET,tileset)
            for tech_tree in xml.getElementsByTagName("tech-tree"):
                tech_tree = tech_tree.attributes["value"].value
                if tech_tree not in self.tech_trees:
                    unresolved(f,File.TECH_TREE,tech_tree)
            for lng in self._listdir("scenarios/%s"%name,os.path.isfile,FilterExt(".lng")):
                if os.path.split(lng)[1].startswith(name):
                    self.files.add(File.LANGUAGE,lng)
    def _init_model(self,model):
        if model.inited:
            return
        model.inited = True
        try:
            f = open(model.path,"rb")
            if not f.read(3) == "G3D":
                model.error("not a valid G3D model")
                return
            ver = ord(f.read(1))
            def uint16():
                return unpack("<H",f.read(2))[0]
            def uint32():
                return unpack("<L",f.read(4))[0]
            if ver == 3:
                meshCount = uint32()
                for mesh in xrange(meshCount):
                    vertexFrameCount = uint32()
                    normalFrameCount = uint32()
                    texCoordFrameCount = uint32()
                    colorFrameCount = uint32()
                    pointCount = uint32()
                    indexCount = uint32()
                    properties = uint32()
                    texture = f.read(64)
                    has_texture = 0 == (properties & 1)
                    if has_texture:
                        texture = texture[:texture.find('\0')]
                        self.files.ref(File.TEXTURE,model.subpath(texture),model,f.tell()-64)
                    f.read(12*vertexFrameCount*pointCount)
                    f.read(12*vertexFrameCount*pointCount)
                    if has_texture:
                        f.read(8*texCoordFrameCount*pointCount)
                    f.read(16)
                    f.read(16*(colorFrameCount-1))
                    f.read(4*indexCount)
            elif ver == 4:
                meshCount = uint16()
                if ord(f.read(1)) != 0:
                    model.error("not mtMorphMesh!")
                    return
                for mesh in xrange(meshCount):
                    f.read(64) # meshName
                    frameCount = uint32()
                    vertexCount = uint32()
                    indexCount = uint32()
                    f.read(8*4)
                    properties = uint32()
                    textures = uint32()
                    for t in xrange(5):
                        if ((1 << t) & textures) != 0:
                            texture = f.read(64)
                            texture = texture[:texture.find('\0')]
                            self.files.ref(File.TEXTURE,model.subpath(texture),model,f.tell()-64)
                    f.read(12*frameCount*vertexCount*2)
                    if textures != 0:
                        f.read(8*vertexCount)
                    f.read(4*indexCount)
            else:
                model.error("Unsupported G3D version"+ver)
        except Exception,e:
            model.error("Error reading G3D file",e)
    def _listdir(self,path,*filters):
        path = os.path.join(self.base_folder,path)
        try:
            return [f for f in map(lambda x: os.path.join(path,x),os.listdir(path)) if all([ftr(f) for ftr in filters])]
        except OSError,e:
            if e.errno == 2: # file not found
                return []
            raise
    def _init_ignored(self):
        for folder in ["scenarios","techs","maps","tilesets"]:
            for folder in os.walk(os.path.join(self.base_folder,folder)):
                for f in folder[2]:
                    f = os.path.join(folder[0],f)
                    if f.lower() not in self.files.files:
                        self.files.ignored.add(f)
    def optimise(self):
        removed = 0
        # index by size
        by_size = {}
        for f in self.files.files.values():
            if f.broken: continue
            if hasattr(f,"xml"): continue
            if len(f.referenced_by) == 0: continue
            if f.filesize not in by_size:
                by_size[f.filesize] = set()
            by_size[f.filesize].add(f)
        # look for dups
        dups = set()
        for k,v in by_size.iteritems():
            if len(v) == 1: continue
            v = sorted(v,lambda x,y: len(x.modpath)-len(y.modpath)) # assume shorter path means shorter relative path
            assert len(v[0].modpath) <= len(v[1].modpath)
            for i,f in enumerate(v):
                if f not in dups:
                    for j in xrange(i+1,len(v)):
                        candidate = v[j]
                        if 0 == cmp(f.get_bytes(),candidate.get_bytes()):
                            candidate.dup = f
                            dups.add(candidate)
                del f._bytes
        errors = set()
        for d in dups:
            error = False
            print "Removing duplicate",d.modpath,fmt_bytes(d.filesize),"->",d.dup.modpath
            for referrer in d.referenced_by:
                relpath = os.path.relpath(d.dup.modpath,os.path.split(referrer.modpath)[0]).replace("\\","/")
                for r in relpath:
                    if r not in legal_path_chars:
                        errors.add("%s contains illegal characters"%relpath)
                        error = True
                        break
                if error:
                    continue
                if referrer.path.endswith(".g3d"):
                    relpath = buffer(relpath.encode("utf-8"))
                    if len(relpath) > 64:
                        error = True
                        errors.add("Error! cannot remap %s -> %s in %s because the relative path is too long (g3d paths cannot be longer than 64 bytes)"%\
                            (d.modpath,relpath,referrer.modpath))
                        continue
                    g3d = referrer.g3d_body()
                for r in referrer.references[d]:
                    if hasattr(referrer,"xml"):
                        if r.hasAttribute("path"):
                            r.setAttribute("path",relpath)
                        elif r.hasAttribute("image-path"):
                            r.setAttribute("image-path",relpath)
                        else:
                            errors.append("Error! Could not find reference to %s in %s %s"%\
                                (d.modpath,referrer.modpath,r.toxml()))
                    else:
                        for i in xrange(64):
                            if i < len(relpath):
                                g3d[r+i] = relpath[i]
                            else:
                                g3d[r+i] = 0
            if not error:
                del self.files.files[d.path.lower()]
                removed += d.filesize
        if len(errors) > 0:
            print "\n*** The following errors occurred whilst optimising: ***"
            for e in errors: print e
            print "*** Please report these errors in the forum! ***\n"
        return removed
    def manifest(self):
        if not hasattr(self,"_manifest"):
          self._manifest = """"
<?xml version="1.0" standalone="no"?>
<glest-mod-manifest>
    <!-- packed with glest_mod_pack.py by Will -->
    <pack-fmt value="0.1"/>
    <!-- description of mod to go here for tools to parse -->
</glest-mod-manifest>
"""
        return self._manifest
                        
def fmt_bytes(b):
    for m in ["B","KB","MB","GB"]:
        if b < 1024:
            return "%1.1f %s"%(b,m)
        b /= 1024.
        
def sum_type(mod,typ):
    if typ in mod.files.typ:
       label = string.capitalize(typ)
       typ = mod.files.typ[typ]
       print "=== %ss:"%label,len(typ),fmt_bytes(sum(f.filesize for f in typ)),"==="
            
def main(argv):
    if len(argv) == 1:
        print help_modname
        while True:
            path = raw_input("Please enter the path to your mod: ")
            if path in [None,False,""]:
                sys.exit("You have not specified your path")
            if os.path.isdir(path):
                argv = (argv[0],path)
                break
            print path,"does not exist or is not a folder"
    if len(argv) != 2:
        print "Usage: python",argv[0],"[mod_root_dir]"
        print help_modname
        sys.exit(1)
    time_start = time.time()
    
    # make a list of all known mods
    base_folder = os.path.abspath(argv[1])
    root_folder = os.path.split(base_folder)[0]
    print "Analysing",base_folder,"if this is a big mod, you might want to go get a coffee..."
    mods = []
    for mod in os.listdir(root_folder):
        path = os.path.join(root_folder,mod)
        if os.path.isfile(path):
            if os.path.splitext(mod)[1] in [".zip",".zip.xy"]:
                mod = os.path.splitext(mod)[0]
            else:
                continue
        elif not os.path.isdir(path):
            continue
        m = parse_mod_name(mod)
        if m is not None:
            mods.append((path,m))

    # parse the mod
    mod = Mod(base_folder,mods)
    included = 0
    include_count = 0
    for f in sorted(mod.files.files.values(),lambda x,y: x.sortorder(y)):
        if f.broken:
            continue
        include_count += 1
        included += f.filesize
        print "Including",f.modpath,fmt_bytes(f.filesize)
    if len(mod.files.ignored) > 0:
        ignored = 0
        print "=== The following",len(mod.files.ignored),"files are ignored ==="
        for f in sorted(mod.files.ignored):
            try:
                filesize = os.path.getsize(f)
                ignored += filesize
                filesize = fmt_bytes(os.path.getsize(f))
            except:
                filesize = "(no size!)"
            print "Ignoring",os.path.relpath(f,mod.base_folder),filesize
        print "=== Ignored:",len(mod.files.ignored),fmt_bytes(ignored),"==="
    time_stop = time.time()
    print "=== (Analysis took %0.1f seconds) =="%(time_stop-time_start)
    print "=== Included:",include_count,fmt_bytes(included),"==="
    sum_type(mod,File.MODEL)
    sum_type(mod,File.TEXTURE)
    sum_type(mod,File.PARTICLE)
    sum_type(mod,File.SOUND)
    sum_type(mod,File.UNIT)
    sum_type(mod,File.UPGRADE)
    sum_type(mod,File.RESOURCE)
    sum_type(mod,File.LANGUAGE)
    if len(mod.factions) > 0:
        print "=== Fractions:",", ".join(mod.factions),"==="
    if len(mod.maps) > 0:
        print "=== Maps:",", ".join(mod.maps),"==="
    if len(mod.tilesets) > 0:
        print "=== Tile Sets:",", ".join(mod.tilesets),"==="
    if len(mod.tech_trees) > 0:
        print "=== Tech Trees:",", ".join(mod.tech_trees),"==="
    if len(mod.scenarios) > 0:
        print "=== Scenarios:",", ".join(mod.scenarios),"==="
    if len(mod.external) > 0:
        print "=== Dependencies: ==="
        for k,v in mod.external.items():
            print k,v
    if (len(mod.broken) > 0) or (len(mod.broken_msg) > 0):
        print "=== Mod check failed ==="
        for f,reason in sorted(mod.broken.items(),lambda x,y: x[0].sortorder(y[0])):
            try:
                print f,", ".join(str(r) for r in reason)
            except Exception,e:
                print "ERROR",f
                print "REASON",reason
                raise
        for msg in mod.broken_msg:
            print msg
        if not confirm("Mod contains errors: do you want to package it up anyway?"):
            sys.exit(1)
    print """
This tool has some experimental optimisations:
* Duplicate files are, where possible, removed and all references to them
  rewired to point to the same content in another file.
  Inside the zip file, the G3D and XML files that reference the file are
  rewritten but NO CHANGES ARE MADE to the files on your disk!
  If you later choose Zip compression, then users get a much smaller download.
  If you chose XY compression, then players use less diskspace when they've
  uncompressed your mod, so its seems always a good idea..."""
    optimise = confirm("Should we perform some (experimental!) optimisations?")
    if optimise:
        time_start = time.time()
        saved = mod.optimise()
        time_stop = time.time()
        print "=== (Optimisation took %0.1f seconds to save %s) =="%((time_stop-time_start),fmt_bytes(saved))
    print """
There are two formats for packaging mods, and these choices affect file size:
* ZIP compression is very portable, and suitable even for Classic Glest users
  ZIP files will also take less space on GAE players harddisks
* XY offers smaller downloads, but GAE users will use as much diskspace
  as MG and Classic Glest users.  XY is intended to be used eventually by the
  automated mod managing tools (which I plan to write).
  It offers better partial-update download sizes too, if you are making an
  upgrade of an existing mod.  Power users will be able to use these files
  manually, but most Classic Glest players will be unsure what to do with them!
  (XY takes a lot longer to pack, so if you are impatient go with ZIP)"""
    fmt = query("What compression choice do you want to use?",("z=zip","z"),("x=xy","x"))
    out_filename = os.path.abspath(os.path.join(mod.base_folder,"../%s.zip"%os.path.split(mod.base_folder)[1]))
    if os.path.exists(out_filename) and \
        not confirm("The file %s already exists; proceeding will re-create it; are you sure?"%out_filename):
        sys.exit(1)
    time_start = time.time()
    try:
        if (fmt == "z"): # zip
            archive = zipfile.ZipFile(out_filename,"w",zipfile.ZIP_DEFLATED)
            print
            print "Compressing mod using zip, please wait... (go get more coffee!)"
        elif (fmt == "x"): #xy
            archive = zipfile.ZipFile(out_filename,"w",zipfile.ZIP_STORED)
            print "Stage 1: storing all files in a zip..."
        else:
            assert False,"unexpected choice: %s"%fmt
        included = 0
        for f in sorted(mod.files.files.values(),lambda x,y: x.sortorder(y)):
            if not os.path.isfile(f.path):
                continue
            if optimise:
                bytes = f.optimised_body()
                if bytes is not None:
                    print "Rewriting",f.modpath
                    archive.writestr(f.modpath,bytes)
                    included += len(bytes)
                    continue
            included += f.filesize
            archive.write(f.path,f.modpath)
        archive.comment = mod.manifest()
        archive.close()
        if (fmt == "x"):
            print "Stage 2: compressing with xz... (go get more coffee!)"
            target_filename = out_filename+".xz"
            if os.path.exists(target_filename):
                time_stop = time.time()-time_start
                if not confirm("The file %s already exists; proceeding will re-create it; are you sure?"%target_filename):
                    sys.exit(1)
                time_start = time.time()-time_stop
                os.unlink(target_filename)
            if 0 != os.system("xz -e -9 %s"%out_filename):
                raise Exception("Error compressing with xz")
            out_filename = target_filename
    except:
        try: os.unlink(out_filename)
        except: pass
        raise
    mod_size = os.path.getsize(out_filename)
    time_stop = time.time()
    print "=== (Packaging took %0.1f seconds) =="%(time_stop-time_start)
    print fmt_bytes(included),"compressed to",fmt_bytes(mod_size),\
        "(%1.1f%%)"%((float(mod_size)/float(included))*100.),"->",out_filename
    print "=== deltas are not yet supported ==="
    
if __name__ == "__main__":
    print "Glest/MG/GAE mod-packer by Will"
    error = True
    try:
        main(sys.argv)
        print "== DONE =="
        error = False
    except KeyboardInterrupt:
        print "\naborting!"
        os._exit(1)
    except SystemExit,se:
        if se.code != 1:
            print "Error:",se.code
    except Exception,e:
        print "An error has occurred:"
        import traceback
        traceback.print_exc()
    try: raw_input(" Press [enter] to continue... ")
    except: print " You really want to leave!"
    if error:
        sys.exit(1)
