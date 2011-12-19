
import csv
import CGData
import math
from copy import copy
try:
    import numpy
except ImportError:
    numpy = None

class BaseMatrix(CGData.CGDataMatrixObject):
    
    element_type = str
    null_type = None
    def __init__(self):
        CGData.CGDataMatrixObject.__init__(self)
        self.free()
        if self.__format__["valueType"] == 'float':
            self.element_type = float

    def free(self):
        self.col_map = {}
        self.row_map = {}    
        self.matrix = None

    def read(self, handle, skip_vals=False):
        self.col_map = {}
        self.row_map = {}    
        pos_hash = None

        if numpy is not None:
            txtMatrix = numpy.loadtxt(handle, delimiter="\t", dtype=str)
            txtMatrix[ txtMatrix=="NA" ] = 'nan'
            self.matrix = numpy.matrix(txtMatrix[1:,1:], dtype=self.element_type)
            for i, col in enumerate( txtMatrix[0,1:] ):
                self.col_map[col] = i
            for i, row in enumerate( txtMatrix[1:,0] ):
                self.row_map[row] = i
        else:
            self.matrix = []
            for row in csv.reader(handle, delimiter="\t"):
                if pos_hash is None:
                    pos_hash = {}
                    pos = 0
                    for name in row[1:]:
                        i = 1
                        orig_name = name
                        while name in pos_hash:
                            name = orig_name + "#" + str(i)
                            i += 1
                        pos_hash[name] = pos
                        pos += 1
                else:
                    newRow = []
                    if not skip_vals:                    
                        newRow = [self.null_type] * (len(pos_hash))
                        for col in pos_hash:
                            i = pos_hash[col] + 1
                            if row[i] != 'NA' and row[i] != 'null' and row[i] != 'NONE' and row[i] != "N/A" and len(row[i]):
                                newRow[i - 1] = self.element_type(row[i])
                    self.row_map[row[0]] = len(self.matrix)
                    self.matrix.append(newRow)

            self.col_map = {}
            for col in pos_hash:
                self.col_map[col] = pos_hash[col]

    def write(self, handle, missing='NA'):
        write = csv.writer(handle, delimiter="\t", lineterminator='\n')
        col_list = self.get_col_list()
        
        write.writerow([self.corner_name] + col_list)
        for rowName in self.row_map:
            out = [probe]
            row = self.get_row(rowName)
            for col in col_list:
                val = row[self.col_map[col]]
                if val == self.null_type or val is None or (type(val)==float and math.isnan(val)):
                    val = missing
                out.append(val)
            write.writerow(out)
    
    def read_keyset(self, handle, key_predicate):
        if key_predicate == "rowKeySrc":
            reader = csv.reader( handle, delimiter="\t")
            head = None
            for row in reader:
                if head is None:
                    head = row
                else:
                    yield row[0]
        
        if key_predicate=="columnKeySrc":
            reader = csv.reader( handle, delimiter="\t")
            head = None
            for row in reader:
                for col in row[1:]:
                    yield col
                break
                
    def get_col_namespace(self):
        """
        Return the name of the column namespace
        """
        return self.get("colNamespace", None)

    def get_row_namespace(self):
        """
        Return the name of the row namespace
        """
        return self.get("rowNamespace", None)
        
    def get_col_list(self):
        """
        Returns names of columns
        """
        if not self.loaded:
            self.load( )
        out = self.col_map.keys()
        out.sort( lambda x,y: self.col_map[x]-self.col_map[y])
        return out 
        
    def get_row_list(self):
        """
        Returns names of rows
        """
        out = self.row_map.keys()
        out.sort( lambda x,y: self.row_map[x]-self.row_map[y])
        return out 
    
    def get_row_pos(self, row):
        return self.row_map[row]
    
    def get_col_pos(self, col):
        return self.col_map[col]
    
    def get_row_count(self):
        return len(self.row_map)
        
    def get_col_count(self):
        return len(self.col_map)
    
    def get_row(self, row_name):
        if not self.loaded:
            self.load( )
        if isinstance(self.matrix, list):
            return self.matrix[ self.row_map[row_name] ]
        else:
            return self.matrix[ self.row_map[row_name] ].tolist()[0]
    def get_col(self, col_name):
        if not self.loaded:
            self.load( )
        if isinstance(self.matrix, list):
            out = []
            for row_name in self.get_row_list():
                out.append( self.get_val(col_name, row_name) )
            return out
        else:
            return self.matrix[:,self.col_map[col_name]].reshape(-1).tolist()[0]
    
    def get_val(self, col_name, row_name):
        if isinstance(self.matrix, list):
            return self.matrix[self.row_map[row_name]][self.col_map[col_name]]
        return self.matrix[self.row_map[row_name],self.col_map[col_name]]
    
    def add(self, col, row, value):
        """
        Put a value into particular cell, adding new 
        columns or rows if needed
        
        col -- name of column
        row -- name of column
        value -- value to be inserted
        """
        if not col in self.col_list:
            self.col_list[col] = len(self.col_list)
            for r in self.row_hash:
                self.row_hash[r].append(self.null_type)

        if not row in self.row_hash:
            self.row_hash[row] = [self.null_type] * (len(self.col_list))

        self.row_hash[row][self.col_list[col]] = value

    def join(self, matrix):
        """
        Insert values from matrix into the current matrix
        """
        for sample in matrix.sample_list:
            if not sample in self.sample_list:
                self.sample_list[sample] = len(self.sample_list)
                for probe in self.row_hash:
                    self.row_hash[probe].append(self.null_type)
            for probe in matrix.row_hash:
                if not probe in self.row_hash:
                    self.row_hash[probe] = [self.null_type] * (len(self.sample_list))
                self.row_hash[probe][self.sample_list[sample]] = \
                matrix.row_hash[probe][matrix.sample_list[sample]]

