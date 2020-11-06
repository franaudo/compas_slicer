import logging
from compas.geometry import Point
from compas_slicer.print_organization.print_organizer import PrintOrganizer
from compas_slicer.geometry import VerticalLayer
from compas_slicer.print_organization.curved_print_organization import topological_sorting as topo_sort
import compas_slicer.utilities as utils
from compas_slicer.print_organization.curved_print_organization import BaseBoundary
from compas_slicer.print_organization.curved_print_organization import SegmentConnectivity
from compas_slicer.print_organization import set_linear_velocity

logger = logging.getLogger('logger')

__all__ = ['CurvedPrintOrganizer']


class CurvedPrintOrganizer(PrintOrganizer):

    def __init__(self, slicer, parameters, DATA_PATH):
        assert isinstance(slicer.layers[0], VerticalLayer)  # curved printing only works with vertical layers
        PrintOrganizer.__init__(self, slicer)
        self.DATA_PATH = DATA_PATH
        self.OUTPUT_PATH = utils.get_output_directory(DATA_PATH)
        self.parameters = parameters

        # topological sorting of vertical layers depending on their connectivity
        self.topo_sort_graph = None
        if len(self.slicer.vertical_layers) > 1:
            self.topological_sorting()
        self.selected_order = None

        self.segments = {}  # one segment per vertical layer
        self.create_segments_dict()
        self.base_boundaries_creation()  # creation of one base boundary per vertical_layer
        self.create_segment_connectivity()

    def __repr__(self):
        return "<CurvedPrintOrganizer with %i segments>" % len(self.segments)

    def topological_sorting(self):
        """ When the print consists of various paths, this function initializes a class that creates
        a directed graph with all these parts, with the connectivity of each part reflecting which
        other parts it lies on, and which other parts lie on it."""
        self.topo_sort_graph = topo_sort.SegmentsDirectedGraph(self.slicer.mesh, self.slicer.vertical_layers,
                                                               max_d_threshold=self.parameters['max_layer_height'],
                                                               DATA_PATH=self.DATA_PATH)

    def create_segments_dict(self):
        """ Initializes segments dictionary with empty segments """
        for i, vertical_layer in enumerate(self.slicer.vertical_layers):
            self.segments[i] = {'boundary': None,
                                'path_collection': None}

    def base_boundaries_creation(self):
        """ Creates one BaseBoundary per vertical_layer  """
        root_vs = utils.get_mesh_vertex_coords_with_attribute(self.slicer.mesh, 'boundary', 1)
        root_boundary = BaseBoundary(self.slicer.mesh, [Point(*v) for v in root_vs])

        if len(self.slicer.vertical_layers) > 1:
            for i, vertical_layer in enumerate(self.slicer.vertical_layers):
                parents_of_current_node = self.topo_sort_graph.get_parents_of_node(i)
                if len(parents_of_current_node) == 0:
                    boundary = root_boundary
                else:
                    boundary_pts = []
                    for parent_index in parents_of_current_node:
                        parent = self.slicer.vertical_layers[parent_index]
                        boundary_pts.extend(parent.paths[-1].points)
                    boundary = BaseBoundary(self.slicer.mesh, boundary_pts)
                self.segments[i]['boundary'] = boundary
        else:
            self.segments[0]['boundary'] = root_boundary

        if self.parameters['create_intermediary_outputs']:
            b_data = {}
            for i in self.segments:
                b_data[i] = self.segments[i]['boundary'].to_data()
            utils.save_to_json(b_data, self.OUTPUT_PATH, 'boundaries.json')

    def create_segment_connectivity(self):
        """ A SegmentConnectivity finds vertical relation between paths. Creates and fills in printpoints """
        for i, vertical_layer in enumerate(self.slicer.vertical_layers):
            logger.info('Creating connectivity of segment no %d' % i)
            path_collection = SegmentConnectivity(paths=vertical_layer.paths,
                                                  base_boundary=self.segments[i]['boundary'],
                                                  mesh=self.slicer.mesh,
                                                  parameters=self.parameters)
            path_collection.compute()
            self.segments[i]['path_collection'] = path_collection

    def create_printpoints(self, mesh):
        """
        Based on the directed graph, select one topological order.
        From each path collection in that order fill in the PrintPoints dictionary
        """
        if len(self.slicer.vertical_layers) > 1:  # the you need to select one topological order
            all_orders = self.topo_sort_graph.get_all_topological_orders()
            self.selected_order = all_orders[0]  # TODO: add more elaborate selection strategy
        else:
            self.selected_order = [0]  # there is only one segment, only this option

        for i in self.selected_order:
            path_collection = self.segments[i]['path_collection']
            self.printpoints_dict['layer_%d' % i] = {}

            for j, path in enumerate(path_collection.paths):
                self.printpoints_dict['layer_%d' % i]['path_%d' % j] = \
                    [path_collection.printpoints[j][k] for k, p in enumerate(path.points)]

    ############################################
    #  ---  override function from base class

    def set_linear_velocity(self, velocity_type="matching_layer_height", v=None, per_layer_velocities=None):
        if velocity_type != "matching_layer_height":
            logger.warning("For non-planar slicing, print velocity should match layer_height")
        logger.info("Setting linear velocity to match layer_height")
        set_linear_velocity(self.printpoints_dict, velocity_type, v=v, per_layer_velocities=per_layer_velocities)