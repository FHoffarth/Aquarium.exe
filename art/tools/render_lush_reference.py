"""One offline art-direction candidate; never writes into habitat/.

node art/tools/export_offline_fish.mjs
blender -b --factory-startup -P art/tools/render_lush_reference.py
"""
import bpy, math, random, pathlib, json, os
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = ROOT / 'art/work/lush-reference'
OUT = ROOT / 'docs/evidence/lush-reference'
TEXTURES = ROOT / 'habitat/assets/slice-c/textures'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(260927)
PREVIEW = os.environ.get('LUSH_PREVIEW') == '1'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

def material(name, color, rough=.5, metal=0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value = (*color, 1)
    p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    return m

def leaf_material(name, color):
    m = material(name, color, .46)
    n, l = m.node_tree.nodes, m.node_tree.links
    p = n.get('Principled BSDF')
    p.inputs['Subsurface Weight'].default_value = .035
    noise = n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 65
    noise.inputs['Detail'].default_value = 3
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .15
    ramp.color_ramp.elements[0].color = tuple(c*.46 for c in color)+(1,)
    ramp.color_ramp.elements[1].position = .85
    ramp.color_ramp.elements[1].color = tuple(min(.85,c*1.05) for c in color)+(1,)
    l.new(noise.outputs['Fac'], ramp.inputs[0]); l.new(ramp.outputs[0],p.inputs['Base Color'])
    bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .13
    bump.inputs['Distance'].default_value = .035
    l.new(noise.outputs['Fac'], bump.inputs['Height']); l.new(bump.outputs[0],p.inputs['Normal'])
    return m

greens = []
for depth in range(3):
    for c in [(0.055,.26,.014),(.11,.33,.018),(.045,.19,.012),(.16,.30,.025),(.052,.25,.03),(.10,.23,.012)]:
        c = (c[0]*.62,c[1]*.82,c[2]*.64)
        if depth == 2: c = (c[0]*.55,c[1]*.55,c[2]+.025)
        if depth == 1: c = (c[0]*.8,c[1]*.8,c[2]+.006)
        greens.append(leaf_material(f'leaf-{depth}-{len(greens)}',c))
stemmat = material('living green stems',(.09,.22,.025),.6)
leaf_atlas=leaf_material('photographed broad leaf surfaces',(.07,.31,.025))
leaf_image=bpy.data.images.load(str(TEXTURES/'leaves_albedo.webp'))
leaf_image.pack()
leaf_node=leaf_atlas.node_tree.nodes.new('ShaderNodeTexImage');leaf_node.image=leaf_image
leaf_bw=leaf_atlas.node_tree.nodes.new('ShaderNodeRGBToBW')
leaf_atlas.node_tree.links.new(leaf_node.outputs['Color'],leaf_bw.inputs[0])
leaf_grade=leaf_atlas.node_tree.nodes.new('ShaderNodeHueSaturation')
leaf_grade.inputs['Saturation'].default_value=1.25
leaf_grade.inputs['Value'].default_value=2.0
leaf_atlas.node_tree.links.new(leaf_node.outputs['Color'],leaf_grade.inputs['Color'])
leaf_atlas.node_tree.links.new(leaf_grade.outputs['Color'],
    leaf_atlas.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
leaf_bump=next(node for node in leaf_atlas.node_tree.nodes if node.type=='BUMP')
leaf_bump.inputs['Strength'].default_value=.24
leaf_bump.inputs['Distance'].default_value=.045
leaf_atlas.node_tree.links.new(leaf_bw.outputs[0],leaf_bump.inputs['Height'])
ambermats=[leaf_material('rust accent stems',(.26,.115,.018)),
           leaf_material('golden olive accent stems',(.19,.22,.024))]
leaf_profiles=json.loads((ROOT/'art/tools/lush_leaf_profiles.json').read_text())

class Mesh:
    def __init__(self,name): self.name=name; self.v=[]; self.f=[]; self.mi=[]; self.uv=[]
    def face(self, pts, mi=0):
        start=len(self.v); self.v.extend(pts);self.uv.extend([(0,0)]*len(pts))
        self.f.append(tuple(range(start,start+len(pts)))); self.mi.append(mi)
    def leaf(self,base, direction,length,width,mi, bend=.2,twist=0,segments=7,shape='lance',atlas=False):
        base=Vector(base); axis=Vector(direction).normalized()
        side=axis.cross(Vector((0,-1,.2))).normalized()
        if side.length < .1: side=Vector((1,0,0))
        normal=axis.cross(side).normalized(); start=len(self.v)
        tile=rng.randrange(6) if atlas else 0
        for i in range(segments+1):
            t=i/segments
            center=base+axis*length*t+Vector((math.sin(t*3+twist)-math.sin(twist),0,-t*t))*bend
            if shape == 'grass':
                outline=min(1,t*10)*(max(0,1-t**1.7)**.68)
            elif shape == 'broad':
                outline=(math.sin(math.pi*t)**.88)*(.68+.62*t)
            elif shape == 'needle':
                outline=math.sin(math.pi*t)**.46
            else:
                outline=math.sin(math.pi*t)**.72
            span=width*outline*(.92+.08*math.sin(t*17+twist))
            for u in [-1,0,1]:
                p=center+side*(span*u)+normal*(span*.18*(1-abs(u)))
                p+=normal*(span*u*math.sin(t*5+twist)*.24)
                self.v.append(tuple(p))
                if atlas:
                    self.uv.append(((tile%3+.075+(u+1)*.425)/3,
                                    (tile//3+.06+t*.88)/2))
                else:self.uv.append(((u+1)*.5,t))
        for i in range(segments):
            for j in range(2):
                a=start+i*3+j
                self.f.append((a,a+1,a+4,a+3));self.mi.append(mi)
    def photo_leaf(self,base,direction,length,profile,twist,arch,curl):
        base=Vector(base);axis=Vector(direction).normalized()
        side=axis.cross(Vector((0,-1,.5))).normalized()
        normal=side.cross(axis).normalized();start=len(self.v)
        rows=profile['rows']
        for row in rows:
            t=row['t'];span=row['half_width']*length
            side_t=side*math.cos(twist*t)+normal*math.sin(twist*t)
            fold=normal*span*.16
            center=base+axis*length*t-normal*(arch*length*t*t)+side*(curl*length*t*t)
            for j,u in enumerate([-1,0,1]):
                self.v.append(tuple(center+side_t*span*u+fold*(1-abs(u))))
                self.uv.append(tuple(row['uv'][j]))
        for i in range(len(rows)-1):
            for j in range(2):
                a=start+i*3+j
                self.f.append((a,a+1,a+4,a+3));self.mi.append(18)
    def tube(self,pts,radius,mi=0):
        start=len(self.v); sides=5
        for i,p in enumerate(pts):
            for j in range(sides):
                a=j*math.tau/sides; r=radius*(1-i/(len(pts)+.5)*.75)
                self.v.append((p[0]+r*math.cos(a),p[1]+r*math.sin(a),p[2]))
                self.uv.append((0,0))
        for i in range(len(pts)-1):
            for j in range(sides):
                a=start+i*sides+j;b=start+i*sides+(j+1)%sides
                self.f.append((a,b,b+sides,a+sides));self.mi.append(mi)
    def finish(self,mats):
        mesh=bpy.data.meshes.new(self.name);mesh.from_pydata(self.v,[],self.f);mesh.update()
        obj=bpy.data.objects.new(self.name,mesh);bpy.context.collection.objects.link(obj)
        for mat in mats: mesh.materials.append(mat)
        for p,mi in zip(mesh.polygons,self.mi):p.material_index=mi;p.use_smooth=True
        if len(self.uv)==len(self.v):
            layer=mesh.uv_layers.new()
            for loop in mesh.loops:layer.data[loop.index].uv=self.uv[loop.vertex_index]
        return obj

ribbon=Mesh('01 flowing ribbon plants'); grass=Mesh('02 tall grass'); feather=Mesh('03 fine feather plants')
stems=Mesh('04 medium stems'); bush=Mesh('05 irregular small leaf bushes')
broad=Mesh('06 broad leaves'); low=Mesh('07 low foreground plants'); stalk=Mesh('supporting stems')

def ribbon_clump(x,y,h,n):
    depth=2 if y>2 else 1
    for j in range(n):
        a=rng.uniform(0,math.tau)
        ribbon.leaf((x+rng.gauss(0,.16),y+rng.gauss(0,.1),.12),
            (math.cos(a)*rng.uniform(.18,.7),math.sin(a)*.28,1),h*rng.uniform(.58,1.16),
            rng.uniform(.085,.17),depth*6+rng.randrange(6),rng.uniform(.55,1.25),rng.uniform(-3,3),17)

for x,y,h,n in [(-6.0,2.3,4.8,8),(-5.1,2.6,5.9,11),(-3.8,3.0,5.1,7),
                 (-1.65,3.4,3.7,5),(2.8,3.2,4.5,7),(4.1,2.9,5.7,12),(5.45,2.6,5.3,9),(6.2,2.2,4.4,6)]:
    ribbon_clump(x,y,h,n)

def tall_grass(x,y,h,n):
    for j in range(n):
        a=rng.uniform(0,math.tau)
        grass.leaf((x+rng.gauss(0,.12),y+rng.gauss(0,.1),.12),
            (math.cos(a)*rng.uniform(.05,.38),math.sin(a)*.16,1),h*rng.uniform(.54,1.22),
            rng.uniform(.016,.052),rng.randrange(6,18),rng.uniform(.3,.9),a,13,'grass')

for x,y,h,n in [(-5.9,1.0,3.8,18),(-4.65,2.3,4.9,21),(-2.9,3.05,4.3,16),
                (1.9,3.25,3.3,13),(3.6,2.6,4.6,17),(5.5,1.5,5.0,19)]:
    tall_grass(x,y,h,n)

def feather_spray(x,y,h):
    phase=rng.random()*math.tau
    spine=[]
    for k in range(11):
        t=k/10; p=Vector((x+math.sin(t*4+phase)*.18,y+math.cos(t*3+phase)*.12,.16+h*t));spine.append(p)
        if k<2:continue
        for side in [-1,1]:
            a=phase+t*2.1+side*1.35
            branch=Vector((math.cos(a),math.sin(a)*.72,.44)).normalized()
            bl=h*.18*(1-t*.55)*rng.uniform(.72,1.28)
            for b in range(6):
                u=(b+.5)/6; base=p+branch*bl*u
                off=Vector((-branch.y,branch.x,rng.uniform(-.1,.2)))
                for sign in [-1,1]:
                    feather.leaf(base,branch*.28+off*sign,bl*.24,rng.uniform(.012,.024),
                        12+rng.randrange(6),.004,a,3,'needle')
    stalk.tube(spine,.008)

for cx,cy,h,n in [(-4.15,2.5,4.5,18),(-2.05,3.25,3.55,11),(.15,3.5,3.1,8),
                  (3.45,2.9,4.1,13),(5.0,3.1,4.6,16)]:
    for i in range(n):feather_spray(cx+rng.gauss(0,.38),cy+rng.gauss(0,.2),h*rng.uniform(.62,1.17))

def stem_plant(x,y,h,depth=1,amber=False):
    phase=rng.random()*math.tau; tilt=rng.uniform(-.36,.36);pts=[]
    for k in range(11):
        t=k/10;p=Vector((x+tilt*t+math.sin(t*3+phase)*.1,y+math.sin(t*4+phase)*.08,.12+h*t));pts.append(p)
        if k<2:continue
        for j in range(rng.randint(2,4)):
            a=j*math.tau/3+k*1.2+phase
            tint=(19+rng.randrange(2)) if amber and rng.random()<.64 else depth*6+rng.randrange(6)
            stems.leaf(p,(math.cos(a),math.sin(a)*.7,.48),rng.uniform(.16,.38)*(1-.25*t),
                rng.uniform(.028,.07),tint,.02,phase,5)
    stalk.tube(pts,.011)

for cx,cy,h,n in [(-5.25,1.75,3.8,18),(-2.75,2.5,3.1,19),(.6,3.2,2.5,9),
                  (2.55,2.6,3.2,13),(4.9,1.8,3.9,19)]:
    for i in range(n):stem_plant(cx+rng.gauss(0,.38),cy+rng.gauss(0,.24),h*rng.uniform(.7,1.13),2 if cy>2.4 else 1)
for cx,cy,h,n in [(-1.85,2.75,3.15,7),(3.0,2.85,2.9,5)]:
    for i in range(n):stem_plant(cx+rng.gauss(0,.22),cy+rng.gauss(0,.15),h*rng.uniform(.72,1.05),2,True)

def bush_mass(cx,cy,h,n):
    for i in range(n):
        x=cx+rng.gauss(0,.3);y=cy+rng.gauss(0,.2);height=h*rng.uniform(.55,1.25)
        tilt=rng.uniform(-.4,.4);pts=[]
        for k in range(rng.randint(6,9)):
            t=k/8;p=Vector((x+tilt*t,y+.11*math.sin(t*3+i),.13+t*height));pts.append(p)
            if k<2:continue
            for j in range(rng.randint(2,4)):
                a=j*2.2+k*1.8+i
                bush.leaf(p,(math.cos(a),math.sin(a),.3),rng.uniform(.11,.28),
                    rng.uniform(.035,.085),rng.randrange(6),.025,a,5)
        stalk.tube(pts,.009)

for x,y,h,n in [(-5.25,.3,2.4,13),(-3.4,.7,1.8,10),(-2.1,1.5,2.0,9),
                (.3,2.3,2.3,8),(2.65,1.6,2.05,9),(4.3,.45,2.45,13),(5.8,.45,1.8,9)]:
    bush_mass(x,y,h,n)

for cx,cy,h,n in [(-4.8,-.35,1.55,3),(-2.9,.3,1.5,2),(-1.8,1.15,1.45,2),
                  (-.35,.4,1.35,2),(2.45,.55,1.75,2),(4.15,-.2,2.0,2),(5.4,.45,1.35,2)]:
    for p in range(n):
        x=cx+rng.uniform(-.33,.33);y=cy+rng.uniform(-.2,.2)
        for j in range(rng.randint(5,8)):
            a=j*2.4+p;d=Vector((math.cos(a)*.6,math.sin(a)*.45,rng.uniform(.45,1)))
            broad.photo_leaf((x,y,.16),d,h*rng.uniform(.42,.78),rng.choice(leaf_profiles),
                             rng.uniform(-.42,.42),rng.uniform(.10,.3),rng.uniform(-.08,.08))

# Patchy foreground clusters frame open gravel rather than forming a hedge.
for cx,cy,n in [(-5.9,-1.15,8),(-5.15,-.7,4),(-4.05,-1.65,9),(-3.25,-.65,5),
                (-2.55,-1.35,6),(-1.35,-.55,3),(.1,-.45,4),(1.6,-1.6,6),
                (2.6,-.75,3),(3.8,-1.55,8),(4.8,-.7,5),(5.8,-1.25,7)]:
    for i in range(n):
        x=cx+rng.gauss(0,.2);y=cy+rng.gauss(0,.16)
        for j in range(rng.randint(3,8)):
            a=rng.random()*math.tau
            low.leaf((x,y,.07),(math.cos(a)*.85,math.sin(a)*.65,1),rng.uniform(.2,.62),
                rng.uniform(.015,.043),rng.randrange(6),.11,a,7,'grass')

for mesh in [ribbon,grass,feather,bush,broad,low]:mesh.finish(greens+[leaf_atlas])
stems.finish(greens+[leaf_atlas]+ambermats)
stalk.finish([stemmat])

# A gently raised bed carries the plants and makes the foreground read as a
# plane extending into the tank. Openings follow the irregular plant patches.
gravelmats=[material('gravel '+str(i),c,.87) for i,c in enumerate([
    (.105,.098,.078),(.18,.17,.14),(.075,.085,.08),(.235,.22,.18),(.14,.13,.11)])]
def floor_height(x,y):
    rise=.025+.08*math.sin(x*.72+y*.8)**2+.045*math.sin(x*2.2-y*1.3)**2
    rise+=.09*math.exp(-((x-1.25)**2/4+(y-.5)**2/1.5))
    return rise
floor=Mesh('undulating natural gravel bed')
nx,ny=70,45
for j in range(ny):
    y=-5+j*9.4/(ny-1)
    for i in range(nx):
        x=-7+i*14/(nx-1)
        floor.v.append((x,y,floor_height(x,y)))
for j in range(ny-1):
    for i in range(nx-1):
        a=j*nx+i;floor.f.append((a,a+1,a+1+nx,a+nx));floor.mi.append(0)
floor.finish([gravelmats[0]])
pebbles=Mesh('fine gravel openings')
for i in range(6500):
    x=rng.uniform(-6.8,6.8);y=rng.uniform(-4.8,3.8);z=floor_height(x,y);r=rng.uniform(.012,.042)
    pts=[(x+math.cos(j*math.tau/6)*r,y+math.sin(j*math.tau/6)*r*.8,z) for j in range(6)]
    top=(x+r*.15,y,r*.65+z)
    for j in range(6):pebbles.face([pts[j],pts[(j+1)%6],top],rng.randrange(5))
pebbles.finish(gravelmats)
larger_stones=Mesh('scattered embedded foreground gravel')
for i in range(90):
    x=rng.uniform(-6.5,6.5);y=rng.uniform(-4.2,.7)
    if -.5<x<1.6 and y>-.4 and rng.random()<.6:continue
    z=floor_height(x,y);r=rng.uniform(.045,.135)
    pts=[(x+math.cos(j*math.tau/7)*r*rng.uniform(.75,1.2),
          y+math.sin(j*math.tau/7)*r*.8*rng.uniform(.75,1.2),z-.015) for j in range(7)]
    top=(x+rng.uniform(-.25,.25)*r,y,z+r*rng.uniform(.3,.62))
    for j in range(7):larger_stones.face([pts[j],pts[(j+1)%7],top],rng.randrange(5))
larger_stones.finish(gravelmats)
wood=material('rooted warm driftwood',(.115,.048,.019),.84)
wn=wood.node_tree.nodes;wl=wood.node_tree.links;tex=wn.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=7;tex.inputs['Detail'].default_value=4
bu=wn.new('ShaderNodeBump');bu.inputs['Strength'].default_value=.6;bu.inputs['Distance'].default_value=.12;wl.new(tex.outputs['Fac'],bu.inputs['Height']);wl.new(bu.outputs[0],wn.get('Principled BSDF').inputs['Normal'])
wood_image=bpy.data.images.load(str(TEXTURES/'wood_albedo.webp'));wood_image.pack()
wood_tex=wn.new('ShaderNodeTexImage');wood_tex.image=wood_image
wl.new(wood_tex.outputs['Color'],wn.get('Principled BSDF').inputs['Base Color'])
def branch(points,radii,name):
    # Cylindrical segments overlap at the bends; the base sinks into gravel.
    for i,(a,b) in enumerate(zip(points,points[1:])):
        a,b=Vector(a),Vector(b);direction=b-a
        bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=radii[i],radius2=radii[i+1],depth=direction.length,
            location=(a+b)*.5)
        obj=bpy.context.object;obj.name=name;obj.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
        obj.data.materials.append(wood)
        bevel=obj.modifiers.new('weathered rounded bark','BEVEL');bevel.width=.045;bevel.segments=2
        for p in obj.data.polygons:p.use_smooth=True
branch([(-1.7,.5,.05),(-.95,.62,.27),(-.15,.9,.42),(.65,1.0,.57),(1.55,1.25,.83)],
       [.24,.22,.18,.14,.07],'planted central wood')
branch([(-.9,.62,.25),(-1.5,.75,.72),(-2.4,1.0,1.18)], [.16,.11,.025],'left branch')
branch([(.45,1,.5),(.95,1.25,1.18),(1.65,1.55,1.48)], [.12,.08,.018],'right branch')

# Individual scanned rocks from the repo; the old Slice C arrangement is
# discarded. These stay low, irregular and partly buried beneath plants.
before=set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=str(ROOT/'habitat/assets/slice-c/environment.glb'))
imported=[ob for ob in bpy.data.objects if ob not in before]
rock_sources={}
for ob in imported:
    if ob.type!='MESH':continue
    name=next((key for key in ('rock-07','rock-09','boulder') if key in ob.name.lower()),None)
    if name is None:continue
    mesh=ob.data.copy();mesh.transform(ob.matrix_world)
    xs=[v.co.x for v in mesh.vertices];ys=[v.co.y for v in mesh.vertices];zs=[v.co.z for v in mesh.vertices]
    center=Vector(((min(xs)+max(xs))*.5,(min(ys)+max(ys))*.5,min(zs)))
    for v in mesh.vertices:v.co-=center
    rock_sources[name]=(mesh,max(zs)-min(zs))
for ob in imported:bpy.data.objects.remove(ob,do_unlink=True)
rockmats={}
for name,file in [('rock-07','rock07_albedo.webp'),('rock-09','rock09_albedo.webp'),('boulder','boulder_albedo.webp')]:
    mat=material('scanned stone '+name,(.15,.15,.13),.91)
    img=bpy.data.images.load(str(TEXTURES/file));img.pack()
    texnode=mat.node_tree.nodes.new('ShaderNodeTexImage');texnode.image=img
    mat.node_tree.links.new(texnode.outputs['Color'],mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
    rockmats[name]=mat
for x,y,h,name in [(-2.0,.7,.42,'rock-07'),(-.85,.25,.28,'rock-09'),
                   (.45,1.4,.46,'boulder'),(1.55,.85,.39,'rock-07')]:
    source,source_h=rock_sources[name]
    ob=bpy.data.objects.new('partly buried '+name,source.copy());bpy.context.collection.objects.link(ob)
    ob.data.materials.clear();ob.data.materials.append(rockmats[name])
    ob.location=(x,y,floor_height(x,y)-h*.19);ob.scale=(h/source_h,)*3
    ob.rotation_euler[2]=rng.uniform(-math.pi,math.pi)

# Luminous blue rear water is a backdrop, not a fog layer over the foreground.
back=bpy.data.materials.new('clear blue depth');back.use_nodes=True
n=back.node_tree.nodes;l=back.node_tree.links;n.clear()
o=n.new('ShaderNodeOutputMaterial');e=n.new('ShaderNodeEmission');tc=n.new('ShaderNodeTexCoord');s=n.new('ShaderNodeSeparateXYZ');r=n.new('ShaderNodeValToRGB')
r.color_ramp.elements[0].color=(.015,.055,.08,1);r.color_ramp.elements[1].color=(.18,.55,.72,1)
l.new(tc.outputs['Generated'],s.inputs[0]);l.new(s.outputs['Z'],r.inputs[0]);l.new(r.outputs[0],e.inputs[0]);l.new(e.outputs[0],o.inputs[0]);e.inputs[1].default_value=.8
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,4.8,3.4));obj=bpy.context.object;obj.name='blue water background';obj.scale=(17,.05,8);obj.data.materials.append(back)

# Exported production fish geometry, frozen only for this composition review.
fishdata=json.loads((WORK/'hero-fish.json').read_text())
def srgb_to_linear(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
def fish_texture(name,data,group):
    w,h=data['width'],data['height'];pixels=[]
    for y in range(h):
        for x in range(w):
            at=(y*w+x)*4;rgb=[srgb_to_linear(v/255) for v in data['pixels'][at:at+3]];alpha=data['pixels'][at+3]/255
            s=(x+.5)/w;surface=-math.cos((y+.5)/h*math.tau);flank=1-min(1,max(0,(abs(surface)-.48)/.46))
            lum=sum(a*b for a,b in zip(rgb,[.2126,.7152,.0722]))
            if name=='bodies' and group<2:
                tint=[.35,1.05,1.65] if group==0 else [2,.55,.12];amt=flank*(.65 if group==0 else .85)
                rgb=[a*(1-amt)+lum*b*amt for a,b in zip(rgb,tint)]
                if group==0:
                    red=min(1,max(0,(s-.55)/.2))*flank*.92
                    rgb=[a*(1-red)+lum*b*red for a,b in zip(rgb,[2,.10,.055])]
            if name=='membranes' and group<2:
                tint=[1.8,.08,.035] if group==0 else [2,.38,.055]
                rgb=[a*.15+max(.12,lum)*b*.85 for a,b in zip(rgb,tint)];alpha=min(.88,alpha*1.6)
            pixels.extend(rgb+[alpha])
    im=bpy.data.images.new(f'{name}-palette-{group}',width=w,height=h,alpha=True);im.pixels=pixels;im.pack()
    m=material(f'fish {name} {group}',(.7,.7,.7),.3,.48 if name=='bodies' else .05)
    n=m.node_tree.nodes;l=m.node_tree.links;p=n.get('Principled BSDF');t=n.new('ShaderNodeTexImage');t.image=im
    l.new(t.outputs['Color'],p.inputs['Base Color'])
    if name=='membranes':l.new(t.outputs['Alpha'],p.inputs['Alpha']);m.surface_render_method='DITHERED'
    p.inputs['Coat Weight'].default_value=.3
    return m
fishmats={(name,g):fish_texture(name,fishdata[name]['texture'],g) for name in fishdata for g in range(3)}
eye=material('fish pupil',(.003,.005,.006),.12);iris=material('fish silver iris',(.3,.25,.14),.25,.75)
fishposes=[(-3.8,-.9,3.2,1,0),(-2.4,-.6,3.8,1,1),(-.7,-.7,3.15,-1,0),(1.0,-.5,3.6,-1,1),(3.0,-.6,3.25,-1,2),
           (-1.4,-1.0,2.35,1,2),(.35,-1.0,2.65,1,0),(2.2,-.9,2.5,-1,1),(4.25,-.8,2.9,-1,0),(-.15,-.2,4.2,1,1)]
for i,(x,y,z,d,g) in enumerate(fishposes):
    for name,data in fishdata.items():
        vs=[(data['position'][j],-data['position'][j+2],data['position'][j+1]) for j in range(0,len(data['position']),3)]
        faces=[data['index'][j:j+3] for j in range(0,len(data['index']),3)]
        me=bpy.data.meshes.new(f'hero-{i}-{name}');me.from_pydata(vs,[],faces);me.update()
        ob=bpy.data.objects.new(me.name,me);bpy.context.collection.objects.link(ob);ob.location=(x,y,z);ob.rotation_euler[2]=0 if d==1 else math.pi
        ob.rotation_euler[1]=rng.uniform(-.08,.08);ob.scale=(1.05,)*3
        me.materials.append(fishmats[(name,g)]);me.materials.append(eye);me.materials.append(iris)
        uv=me.uv_layers.new()
        for poly in me.polygons:
            poly.use_smooth=True
            ids=list(poly.vertices)
            if data['part'][ids[0]]==1:poly.material_index=1 if sum(data['surface'][v] for v in ids)/3>.87 else 2
            for li in poly.loop_indices:
                vi=me.loops[li].vertex_index;uv.data[li].uv=data['uv'][vi*2:vi*2+2]

def area(name,loc,target,power,size,color):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;data.color=color
    ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()
area('wide overhead aquarium lamp',(-1,0,7.3),(0,1,0),1900,7,(.91,1,.91))
area('right overhead lamp',(4,1.3,6.8),(3,1,1),900,4,(.93,.98,1))
area('soft light through front glass',(0,-5,4.5),(0,1,2),800,8,(.88,.94,1))
area('leaf transmission light',(-3,3.8,5),(-2,0,2),1000,5,(.84,1,.83))
world=bpy.data.worlds.new('aquarium ambient');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.22,.31,.38,1);world.node_tree.nodes['Background'].inputs[1].default_value=.35;bpy.context.scene.world=world
camdata=bpy.data.cameras.new('offline reference camera');cam=bpy.data.objects.new('offline reference camera',camdata);bpy.context.collection.objects.link(cam)
cam.location=(0,-15.3,6.6);target=Vector((0,1,2.5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='PERSP';camdata.lens=48
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=50 if PREVIEW else 100
scene.cycles.samples=7 if PREVIEW else 24
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(WORK/'preview.png' if PREVIEW else OUT/'offline-1920.png')
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.5
scene.render.threads_mode='FIXED';scene.render.threads=6
bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'lush-reference.blend'))
print('Offline scene saved. Rendering one reference-camera candidate.',flush=True)
bpy.ops.render.render(write_still=True)
