import pymel.core as pc


from . import references
reload(references)
from .references import getReferences


def getRefFromSet(geoset):
    for ref in getReferences(loaded=True):
        if geoset in ref.nodes():
            return ref


def getMeshFromSet(ref):
    meshes = []
    if ref:
        try:
            _set = [obj for obj in ref.nodes() if 'geo_set' in obj.name()
                    and type(obj)==pc.nt.ObjectSet ][0]
            meshes = [shape
                    for transform in pc.PyNode(_set).dsm.inputs(type="transform")
                    for shape in transform.getShapes(type = "mesh", ni = True)]
            #return [pc.polyUnite(ch=1, mergeUVSets=1, *_set.members())[0]] # put the first element in list and return
            combinedMesh = pc.polyUnite(ch=1, mergeUVSets=1, *meshes)[0]
            combinedMesh.rename(getNiceName(_set) + '_combinedMesh')
            return [combinedMesh] # put the first element in list and return
        except:
            return meshes
    return meshes


def getCombinedMeshFromSet(_set, midfix='shaded'):
    meshes = [shape for transform in _set.dsm.inputs() for shape in transform.getShapes(ni=True, type='mesh')]
    if not meshes: return
    pc.select(meshes)
    meshName =_set.name().replace('_geo_', '_' + midfix + '_').replace('_set',
            '_combined')
    if len(meshes) == 1:
        mesh = pc.duplicate(ic=True, name=meshName)[0]
        pc.parent(mesh, w=True)
        meshes[0].io.set(True)
        trash = [child for child in mesh.getChildren() if child !=
                mesh.getShape(type='mesh', ni=True)]
        pc.delete(trash)
    else:
        mesh = pc.polyUnite(ch=1, mergeUVSets=1, name=meshName)[0]
    try: pc.delete(_set)
    except: pass
    return mesh


def meshesCompatible(mesh1, mesh2, max_tries=100, feedback=False):
    reasons = {}
    status = True

    if not isMesh(mesh1):
        raise TypeError (
                'Object %r is not an instance of pymel.core.nodetypes.Mesh' % (
                    mesh1 ) )
    if not isMesh(mesh2):
        raise TypeError (
                'Object %r is not an instance of pymel.core.nodetypes.Mesh' % (
                    mesh2 ) )

    faces = pc.polyEvaluate(mesh1, f=True), pc.polyEvaluate(mesh2, f=True)
    vertices = pc.polyEvaluate(mesh1, v=True), pc.polyEvaluate(mesh2, v=True)
    edges = pc.polyEvaluate(mesh1, e=True), pc.polyEvaluate(mesh2, e=True)

    if faces[0] != faces[1]:
        if feedback: reasons['faces']=faces
        status = False
    if vertices[0] != vertices[1]:
        if feedback: reasons['vertices'] = vertices
        status = False
    if edges[0] != edges[1]:
        if feedback: reasons['edges'] = edges
        status = False

    if status:
        for i in range(min(len(mesh2.vtx), max_tries)):
            v = random.choice( mesh1.vtx.indices() )
            connEdges = ( mesh1.vtx[v].numConnectedEdges(),
                    mesh2.vtx[v].numConnectedEdges()  )
            if connEdges[0] != connEdges[1]:
                status = False
                if feedback: reasons['vertexOrder'] = (v, connEdges)
                break

    if feedback:
        return status, reasons
    else:
        return status


def setsCompatible(obj1, obj2, feedback=False):
    '''
    returns True if two ObjectSets are compatible for cache
    '''
    reasons = {}
    if type(obj1) != pc.nt.ObjectSet:
        raise TypeError(
                "Object %r is not an instance of pc.nt.ObjectSet"%( obj1 ))
    if type(obj2) != pc.nt.ObjectSet:
        raise TypeError(
                "Object %r is not an instance of pc.nt.ObjectSet"%( obj2 ))
    flag = True

    len1 = len(obj1)
    len2 = len(obj2)

    # check if the number of members is equal in both sets
    if len1 != len2:
        s1 = [removeNamespaceFromPathName(s) for s in obj1]
        s2 = [removeNamespaceFromPathName(s) for s in obj1]
        missing = set(s1) - set(s2)
        if feedback and missing:
            reasons['missing'] = missing
        extras = set(s2) - set(s1)
        if feedback and extras:
            reasons['extras'] = extras
        flag = False

    # check if the order and meshes are compatible in each set
    for i in range(max(len1, len2)):
        try:
            mesh1 = obj1.dagSetMembers[i].inputs()[0]
            mesh2 = obj2.dagSetMembers[i].inputs()[0]
            mesh_comp, mesh_reasons = meshesCompatible(mesh1, mesh2,
                    feedback=True)
            if not mesh_comp:
                flag = False
                if feedback:
                    if not reasons.get('unmatched', None):
                        reasons[ 'unmatched' ] = {}
                    reasons['unmatched'][i] = (
                            removeNamespaceFromPathName(mesh1),
                            removeNamespaceFromPathName(mesh2), mesh_reasons)
        except IndexError:
            pass
        except TypeError as e:
            import traceback
            traceback.print_exc()
            flag = False
            if feedback:
                if not reasons.get('errors', None):
                    reasons[ 'errors' ] = []
                reasons['errors'].append(('TypeError', str(e)))

    if feedback:
        return flag, reasons
    return flag

geo_sets_compatible = setsCompatible


def geo_set_valid(obj1):
    '''  '''
    obj1 = pc.nt.ObjectSet(obj1)
    if 'geo_set' not in obj1.name().lower():
        return False
    for i in range(len(obj1)):
        try:
            member = obj1.dagSetMembers[i].inputs()[0]
            mesh = member.getShape(type='mesh', ni=True)
        except:
            return False
        if not mesh or not mesh.numVertices():
            return False
    return True


def get_geo_sets(nonReferencedOnly=False, validOnly=False):
    geosets = []
    for node in pc.ls(exactType='objectSet'):
        if 'geo_set' in node.name().lower() and (not nonReferencedOnly or
                not node.isReferenced()) and (not validOnly or
                        geo_set_valid(node) ):
            geosets.append(node)
    return geosets


def getGeoSets():
    '''return only valid geo sets'''
    try:
        return [s for s in pc.ls(exactType=pc.nt.ObjectSet) if
                s.name().lower().endswith('_geo_set') and geo_set_valid(s)]
    except IndexError:
        pass


def find_geo_set_in_ref(ref, key=lambda node: 'geo_set' in node.name().lower()):
    for node in ref.nodes():
        if pc.nodeType(node) == 'objectSet':
            if key(node):
                return node

