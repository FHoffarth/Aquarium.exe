"""One offline art-direction candidate; never writes into habitat/.

node art/tools/export_offline_fish.mjs
blender -b --factory-startup -P art/tools/render_lush_reference.py
"""
import bpy, math, random, pathlib, json
from mathutils import Vector

ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK = ROOT / 'art/work/lush-reference'
OUT = ROOT / 'docs/evidence/lush-reference'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(260927)
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
    noise = n.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 8
    noise.inputs['Detail'].default_value = 2
    ramp = n.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = .15
    ramp.color_ramp.elements[0].color = tuple(c*.58 for c in color)+(1,)
    ramp.color_ramp.elements[1].position = .85
    ramp.color_ramp.elements[1].color = tuple(min(.95,c*1.2) for c in color)+(1,)
    l.new(noise.outputs['Fac'], ramp.inputs[0]); l.new(ramp.outputs[0],p.inputs['Base Color'])
    bump = n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = .13
    bump.inputs['Distance'].default_value = .035
    l.new(noise.outputs['Fac'], bump.inputs['Height']); l.new(bump.outputs[0],p.inputs['Normal'])
    return m

greens = []
for depth in range(3):
    for c in [(0.09,.34,.018),(.16,.43,.025),(.055,.25,.018),(.21,.39,.035),(.065,.32,.045),(.12,.29,.014)]:
        if depth == 2: c = (c[0]*.65,c[1]*.64,c[2]+.035)
        if depth == 1: c = (c[0]*.88,c[1]*.88,c[2]+.008)
        greens.append(leaf_material(f'leaf-{depth}-{len(greens)}',c))
stemmat = material('living green stems',(.09,.22,.025),.6)

class Mesh:
    def __init__(self,name): self.name=name; self.v=[]; self.f=[]; self.mi=[]; self.uv=[]
    def face(self, pts, mi=0):
        start=len(self.v); self.v.extend(pts); self.f.append(tuple(range(start,start+len(pts)))); self.mi.append(mi)
    def leaf(self,base, direction,length,width,mi, bend=.2,twist=0,segments=7):
        base=Vector(base); axis=Vector(direction).normalized()
        side=axis.cross(Vector((0,-1,.2))).normalized()
        if side.length < .1: side=Vector((1,0,0))
        normal=axis.cross(side).normalized(); start=len(self.v)
        for i in range(segments+1):
            t=i/segments
            center=base+axis*length*t+Vector((math.sin(t*3+twist)-math.sin(twist),0,-t*t))*bend
            span=width*(math.sin(math.pi*t)**.72)*(.92+.08*math.sin(t*17+twist))
            for u in [-1,0,1]:
                p=center+side*(span*u)+normal*(span*.18*(1-abs(u)))
                p+=normal*(span*u*math.sin(t*5+twist)*.24)
                self.v.append(tuple(p))
        for i in range(segments):
            for j in range(2):
                a=start+i*3+j
                self.f.append((a,a+1,a+4,a+3));self.mi.append(mi)
    def tube(self,pts,radius,mi=0):
        start=len(self.v); sides=5
        for i,p in enumerate(pts):
            for j in range(sides):
                a=j*math.tau/sides; r=radius*(1-i/(len(pts)+.5)*.75)
                self.v.append((p[0]+r*math.cos(a),p[1]+r*math.sin(a),p[2]))
        for i in range(len(pts)-1):
            for j in range(sides):
                a=start+i*sides+j;b=start+i*sides+(j+1)%sides
                self.f.append((a,b,b+sides,a+sides));self.mi.append(mi)
    def finish(self,mats):
        mesh=bpy.data.meshes.new(self.name);mesh.from_pydata(self.v,[],self.f);mesh.update()
        obj=bpy.data.objects.new(self.name,mesh);bpy.context.collection.objects.link(obj)
        for mat in mats: mesh.materials.append(mat)
        for p,mi in zip(mesh.polygons,self.mi):p.material_index=mi;p.use_smooth=True
        return obj

ribbon=Mesh('01 long flowing ribbons'); stems=Mesh('02 fine tall stems')
bush=Mesh('03 dense small-leaf bushes'); broad=Mesh('04 broad leaves'); low=Mesh('05 low foreground leaves')
stalk=Mesh('supporting stems')

def ribbon_clump(x,y,h,count=10):
    depth=2 if y>2.4 else 1 if y>1.2 else 0
    for j in range(count):
        a=rng.uniform(0,math.tau); lean=rng.uniform(.08,.34)
        ribbon.leaf((x+rng.uniform(-.15,.15),y+rng.uniform(-.1,.1),.12),
            (math.cos(a)*lean,math.sin(a)*lean,1),h*rng.uniform(.72,1.13),
            rng.uniform(.065,.13),depth*6+rng.randrange(6),rng.uniform(.2,.62),rng.uniform(-3,3),17)

# A varied rear canopy and sides; the central crown remains open.
for i in range(32):
    x=rng.uniform(-6.25,6.25); y=rng.uniform(1.5,3.45)
    h=rng.uniform(4.4,5.8) if abs(x)>2.5 else rng.uniform(2.4,3.6)
    ribbon_clump(x,y,h,rng.randint(6,11))

def stem_plant(x,y,h,depth=1):
    phase=rng.uniform(0,6.28); tilt=rng.uniform(-.22,.22)
    pts=[]
    for k in range(15):
        t=k/14; z=.12+h*t
        center=Vector((x+tilt*t+math.sin(t*3+phase)*.07,y+math.sin(t*4+phase)*.07,z));pts.append(center)
        if k<2:continue
        for j in range(5):
            a=j*math.tau/5+k*1.04+phase
            ln=rng.uniform(.18,.36)*(1-.3*t)
            stems.leaf(center,(math.cos(a),math.sin(a)*.65,.45),ln,rng.uniform(.023,.048),
                depth*6+rng.randrange(6),.025,phase,4)
    stalk.tube(pts,.012)

for cx,cy,h,n in [(-4.5,1.0,4.8,28),(-2.6,2.7,4.2,26),(4.65,1.1,4.6,30),(2.8,2.5,3.4,24),(-.6,3.3,2.8,18)]:
    for i in range(n):stem_plant(cx+rng.gauss(0,.48),cy+rng.gauss(0,.3),h*rng.uniform(.68,1.15),1 if cy<2 else 2)

def bush_mass(cx,cy,h,n=22):
    for i in range(n):
        x=cx+rng.gauss(0,.35);y=cy+rng.gauss(0,.26); height=h*rng.uniform(.55,1.12)
        tilt=rng.uniform(-.28,.28);pts=[]
        for k in range(8):
            t=k/7; p=Vector((x+tilt*t,y,.12+t*height));pts.append(p)
            for j in range(3):
                a=j*2.1+k*1.8+i
                bush.leaf(p,(math.cos(a),math.sin(a),.38),rng.uniform(.18,.32),rng.uniform(.055,.095),rng.randrange(6),.04,a,5)
        stalk.tube(pts,.009)

for x,y,h in [(-5.5,-.1,2.0),(-4,-.2,1.8),(-2.6,.1,2.3),(-1.3,1.7,2.3),(.25,2.1,2.45),
               (1.6,1.6,2.1),(3.0,.2,2.55),(4.45,-.1,2.1),(5.7,.15,2.6)]:
    bush_mass(x,y,h,25)

for cx,cy,h in [(-4.8,-.6,1.7),(-3.25,-.4,1.35),(-1.8,.1,1.4),(2.1,.0,1.7),(4.1,-.6,1.65),(5.4,-.5,1.6),(-.5,1.3,1.3)]:
    for p in range(4):
        x=cx+rng.uniform(-.4,.4);y=cy+rng.uniform(-.25,.25)
        for j in range(8):
            a=j*2.4+p;d=Vector((math.cos(a)*.55,math.sin(a)*.4,rng.uniform(.6,1.0)))
            broad.leaf((x,y,.15),d,h*rng.uniform(.5,1.05),rng.uniform(.12,.23),rng.randrange(6),.12,a,11)

# Foreground mounds leave a narrow, irregular gravel opening near the centre.
for i in range(75):
    x=rng.uniform(-6.3,6.3);y=rng.uniform(-1.55,-.45)
    if -.8<x<1.55 and rng.random()<.85:continue
    for j in range(rng.randint(7,13)):
        a=rng.uniform(0,math.tau)
        low.leaf((x,y,.06),(math.cos(a)*.8,math.sin(a)*.6,1),rng.uniform(.28,.8),rng.uniform(.018,.042),rng.randrange(6),.12,a,7)

for mesh in [ribbon,stems,bush,broad,low]:mesh.finish(greens)
stalk.finish([stemmat])

# Small neutral gravel; low warm wood stays behind the leaf masses.
gravelmats=[material('gravel '+str(i),c,.85) for i,c in enumerate([(.21,.22,.20),(.36,.34,.29),(.12,.14,.14),(.42,.40,.34),(.26,.25,.22)])]
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.03));bpy.context.object.name='gravel bed';bpy.context.object.data.materials.append(gravelmats[0])
pebbles=Mesh('fine gravel openings')
for i in range(9000):
    x=rng.uniform(-6.7,6.7);y=rng.uniform(-2.2,3.6);z=rng.uniform(.0,.025);r=rng.uniform(.018,.046)
    pts=[(x+math.cos(j*math.tau/6)*r,y+math.sin(j*math.tau/6)*r*.8,z) for j in range(6)]
    top=(x+r*.15,y,r*.65+z)
    for j in range(6):pebbles.face([pts[j],pts[(j+1)%6],top],rng.randrange(5))
pebbles.finish(gravelmats)
wood=material('subordinate warm driftwood',(.12,.049,.019),.83)
wn=wood.node_tree.nodes;wl=wood.node_tree.links;tex=wn.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=7;tex.inputs['Detail'].default_value=4
bu=wn.new('ShaderNodeBump');bu.inputs['Strength'].default_value=.6;bu.inputs['Distance'].default_value=.12;wl.new(tex.outputs['Fac'],bu.inputs['Height']);wl.new(bu.outputs[0],wn.get('Principled BSDF').inputs['Normal'])
for x,y,a in [(-2.1,.3,.3),(2.4,.55,-.5),(-4.3,.7,.1)]:
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20,ring_count=12,location=(x,y,.33))
    obj=bpy.context.object;obj.name='partly planted driftwood';obj.scale=(1.0,.23,.23);obj.rotation_euler[1]=a;obj.data.materials.append(wood)
    for p in obj.data.polygons:p.use_smooth=True

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
cam.location=(0,-17,5.1);target=Vector((0,1,3.05));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=12.7
scene=bpy.context.scene;scene.camera=cam;scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1920;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath=str(OUT/'offline-1920.png')
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium High Contrast';scene.view_settings.exposure=.5
scene.render.threads_mode='FIXED';scene.render.threads=6
bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'lush-reference.blend'))
print('Offline scene saved. Rendering one reference-camera candidate.',flush=True)
bpy.ops.render.render(write_still=True)
