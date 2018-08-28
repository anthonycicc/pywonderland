# -*- coding: utf-8 -*-
"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This file contains the models of various polytopes in 3D/4D
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
To build a polytope two inputs are required:

1. A Coxeter-Dynkin diagram. This diagram completely determines
   the symmetry of the polytope.
   For a 3D polytope its Coxeter-Dynkin diagram is a tuple of three
   integers (p, q, r), e.g. (3, 2, 3) is the tetrahedral symmetry,
   (4, 2, 3) is the octahedral symmetry,
   (5, 2, 3) is the dodecahedral symmetry.
   For a 4D polytope its Coxeter-Dynkin diagram is represented by a
   tuple of six integers, e.g. (5, 2, 2, 3, 2, 3) is the H4 group,
   (4, 2, 2, 3, 2, 2) is the BC3xA1 group of the octahedral prism, etc.
   Given this Coxeter-Dynkin diagram the presentation of the symmetry
   group `G` is built and 3 or 4 reflection planes are then computed.

2. Position of an initial vertex on the unit sphere. This determines
   the "truncation" type of the polytope. This input is represented by
   a tuple of 3 (for a 3D polytope) or 4 (for a 4D polytope) floats which
   specifies the distances of the initial vertex to the reflection planes.
   For example (1, 0.5, 0) means the initial vertex is on the 3rd plane
   and the ratio between its distances to the 1st and 2nd planes is 1: 0.5.
   Given these distances the coordinates of the initial vertex `v` is
   computed (it's also normalized so it lies on the unit sphere).

Once we have the presentation of the symmetry group `G`, the reflection
planes (called mirrors) and coordinates of the initial vertex `v`, we then
move on to compute the vertices, edges and faces of this polytope as follows:

1. [Vertex]
   Find the generators of the stabilizing subgroup `H` which fixes `v`.
   Once this is done we can use Todd-Coxeter algorithm to compute the coset
   table of G/H. By the orbit-stabilizer theorem G/H and the set of vertices
   are in one-to-one correspondence: gH -> gv. So for each gH in the coset
   table we just choose any word representaion of g (a compostions of the
   reflections about the mirrors) and act g on v to get gv.

2. [Edge]
   Find the generators of the stabilizing subgroup `Hi` which fixes an
   initial edge of type `i`. Here an edge is of type `i` if and only if
   its two ends are mirror images of the i-th plane.
   Once this done we can get all edges of type `i` as in the vertex case.

3. [Face]
   Find the generators of the stabilizing subgroup `Hij` which fixes an
   initial face of type `ij`. Here a face is of type `ij` if and only if
   the rotation about the axis that connects its center and the origin is
   the composition of the i-th reflection and the j-th reflection.
   Once this done we can get all faces of type `ij` as in the vertex case.
"""
from itertools import combinations
import numpy as np
from todd_coxeter import CosetTable
import helpers


class BasePolytope(object):
    """
    Base class for 3d polyhedra and 4d polychora using Wythoff's construction.
    """

    def __init__(self, upper_triangle, init_dist):
        # the Coxeter matrix
        self.coxeter_matrix = helpers.get_coxeter_matrix(upper_triangle)

        # the reflecting mirrors
        self._mirrors = helpers.get_mirrors(upper_triangle)

        # reflection transformations about the mirrors
        self._reflections = tuple(helpers.reflection_matrix(v) for v in self._mirrors)

        # coordinates of the initial vertex
        self.init_v = helpers.get_init_point(self._mirrors, init_dist)

        # a bool list holds if a mirror is active or not.
        self.active = tuple(bool(x) for x in init_dist)

        dim = len(self.coxeter_matrix)

        # generators of the Coxeter group
        self.symmetry_gens = tuple(range(dim))

        # relations between the generators
        self.symmetry_rels = tuple((i, j) * self.coxeter_matrix[i][j]
                                   for i, j in combinations(self.symmetry_gens, 2))

        # to be calculated later
        self._vtable = None

        self.num_vertices = None
        self.vertex_coords = []

        self.num_edges = None
        self.edge_indices = []
        self.edge_coords = []

        self.num_faces = None
        self.face_indices = []
        self.face_coords = []

    def build_geometry(self):
        self.get_vertices()
        self.get_edges()
        self.get_faces()

    def get_vertices(self):
        """
        This method computes the following data that will be needed later:

        1. Coset table for the total symmetry group. (so for a vertex indexed by i
           and a word w, we can get the index of the transformed vertex i·w)

        2. Word representaions for each element in the symmetry group. (for exporting
           the words to latex format)

        3. Coordinates of the vertices. (of course we will need this)
        """
        # generators for the stabilizing subgroup of the initial vertex.
        vgens = [(i,) for i, active in enumerate(self.active) if not active]
        # build the coset table
        self._vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, vgens)
        # run the table
        self._vtable.run()
        # get word representaions for the cosets
        self._vwords = self._vtable.get_words()
        # number the vertices
        self.num_vertices = len(self._vwords)
        # use the word representaions to transform the initial vertex to other vertices
        self.vertex_coords = tuple(self._transform(self.init_v, word) for word in self._vwords)

    def get_edges(self):
        """
        If the initial vertex `v0` lies on the `i`-th mirror then the reflection about
        this mirror fixes `v0` and there are no edges of type `i`.

        Else `v0` and its mirror image about this mirror generates a base edge of type `i`,
        its stabilizing subgroup is generated by the word `(i,)` and we can again use
        Todd-Coxeter's procedure to get the word representaions for all edges of type `i`.
        """
        for i, active in enumerate(self.active):
            if active:
                # generator for the stabilizing subgroup of the base edge of type `i`
                egens = [(i,)]
                # build the coset table
                etable = CosetTable(self.symmetry_gens, self.symmetry_rels, egens)
                # run the table
                etable.run()
                # get word representaions for the cosets
                words = etable.get_words()
                # store all edges of type `i` in a list
                elist = []
                for word in words:
                    # two ends of this edge
                    v1 = self._move(0, word)
                    v2 = self._move(0, (i,) + word)
                    # avoid duplicates
                    if (v1, v2) not in elist and (v2, v1) not in elist:
                        elist.append((v1, v2))
                self.edge_indices.append(elist)
                self.edge_coords.append([(self.vertex_coords[x], self.vertex_coords[y])
                                         for x, y in elist])
        self.num_edges = sum([len(elist) for elist in self.edge_indices])

    def get_faces(self):
        """
        Basically speaking, for a pair (i, j), the composition of the i-th and the j-th
        reflection is a rotation which fixes a base face `f0` of type `ij`. But there
        are some cases need be considered:

        1. The i-th and the j-th mirror are both active: in this case the rotation indeed
           generates a face `f0` and edges of type `i` and type `j` occur alternatively in it.

        2. Exactly one of the i-th and the j-th mirror is active: in this case we should check
           whether their reflections commute or not: the rotation generates a face `f0` only when
           these two reflections do not commute, and `f0` contains edges of only one type.

        3. Neither of them is active: in this case there are no faces.
        """
        for i, j in combinations(self.symmetry_gens, 2):
            # the base face that contains the initial vertex
            f0 = []
            if self.active[i] and self.active[j]:
                fgens = [(i, j)]
                for k in range(self.coxeter_matrix[i][j]):
                    f0.append(self._move(0, (i, j)*k))
                    f0.append(self._move(0, (j,) + (i, j)*k))
            elif self.active[i] and self.coxeter_matrix[i][j] > 2:
                fgens = [(i, j), (i,)]
                for k in range(self.coxeter_matrix[i][j]):
                    f0.append(self._move(0, (i, j)*k))
            elif self.active[j] and self.coxeter_matrix[i][j] > 2:
                fgens = [(i, j), (j,)]
                for k in range(self.coxeter_matrix[i][j]):
                    f0.append(self._move(0, (i, j)*k))
            else:
                continue

            ftable = CosetTable(self.symmetry_gens, self.symmetry_rels, fgens)
            ftable.run()
            words = ftable.get_words()
            flist = []
            for word in words:
                f = tuple(self._move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)
            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[x] for x in face) for face in flist])

        self.num_faces = sum([len(flist) for flist in self.face_indices])

    def _transform(self, vector, word):
        """Transform a vector by a word in the symmetry group."""
        for w in word:
            vector = np.dot(vector, self._reflections[w])
        return vector

    def _move(self, vertex, word):
        """
        Transform a vertex by a word in the symmetry group.
        Return the index of the resulting vertex.
        """
        for w in word:
            vertex = self._vtable[vertex][w]
        return vertex

    def export_pov(self, filename):
        raise NotImplementedError

    def get_word_representations(self, symbol=r"\rho", cols=3, snub=False):
        """
        Return the words corresponding to the vertices in latex format.
        `cols` is the number of columns in the array.
        """
        def to_latex(word):
            if not word:
                return "e"
            else:
                if snub:
                    return "".join(symbol + "_{{{}}}".format(i//2) for i in word)
                else:
                    return "".join(symbol + "_{{{}}}".format(i) for i in word)

        latex = ""
        for i, word in enumerate(self._vwords):
            if i > 0 and i % cols == 0:
                latex += r"\\"
            latex += to_latex(word)
            if i % cols != cols - 1:
                latex += "&"

        return r"\begin{{array}}{{{}}}{}\end{{array}}".format("l"*cols, latex)


class Polyhedra(BasePolytope):

    def __init__(self, upper_triangle, init_dist):
        if not len(upper_triangle) == len(init_dist) == 3:
            raise ValueError("Three integers and three floats are required")

        super().__init__(upper_triangle, init_dist)

    def export_pov(self, filename="./povray/polyhedra-data.inc"):
        vstr = "Vertex({})\n"
        estr = "Edge({}, {})\n"
        fstr = "Face({}, {}, vertices_list)\n"
        with open(filename, "w") as f:
            for v in self.vertex_coords:
                f.write(vstr.format(helpers.pov_vector(v)))

            for i, edge_list in enumerate(self.edge_coords):
                for edge in edge_list:
                    f.write(estr.format(i, helpers.pov_vector_list(edge)))

            for i, face_list in enumerate(self.face_coords):
                for face in face_list:
                    f.write(helpers.pov_array(face))
                    f.write(fstr.format(i, len(face)))


class Snub(Polyhedra):
    """
    A snub polyhedra is generated by the subgroup that consists of only rotations
    in the full symmetry group. This subgroup has presentation
        <r, s | r^p = s^q = (rs)^2 = 1>
    where r = ρ0ρ1, s = ρ1ρ2 are two rotations.
    Again we solve all words in this subgroup and then use them to transform an
    initial vertex to get all vertices.
    """

    def __init__(self, upper_triangle, init_dist=(1.0, 1.0, 1.0)):
        super().__init__(upper_triangle, init_dist)

        self.symmetry_gens = (0, 1, 2, 3)
        self.symmetry_rels = ((0,) * self.coxeter_matrix[0][1],
                              (2,) * self.coxeter_matrix[1][2],
                              (0, 2) * self.coxeter_matrix[0][2],
                              (0, 1), (2, 3))
        self.rotations = {(0,): self.coxeter_matrix[0][1],
                          (2,): self.coxeter_matrix[1][2],
                          (0, 2): self.coxeter_matrix[0][2]}

    def get_vertices(self):
        self._vtable = CosetTable(self.symmetry_gens, self.symmetry_rels, coxeter=False)
        self._vtable.run()
        self._vwords = self._vtable.get_words()
        self.num_vertices = len(self._vwords)
        self.vertex_coords = tuple(self._transform(self.init_v, w) for w in self._vwords)

    def get_edges(self):
        for rot in self.rotations:
            elist = []
            e0 = (0, self._move(0, rot))
            for word in self._vwords:
                e = tuple(self._move(v, word) for v in e0)
                if e not in elist and e[::-1] not in elist:
                    elist.append(e)
            self.edge_indices.append(elist)
            self.edge_coords.append([(self.vertex_coords[i], self.vertex_coords[j]) for i, j in elist])
        self.num_edges = sum(len(elist) for elist in self.edge_indices)

    def get_faces(self):
        orbits = (tuple(self._move(0, (0,) * k) for k in range(self.rotations[(0,)])),
                  tuple(self._move(0, (2,) * k) for k in range(self.rotations[(2,)])),
                  (0, self._move(0, (2,)), self._move(0, (0, 2))))
        for f0 in orbits:
            flist = []
            for word in self._vwords:
                f = tuple(self._move(v, word) for v in f0)
                if not helpers.check_duplicate_face(f, flist):
                    flist.append(f)
            self.face_indices.append(flist)
            self.face_coords.append([tuple(self.vertex_coords[v] for v in face) for face in flist])

        self.num_faces = sum([len(flist) for flist in self.face_indices])

    def _transform(self, vertex, word):
        for g in word:
            if g == 0:
                vertex = np.dot(vertex, self._reflections[0])
                vertex = np.dot(vertex, self._reflections[1])
            else:
                vertex = np.dot(vertex, self._reflections[1])
                vertex = np.dot(vertex, self._reflections[2])
        return vertex


class Polychora(BasePolytope):

    def __init__(self, upper_triangle, init_dist):
        if not len(upper_triangle) == 6 and len(init_dist) == 4:
            raise ValueError("Six integers and four floats are required")

        super().__init__(upper_triangle, init_dist)

    def export_pov(self, filename="./povray/polychora-data.inc"):
        vstr = "Vertex({})\n"
        estr = "Edge({}, {})\n"

        extent = np.max([np.linalg.norm(helpers.proj3d(v)) for v in self.vertex_coords])

        with open(filename, "w") as f:
            f.write("#declare extent = {};\n".format(extent))

            for v in self.vertex_coords:
                f.write(vstr.format(helpers.pov_vector(v)))

            for i, edge_list in enumerate(self.edge_coords):
                for edge in edge_list:
                    f.write(estr.format(i, helpers.pov_vector_list(edge)))

            for i, face_list in enumerate(self.face_coords):
                for face in face_list:
                    isplane, center, radius, facesize = helpers.get_sphere_info(face)
                    f.write(helpers.pov_array(face))
                    f.write(helpers.export_face(i, face, isplane, center,
                                                radius, facesize))
