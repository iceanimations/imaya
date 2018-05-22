import random
import re

import pymel.core as pc

from .references import getReferences, createReference, removeReference
from .utils import isMesh, removeNamespaceFromPathName


GEO_SET_PATTERN = re.compile(
        r'(.*?)\|?([^|]*?):?([^\^:|]+)(_geo_set)$', re.IGNORECASE)


def is_geo_set(node, pattern=None):
    if type(node) == pc.nt.ObjectSet:
        return GEO_SET_PATTERN.match(str(pc.nt.ObjectSet(node)))


def get_geo_sets_from_reference(ref, valid_only=False):
    sets = []
    check_func = geo_set_valid if valid_only else is_geo_set
    if ref:
        sets = [obj for obj in ref.nodes() if check_func(obj)]
    return sets


def geo_set_valid(obj1):
    ''' return geo set validity (content) '''
    if not is_geo_set(obj1):
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


def get_combined_mesh_from_set(_set, midfix='shaded'):
    meshes = [shape for transform in _set.dsm.inputs() for shape in
              transform.getShapes(ni=True, type='mesh')]
    if not meshes:
        return
    pc.select(meshes)
    meshName = _set.name().replace('_geo_', '_' + midfix + '_').replace(
            '_set', '_combined')
    if len(meshes) == 1:
        pc.mel.DeleteHistory()
        mesh = pc.duplicate(ic=True, name=meshName)[0]
        pc.parent(mesh, w=True)
        meshes[0].io.set(True)
        trash = [child for child in mesh.getChildren() if child !=
                 mesh.getShape(type='mesh', ni=True)]
        pc.delete(trash)
    else:
        mesh = pc.polyUnite(ch=1, mergeUVSets=1, name=meshName)[0]
    try:
        pc.delete(_set)
    except:
        pass
    return mesh


def get_combined_meshes_from_ref(ref=None, midfix='shaded'):
    meshes = []
    if ref is None:
        sets = get_geo_sets(True, True)
    else:
        sets = get_geo_sets_from_reference(ref)
    for _set in sets:
        meshes.append(get_combined_mesh_from_set(_set, midfix=midfix))
    return meshes


def get_combined_meshes_from_current_scene(midfix='shaded'):
    return get_combined_meshes_from_ref(midfix=midfix)


def meshes_compatible(mesh1, mesh2, max_tries=100, feedback=False):
    reasons = {}
    status = True

    if not isMesh(mesh1):
        raise TypeError(
                'Object %r is not an instance of pymel.core.nodetypes.Mesh' % (
                    mesh1))
    if not isMesh(mesh2):
        raise TypeError(
                'Object %r is not an instance of pymel.core.nodetypes.Mesh' % (
                    mesh2))

    faces = pc.polyEvaluate(mesh1, f=True), pc.polyEvaluate(mesh2, f=True)
    vertices = pc.polyEvaluate(mesh1, v=True), pc.polyEvaluate(mesh2, v=True)
    edges = pc.polyEvaluate(mesh1, e=True), pc.polyEvaluate(mesh2, e=True)

    if faces[0] != faces[1]:
        if feedback:
            reasons['faces'] = faces
        status = False
    if vertices[0] != vertices[1]:
        if feedback:
            reasons['vertices'] = vertices
        status = False
    if edges[0] != edges[1]:
        if feedback:
            reasons['edges'] = edges
        status = False

    if status:
        for i in range(min(len(mesh2.vtx), max_tries)):
            v = random.choice(mesh1.vtx.indices())
            connEdges = (mesh1.vtx[v].numConnectedEdges(),
                         mesh2.vtx[v].numConnectedEdges())
            if connEdges[0] != connEdges[1]:
                status = False
                if feedback:
                    reasons['vertexOrder'] = (v, connEdges)
                break

    if feedback:
        return status, reasons
    else:
        return status


def geo_sets_compatible(obj1, obj2, feedback=False):
    '''
    returns True if two ObjectSets are compatible for cache
    '''
    reasons = {}
    if type(obj1) != pc.nt.ObjectSet:
        raise TypeError(
                "Object %r is not an instance of pc.nt.ObjectSet" % (obj1))
    if type(obj2) != pc.nt.ObjectSet:
        raise TypeError(
                "Object %r is not an instance of pc.nt.ObjectSet" % (obj2))
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
            mesh_comp, mesh_reasons = meshesCompatible(mesh1,
                                                       mesh2, feedback=True)
            if not mesh_comp:
                flag = False
                if feedback:
                    if not reasons.get('unmatched', None):
                        reasons['unmatched'] = {}
                    reasons['unmatched'][i] = (
                            removeNamespaceFromPathName(mesh1),
                            removeNamespaceFromPathName(mesh2), mesh_reasons)

        except IndexError:
            pass

        except TypeError as exc:
            import traceback
            traceback.print_exc()
            flag = False
            if feedback:
                if not reasons.get('errors', None):
                    reasons['errors'] = []
                reasons['errors'].append(('TypeError', str(exc)))

    if feedback:
        return flag, reasons
    return flag


def get_geo_sets(non_referenced_only=False, valid_only=False):
    geosets = []

    for node in pc.ls(exactType='objectSet'):
        if (is_geo_set(node) and
                (not non_referenced_only or not node.isReferenced()) and
                (not valid_only or geo_set_valid(node))):
            geosets.append(node)

    return geosets


def refs_compatible(ref1, ref2=None, feedback=False):
    reasons = dict()

    try:
        sets1 = sorted(get_geo_sets_from_reference(ref1, valid_only=True))
        if ref2 is None:
            sets2 = get_geo_sets(non_referenced_only=True, valid_only=False)
        else:
            sets2 = sorted(get_geo_sets_from_reference(ref2, valid_only=True))

    except (AttributeError, TypeError) as exc:
        reasons['errors'] = [(exc.__class__.__name__, str(exc))]

    flag = True
    if len(sets1) != len(sets2):
        flag = False
        if feedback:
            reasons['sets'] = (
                    'number of valid geo sets (%d, %d) is different' % (
                        len(sets1), len(sets2)))
            return flag, reasons
        else:
            return flag

    count = 0
    for set1, set2 in zip(sets1, sets2):
        if feedback:
            compatible, _reasons = geo_sets_compatible(set1, set2, True)
        else:
            compatible = geo_sets_compatible(set1, set2, False)
        if not compatible:
            flag = False
            if feedback:
                if 'unmatched_sets' not in reasons:
                    reasons['unmatched_sets'] = {}
                reasons['unmatched_sets'][count] = (
                        str(set1), str(set2), _reasons)
                count += 1
            else:
                break

    if feedback:
        return flag, reasons
    return flag


def current_scene_compatible_with_ref(ref, feedback=False):
    return refs_compatible(ref, feedback=feedback)


def current_scene_compatible(_file, feedback=False):
    flag = True
    reasons = dict()

    try:
        ref = createReference(_file)
        flag, reasons = current_scene_compatible_with_ref(ref, True)

    except Exception as exc:
        flag = False
        reasons['errors'] = [(exc.__class__.__name__, str(exc))]

    finally:
        if ref:
            removeReference(ref)

    if feedback:
        return flag, reasons
    return flag


# names for backward compatibility
meshesCompatible = meshes_compatible
setsCompatible = geo_sets_compatible
getGeoSets = get_geo_sets
currentSceneCompatible = current_scene_compatible
currentSceneCompatibleWithRef = current_scene_compatible_with_ref
getCombinedMeshFromSet = get_combined_mesh_from_set
geoSetValid = geo_set_valid
