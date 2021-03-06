# Module with all the routines necessary to extract information
# about the crystal from the configuration file: reciprocal space,
# symmetry group and high symmetry points

# Definition of all routines to build and solve the tight-binding hamiltonian
# constructed from the parameters of the configuration file

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from numpy.linalg import LinAlgError
import math
import sys
import vpython as vp

# --------------- Constants ---------------
PI = 3.141592653589793238
EPS = 0.001


# --------------- Routines ---------------
class Crystal:
    """ Implementation of Crystal class. Defaults to square lattice if no input is given. """

    def __init__(self, bravais_lattice=None, motif=None):
        # To be initialized in methods
        self.group = None
        self.reciprocal_basis = None
        self.high_symmetry_points = None

        self._ndim = None
        self.natoms = None
        self._bravais_lattice = None
        self.bravais_lattice = bravais_lattice
        self._motif = None
        self.motif = motif

    @property
    def ndim(self) -> int:
        return self._ndim

    @ndim.setter
    def ndim(self, ndim):
        assert type(ndim) == int
        if ndim > 3 or ndim < (-1):
            print("Incorrect dimension for system, exiting...")
            sys.exit(1)
        self._ndim = ndim

    @property
    def bravais_lattice(self) -> np.ndarray:
        return self._bravais_lattice

    @bravais_lattice.setter
    def bravais_lattice(self, bravais_lattice):
        if bravais_lattice is None:
            self._bravais_lattice = None
        else:
            assert type(bravais_lattice) == list or type(bravais_lattice) == np.ndarray
            bravais_lattice = np.array(bravais_lattice)
            if bravais_lattice.shape[1] != 3:
                raise Exception("Vectors must have three components")
            self._bravais_lattice = bravais_lattice
            self._ndim = len(bravais_lattice)
            self.update()

    @property
    def motif(self):
        return self._motif

    @motif.setter
    def motif(self, motif):
        if motif is None:
            self._motif = None
        else:
            assert type(motif) == list or type(motif) == np.ndarray
            for atom in motif:
                if len(atom) != 4:
                    raise Exception("Each position must have three components")
            self._motif = motif
            self.natoms = len(motif)

    def add_atom(self, position):
        assert type(position) == list
        if len(position) != 3:
            raise Exception("Vector must have three components")
        self.motif.append(position)

    def remove_atom(self, index):
        self.motif.pop(index)

    def update(self):
        """ Routine to initialize or update the intrinsic attributes of the Crystal class whenever
        the Bravais lattice is changed """
        # Init methods
        self.crystallographic_group()
        self.reciprocal_lattice()
        self.determine_high_symmetry_points()

    def crystallographic_group(self):
        """ Determines the crystallographic group associated to the material from
        the configuration file. NOTE: Only the group associated to the Bravais lattice,
        reduced symmetry due to presence of motif is not taken into account. Its purpose is to
        provide a path in k-space to plot the band structure.
        Workflow is the following: First determine length and angles between basis vectors.
        Then we separate by dimensionality: first we check angles, and then length to
        determine the crystal group. """

        basis_norm = [np.linalg.norm(vector) for vector in self.bravais_lattice]
        group = ''

        basis_angles = []
        for i in range(self.ndim):
            for j in range(self.ndim):
                if j <= i: continue
                v1 = self.bravais_lattice[i]
                v2 = self.bravais_lattice[j]
                basis_angles.append(math.acos(np.dot(v1, v2)/(np.linalg.norm(v1)*np.linalg.norm(v2))))

        if self.ndim == 2:
            if abs(basis_angles[0] - PI / 2) < EPS:
                if abs(basis_norm[0] - basis_norm[1]) < EPS:
                    group += 'Square'
                else:
                    group += 'Rectangular'

            elif (abs(basis_angles[0] - PI / 3) < EPS or
                  abs(basis_angles[0] - 2 * PI / 3) < EPS) and abs(basis_norm[0] - basis_norm[1]) < EPS:
                group += 'Hexagonal'

            else:
                if abs(basis_norm[0] - basis_norm[1]) < EPS:
                    group += 'Centered rectangular'
                else:
                    group += 'Oblique'

        elif self.ndim == 3:
            if (basis_angles[0] - PI/2) < EPS and (basis_angles[1] - PI/2) < EPS and (basis_angles[2] - PI/2) < EPS:
                if abs(basis_norm[0] - basis_norm[1]) < EPS and abs(basis_norm[0] - basis_norm[2]) < EPS and abs(basis_norm[1] - basis_norm[2]) < EPS:
                    group += 'Cube'

            else:
                print('Work in progress')

        self.group = group

    def reciprocal_lattice(self):
        """ Routine to compute the reciprocal lattice basis vectors from
        the Bravais lattice basis. The algorithm is based on the fact that
        a_i\dot b_j=2PI\delta_ij, which can be written as a linear system of
        equations to solve for b_j. Resulting vectors have 3 components independently
        of the dimension of the vector space they span."""

        reciprocal_basis = np.zeros([self.ndim, 3])
        coefficient_matrix = np.array(self.bravais_lattice)

        if self.ndim == 1:
            reciprocal_basis = 2*PI*coefficient_matrix/(np.linalg.norm(coefficient_matrix)**2)

        else:
            coefficient_matrix = coefficient_matrix[:, :self.ndim]
            for i in range(self.ndim):
                coefficient_vector = np.zeros(self.ndim)
                coefficient_vector[i] = 2*PI
                try:
                    reciprocal_vector = np.linalg.solve(coefficient_matrix, coefficient_vector)
                except LinAlgError:
                    print('Error: Bravais lattice basis is not linear independent')
                    sys.exit(1)

                reciprocal_basis[i, 0:self.ndim] = reciprocal_vector

        self.reciprocal_basis = reciprocal_basis

    def brillouin_zone_mesh(self, mesh):
        """ Routine to compute a mesh of the first Brillouin zone using the
        Monkhorst-Pack algorithm. Returns a list of k vectors. """

        if len(mesh) != self.ndim:
            print('Error: Mesh does not match dimension of the system')
            sys.exit(1)

        kpoints = []
        mesh_points = []
        for i in range(self.ndim):
            mesh_points.append(list(range(0, mesh[i] + 1)))

        mesh_points = np.array(np.meshgrid(*mesh_points)).T.reshape(-1, self.ndim)

        for point in mesh_points:
            kpoint = 0
            for i in range(self.ndim):
                kpoint += (2.*point[i] - mesh[i])/(2*mesh[i])*self.reciprocal_basis[i]
            kpoints.append(kpoint)

        self.kpoints = np.array(kpoints)

    def determine_high_symmetry_points(self):
        """ Routine to compute high symmetry points depending on the dimension of the system.
        These symmetry points will be used to plot the band structure along the main
        reciprocal paths of the system (irreducible BZ). Returns a dictionary with pairs
        {letter denoting high symmetry point: its coordinates} """

        norm = np.linalg.norm(self.reciprocal_basis[0])
        special_points = {"G": np.array([0., 0., 0.])}
        if self.ndim == 1:
            special_points.update({'K': self.reciprocal_basis[0]/2})

        elif self.ndim == 2:
            special_points.update({'M': self.reciprocal_basis[0]/2})
            if self.group == 'Square':
                special_points.update({'K': self.reciprocal_basis[0]/2 + self.reciprocal_basis[1]/2})

            elif self.group == 'Rectangular':
                special_points.update({'M*': self.reciprocal_basis[1]/2})
                special_points.update({'K':  self.reciprocal_basis[0]/2 + self.reciprocal_basis[1]/2})
                special_points.update({'K*': -self.reciprocal_basis[0]/2 + self.reciprocal_basis[1]/2})

            elif self.group == 'Hexagonal':
                # special_points.update({'K',: reciprocal_basis[0]/2 + reciprocal_basis[1]/2})
                special_points.update({'K': norm/math.sqrt(3)*(self.reciprocal_basis[0]/2 - self.reciprocal_basis[1]/2)/(
                                             np.linalg.norm(self.reciprocal_basis[0]/2 - self.reciprocal_basis[1]/2))})

            else:
                print('High symmetry points not implemented yet')

        else:
            if self.group == 'Cube':
                special_points.update({'X': self.reciprocal_basis[0]/2})
                special_points.update({'M': self.reciprocal_basis[0]/2 + self.reciprocal_basis[1]/2})
                special_points.update({'R': self.reciprocal_basis[0]/2 + self.reciprocal_basis[1]/2 +
                                            self.reciprocal_basis[2]/2})

            else:
                print('High symmetry points not implemented yet')

        self.high_symmetry_points = special_points

    def __reorder_high_symmetry_points(self, labels):
        """ Routine to reorder the high symmetry points according to a given vector of labels
         for later representation.
         DEPRECATED with the dictionary update """
        points = []
        for label in labels:
            appended = False
            for point in self.high_symmetry_points:
                if appended:
                    continue
                if label == point[0]:
                    points.append(point)
                    appended = True

        self.high_symmetry_points = points

    def __strip_labels_from_high_symmetry_points(self):
        """ Routine to output both labels and array corresponding to high symmetry points
         DEPRECATED with the dictionary update """

        for n, point in enumerate(self.high_symmetry_points):
            self.high_symmetry_points[n] = point[1]

    def high_symmetry_path(self, nk, points):
        """ Routine to generate a path in reciprocal space along the high symmetry points """

        # self.__reorder_high_symmetry_points(points)
        # self.__strip_labels_from_high_symmetry_points()

        kpoints = []
        number_of_points = len(points)
        interval_mesh = int(nk/number_of_points)
        previous_point = self.high_symmetry_points[points[0]]
        for point in points[1:]:
            next_point = self.high_symmetry_points[point]
            kpoints += list(np.linspace(previous_point, next_point, interval_mesh, endpoint=False))
            previous_point = next_point
        kpoints.append(self.high_symmetry_points[points[-1]])

        return kpoints

    def plot_crystal(self, cell_number=1, crystal_name=''):
        """
        Method to visualize the crystalline structure (Bravais lattice + motif).
        Parameters:
            (optional) cell_number: Number of cells appended in each direction with respect to the origin
            By default, cell_number = 1 (zero = only motif)
        """

        bravais_lattice = np.array(self.bravais_lattice)
        motif = np.array(self.motif)

        fig = plt.figure()
        ax = Axes3D(fig)
        bravais_vectors_mesh = []
        for i in range(self.ndim):
            bravais_vectors_mesh.append(list(range(-cell_number, cell_number + 1)))
        bravais_vectors_mesh = np.array(np.meshgrid(*bravais_vectors_mesh)).T.reshape(-1, self.ndim)

        bravais_vectors = np.zeros([len(bravais_vectors_mesh[:, 0]), 3])
        for n, coefs in enumerate(bravais_vectors_mesh):
            for i, coef in enumerate(coefs):
                bravais_vectors[n, :] += coef * bravais_lattice[i]

        all_atoms_list = np.zeros([len(bravais_vectors_mesh)*len(motif), 3])
        iterator = 0
        for vector in bravais_vectors:
            for atom in motif:
                all_atoms_list[iterator, :] = atom[:3] + vector
                iterator += 1

        [min_axis, max_axis] = [np.min(all_atoms_list), np.max(all_atoms_list)]

        for atom in all_atoms_list:
            ax.scatter(atom[0], atom[1], atom[2], color='y', s=50)

        ax.set_xlabel('x (A)')
        ax.set_ylabel('y (A)')
        ax.set_zlabel('z (A)')
        ax.set_title(crystal_name + ' crystal')
        ax.set_xlim3d(min_axis, max_axis)
        ax.set_ylim3d(min_axis, max_axis)
        ax.set_zlim3d(min_axis, max_axis)
        plt.show()

    def visualize(self):
        global atoms, extra_atoms
        global bonds, extra_bonds
        atoms = []
        extra_atoms = []
        bonds = []
        extra_bonds = []
        mesh_points = []
        vp.scene.background = vp.color.white
        color_list = [vp.color.yellow, vp.color.red]
        # Unit cell atoms
        for position in self.motif:
            species = int(position[3])
            atom = vp.sphere(radius=0.1, color=color_list[species])
            atom.pos.x, atom.pos.y, atom.pos.z = position[:3]
            atoms.append(atom)

        # Supercell atoms
        for i in range(self.ndim):
            mesh_points.append(list(range(-1, 2)))
        mesh_points = np.array(np.meshgrid(*mesh_points)).T.reshape(-1, self.ndim)
        for point in mesh_points:
            unit_cell = np.array([0., 0., 0.])
            if np.linalg.norm(point) == 0:
                continue
            for n in range(self.ndim):
                unit_cell += point[n]*self.bravais_lattice[n]
            for position in self.motif:
                species = int(position[3])
                atom = vp.sphere(radius=0.1, color=color_list[species])
                atom.visible = False
                atom.pos.x, atom.pos.y, atom.pos.z = (position[:3] + unit_cell)
                extra_atoms.append(atom)

        # Unit cell bonds
        for i, neighbours in enumerate(self.neighbours):
            for neighbour in neighbours:
                unit_cell = vp.vector(neighbour[1][0], neighbour[1][1], neighbour[1][2])
                bond = vp.curve(atoms[i].pos, atoms[neighbour[0]].pos + unit_cell)
                bonds.append(bond)

        # Supercell bonds
        for point in mesh_points:
            unit_cell = np.array(([0., 0., 0.]))
            for n in range(self.ndim):
                unit_cell += point[n]*self.bravais_lattice[n]
            unit_cell = vp.vector(unit_cell[0], unit_cell[1], unit_cell[2])
            for bond in bonds:
                supercell_bond = vp.curve(bond.point(0)["pos"] + unit_cell, bond.point(1)["pos"] + unit_cell)
                supercell_bond.visible = False
                extra_bonds.append(supercell_bond)

        vp.button(text="supercell", bind=self.__add_unit_cells)
        vp.button(text="primitive unit cell", bind=self.__remove_unit_cells)
        vp.button(text="remove bonds", bind=self.__remove_bonds)
        vp.button(text="show bonds", bind=self.__show_bonds)
        vp.button(text="draw cell boundary", bind=self.__draw_boundary)
        vp.button(text="remove cell boundary", bind=self.__remove_boundary)
        vp.scene.bind("mousedown", self.__mousedown)
        vp.scene.bind("mousemove", self.__mousemove)
        vp.scene.bind("mouseup", self.__mouseup)

    def __mousedown(self):
        global drag, initial_position
        initial_position = vp.scene.mouse.pos
        drag = True

    def __mousemove(self):
        global drag, initial_position
        if drag:
            increment = vp.scene.mouse.pos - initial_position
            initial_position = vp.scene.mouse.pos
            vp.scene.camera.pos -= increment

    def __mouseup(self):
        global drag, initial_position
        pass

    def __add_unit_cells(self):
        for atom in extra_atoms:
            atom.visible = True

    def __show_bonds(self):
        for bond in bonds:
            bond.visible = True
        if extra_atoms[0].visible:
            for bond in extra_bonds:
                bond.visible = True

    def __remove_unit_cells(self):
        for atom in extra_atoms:
            atom.visible = False
        if extra_bonds[0].visible:
            for bond in extra_bonds:
                bond.visible = False

    def __remove_bonds(self):
        for bond in bonds:
            bond.visible = False
        for bond in extra_bonds:
            bond.visible = False

    def __draw_boundary(self):
        global cell_boundary
        global cell_vectors
        cell_vectors = []
        mid_point = np.array([0., 0., 0.])
        size_vector = [0., 0., 0.]
        for n in range(self.ndim):
            mid_point += self.bravais_lattice[n]/2
            size_vector[n] = self.bravais_lattice[n][n]
        cell_boundary = vp.box(pos=vp.vector(mid_point[0], mid_point[1], mid_point[2]),
                               size=vp.vector(size_vector[0], size_vector[1], size_vector[2]), opacity=0.5)
        for basis_vector in self.bravais_lattice:
            unit_cell = vp.vector(basis_vector[0], basis_vector[1], basis_vector[2])
            vector = vp.arrow(pos=vp.vector(0, 0, 0), axis=unit_cell, color=vp.color.green, shaftwidth=0.1)
            cell_vectors.append(vector)

    def __remove_boundary(self):
        cell_boundary.visible = False
        for vector in cell_vectors:
            vector.visible = False

