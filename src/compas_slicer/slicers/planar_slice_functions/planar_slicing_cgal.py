import itertools
from compas.geometry import Point
from compas_slicer.geometry import Layer
from compas_slicer.geometry import Path
from compas_cgal.slicer import slice_mesh

import logging
import time

logger = logging.getLogger('logger')

__all__ = ['create_planar_paths_cgal']


def create_planar_paths_cgal(mesh, min_z, max_z, planes):
    """Creates planar contours using CGAL
    Considers all resulting paths as CLOSED paths.
    This is a very fast method.

    Parameters
    ----------
    mesh : compas.datastructures.Mesh
        A compas mesh.
    min_z: float
    max_z: float
    planes: list, compas.geometry.Plane
    """

    # prepare mesh for slicing
    M = mesh.to_vertices_and_faces()

    # slicing operation
    contours = slice_mesh(M, planes)

    def get_grouped_list(item_list, key_function):
        # first sort, because grouping only groups consecutively matching items
        sorted_list = sorted(item_list, key=key_function)
        # group items, using the provided key function
        grouped_iter = itertools.groupby(sorted_list, key_function)
        # return reformatted list
        return [list(group) for _key, group in grouped_iter]

    def key_function(item):
        return item[0][2]

    cgal_layers = get_grouped_list(contours, key_function=key_function)

    layers = []
    for layer in cgal_layers:

        z = layer[0][0][2]
        logger.info('Cutting at height %.3f, %d percent done' % (
            z, int(100 * (z - min_z) / (max_z - min_z))))

        paths_per_layer = []
        for path in layer:
            points_per_contour = []
            for point in path:
                pt = Point(point[0], point[1], point[2])
                points_per_contour.append(pt)
            # generate contours
            # TODO: add a check for is_closed
            path = Path(points=points_per_contour, is_closed=True)
            paths_per_layer.append(path)

        # generate layers
        l = Layer(paths_per_layer)
        layers.append(l)

    return layers


if __name__ == "__main__":
    pass
