

import CGData.BaseTable

class Bed(CGData.BaseTable.BaseTable):

    __format__ = {
        "name" : "bed",
        "type" : "type",
        "form" : "table",
        "columnOrder" : 
        [
            "chrom",
            "chrom_start",
            "chrom_end",
            "name",
            "score",
            "strand",
            "thick_start",
            "thick_end",
            "item_rgb",
            "block_count",
            "block_sizes",
            "block_starts",
        ],
        "primaryKey" : "probeName",
        "columnDef" : {
            "chrom_start" : { 'type' : 'int' }
        }
    }

    def __init__(self):
        CGData.BaseTable.BaseTable.__init__(self)
