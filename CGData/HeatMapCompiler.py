
import sys
import os
from glob import glob
import json
from copy import copy
import CGData
import CGData.CGZ

from CGData.SQLUtil import *

from CGData import log, error, warn
import re

CREATE_COL_DB = """
CREATE TABLE `%s` (
  `id` int(10) unsigned NOT NULL PRIMARY KEY AUTO_INCREMENT,
  `name` varchar(255) NOT NULL UNIQUE,
  `shortLabel` varchar(255) default NULL,
  `longLabel` varchar(255) default NULL,
  `valField` varchar(255) default NULL,
  `clinicalTable` varchar(255) default NULL,
  `priority` float default NULL,
  `filterType` varchar(255) default NULL,
  `visibility` varchar(255) default NULL,
  `groupName` varchar(255) default NULL
) engine 'MyISAM';
"""

    
CREATE_BED = """
CREATE TABLE %s (
    id int unsigned not null primary key auto_increment,
    chrom varchar(255) not null,
    chromStart int unsigned not null,
    chromEnd int unsigned not null,
    name varchar(255) not null,
    score int not null,
    strand char(1) not null,
    thickStart int unsigned not null,
    thickEnd int unsigned not null,
    reserved int unsigned  not null,
    blockCount int unsigned not null,
    blockSizes longblob not null,
    chromStarts longblob not null,
    expCount int unsigned not null,
    expIds longblob not null,
    expScores longblob not null,
    INDEX(name(16)),
    INDEX(chrom(5),id)
) engine 'MyISAM';
"""

dataSubTypeMap = {
    'cna': 'CNV',
    'geneExp': 'expression',
    'SNP': 'SNP',
    'RPPA': 'RPPA',
    'DNAMethylation' : 'DNAMethylation'
    }


class CGIDTable(object):
    
    def __init__(self):
        self.id_table = {}
    
    def get( self, itype, iname ):
        if itype not in self.id_table:
            self.id_table[ itype ] = {}
        if iname not in self.id_table[ itype ]:
            self.id_table[ itype ][ iname ] = len( self.id_table[ itype ] )
            
        return self.id_table[ itype ][ iname ]



class CGGroupMember(object):
    pass

class CGGroupBase(object):

    DATA_FORM = None

    def __init__(self, group_name):
        self.members = {}
        self.name = group_name
    
    def __setitem__(self, name, item):
        self.members[ name ] = item
    
    def __getitem__(self, name):
        return self.members[ name ]
    
    def put(self, obj):
        self.members[ obj.get_name() ] = obj
    
    def is_link_ready(self):
        for name in self.members:
            if not self.members[name].is_link_ready():
                return False
        return True
    
    def get_name(self):
        return self.name
    
    def unload(self):
        for name in self.members:
            self.members[name].unload()
    
    def lookup(self, **kw):
        for elem in self.members:
            found = True
            obj = self.members[ elem ]
            for key in kw:
                if obj.get( key, None ) != kw[key] and obj.get( ":" + key, None ) != kw[key]:
                    found = False
            if found:
                return obj
                    
    
    def get_link_map(self):
        out = {}
        for name in self.members:
            lmap = self.members[ name ].get_link_map()
            for ltype in lmap:
                if ltype not in out:
                    out[ ltype ] = []
                for lname in lmap[ltype]:
                    if lname not in out[ltype]:
                        out[ltype].append( lname )
        return out
    

class BrowserCompiler(object):
    
    PARAMS = [ "compiler.mode" ]

    def __init__(self,data_set,params={}):
        import CGData.ClinicalFeature
        self.out_dir = "out"
        self.params = params
        self.set_hash = data_set

        # Create a default null clinicalFeature, to coerce creation of a TrackClinical merge object.
        #if not 'clinicalFeature' in self.set_hash:
        #    self.set_hash['clinicalFeature'] = {}
        #self.set_hash['clinicalFeature']['__null__'] = CGData.ClinicalFeature.NullClinicalFeature()

        #if 'binary' in self.params and self.params['binary']:
        #    CGData.OBJECT_MAP['trackGenomic'] = ('CGData.TrackGenomic', 'BinaryTrackGenomic')

    
    def link_objects(self):
        """
        Scan found object records and determine if the data they link to is
        avalible
        """    
        
        self.id_table = CGIDTable()

        for gmatrix_name in self.set_hash[ 'genomicMatrix' ]:
            gmatrix = self.set_hash['genomicMatrix'][gmatrix_name]
            id_lmap =  self.set_hash.get_linked_data( 'id', gmatrix.get_link_map()['id'][0] )
                        
            print gmatrix.get_name(), id_lmap['idMap'], id_lmap.keys()
            
            tg = TrackGenomic()
            tg.merge( 
                genomicMatrix=gmatrix, 
                idMap=id_lmap['idMap'].values()[0], 
                clinicalMatrix=id_lmap['clinicalMatrix'].values()[0]
            )
            
            probe_lmap = self.set_hash.get_linked_data( 'probe', gmatrix.get_link_map()['probe'][0] )
            tg.merge(
                probeMap = probe_lmap['probeMap'].values()[0],
                aliasMap = probe_lmap['aliasMap'].values()[0]                
            )
            
            print "Generate", tg.get_type(), tg.get_name()
            shandle = tg.gen_sql(self.id_table)
            if shandle is not None:
                ohandle = open( os.path.join( self.out_dir, "%s.%s.sql" % (tg.get_type(), tg.get_name() ) ), "w" )
                for line in shandle:
                    ohandle.write( line )
                ohandle.close()
                
        
        return
        
        #Check objects for their dependencies
        ready_matrix = {}
        for stype in ['genomicMatrix', 'clinicalMatrix', 'clinicalFeature', 'idMap']:
            for sname in self.set_hash[ stype ]:
                print "check linking:", stype, sname
                sobj = self.set_hash[ stype ][ sname ]
                lmap = sobj.get_link_map()
                is_ready = True
                for ltype in lmap:
                    if ltype not in self.set_hash:
                        warn( "%s missing data type %s" % (sname, ltype) )
                        is_ready = False
                    else:
                        for lname in lmap[ ltype ]:
                            if lname not in self.set_hash[ltype]:
                                warn( "%s %s missing data %s %s" % ( stype, sname, ltype, lname ) )
                                is_ready = False
                if not sobj.is_link_ready():
                    warn( "%s %s not LinkReady" % ( stype, sname ) )
                elif is_ready:
                    print "READY", stype, sname
                    if not stype in ready_matrix:
                        ready_matrix[ stype ] = {}
                    ready_matrix[ stype ][ sname ] = sobj
                
                
        for rtype in ready_matrix:
            log( "READY %s: %s" % ( rtype, ",".join(ready_matrix[rtype].keys()) ) )         

        for dType in ready_matrix:
            log("Found %s %d" % (dType, len(ready_matrix[dType])))
            
        merge_children = {}

        for merge_type in [TrackClinical, TrackGenomic]:
            select_types = merge_type.typeSet
            select_set = {}
            try:
                for stype in select_types:
                    select_set[ stype ] = ready_matrix[ stype ] 
                    if stype not in merge_children:
                        merge_children[stype] = {}
            except KeyError:
                error("missing data type %s" % (stype) )
                continue
            mobjlist = self.set_enumerate( merge_type, select_set )
            print mobjlist
            for mobj in mobjlist:
                if merge_type not in ready_matrix:
                    ready_matrix[ merge_type.type_name ] = {}
                for cType in mobj.members:
                    merge_children[cType][mobj.members[cType].get_name()] = True
                ready_matrix[ merge_type.type_name ][ mobj.get_name() ] = mobj
        
        self.compile_matrix = {}
        for sType in ready_matrix:
            self.compile_matrix[sType] = {}
            for name in ready_matrix[sType]:
                if sType not in merge_children or name not in merge_children[sType]:
                    self.compile_matrix[sType][name] = ready_matrix[sType][name]
       
        log("After Merge")
        for dType in ready_matrix:
            log("Found %s %d" % (dType, len(self.compile_matrix[dType])))
        
    def set_enumerate( self, merge_type, a, b={} ):
        """
        This is an recursive function to enumerate possible sets of elements in the 'a' hash
        a is a map of types ('probeMap', 'clinicalMatrix', ...), each of those is a map
        of cgBaseObjects that report get_link_map requests
        """
        cur_key = None
        for t in a:
            if not t in b:
                cur_key = t
        
        if cur_key is None:
            #make sure selected subgraph is connected
            #start by building a graph of connections
            #and map of connected nodes
            cMap = {}
            lMap = {}
            for c in b:
                n = "%s:%s" % (c, b[c].get_name())
                cMap[ n ] = False
                lMap[n] = {}
                for d in b[c].get_link_map():
                    for e in b[c].get_link_map()[d]:
                        m = "%s:%s" % (d,e)
                        lMap[n][m] = True
            #add the first node to the connected set
            cMap[ cMap.keys()[0] ] = True
            found = True
            #continue adding nodes to the connected set, until no more can be found
            while found:
                found = False
                for c in cMap:
                    if not cMap[c]:
                        for d in cMap:
                            if cMap[d]:
                                if d in lMap[c] or c in lMap[d]:
                                    found = True
                                    cMap[c] = True
                                    cMap[d] = True
            
            #if there are no disconnected nodes, then the subset represents a connected graph,
            #and is ready to merge
            if cMap.values().count(False) == 0:
                log( "Merging %s" % ",".join( ( "%s:%s" %(c,b[c].get_name()) for c in b) ) )  
                mergeObj = merge_type()
                mergeObj.merge( **b )
                return [ mergeObj ]
        else:
            out = []
            for i in a[cur_key]:
                c = copy(b)
                sobj = a[cur_key][i] #the object selected to be added next
                lmap = sobj.get_link_map()
                valid = True
                for ltype in lmap:
                    if ltype in c:
                        if c[ltype].get_name() not in lmap[ltype]:
                            valid = False
                for stype in c:
                    slmap = c[stype].get_link_map()
                    for sltype in slmap:
                        if cur_key == sltype:
                            if sobj.get_name() not in slmap[sltype]:
                                valid = False
                if valid:
                    c[ cur_key ] = sobj
                    out.extend( self.set_enumerate( merge_type, a, c ) )
            return out
        return []
    
    def __iter__(self):
        return self.compile_matrix.__iter__()
        
    def __getitem__(self, item):
        return self.compile_matrix[item]

    def gen_sql_base(self):
        if "compiler.mode" in self.params and self.params[ "compiler.mode" ] == "scan":
            return
        log( "Writing SQL " + mode  )     
        if not os.path.exists(self.out_dir):
            os.makedirs(self.out_dir)
        self.id_table = CGIDTable()
       
        
        for rtype in self.compile_matrix:
            for rname in self.compile_matrix[ rtype ]:
                if hasattr(self.compile_matrix[ rtype ][ rname ], "gen_sql_" + mode):
                    sql_func = getattr(self.compile_matrix[ rtype ][ rname ], "gen_sql_" + mode)
                    shandle = sql_func(self.id_table)
                    if shandle is not None:
                        ohandle = open( os.path.join( self.out_dir, "%s.%s.sql" % (rtype, rname ) ), "w" )
                        for line in shandle:
                            ohandle.write( line )
                        ohandle.close()
                    #tell the object to unload data, so we don't continually allocate over the compile
                    self.compile_matrix[ rtype ][ rname ].unload()
    
    


    def feature_type_setup(self, types = {}):
        if self.light_mode:
            self.load()

        self.float_map = {}
        self.enum_map = {}
        for key in self.col_list:
            # get unique list of values by converting to a set & back.
            # also, drop null values.
            values = list(set([v for v in self.column(key) if v not in ["null", "None", "NA"] and v is not None and len(v)]))

            if not key in types:
                types[key] = self.__guess_type__(values)

            if len(values) > 0: # drop empty columns. XXX is this correct behavior?
                if types[key] == ['float']:
                    self.float_map[key] = True
                else:
                    self.enum_map[key] = dict((enum, order) for enum, order in zip(sorted(values), range(len(values))))

        id_map = {}
        id_num = 0
        prior = 1
        self.col_order = []
        self.orig_order = []    

        for name in self.float_map:
            id_map[ name ] = id_num
            id_num += 1    
            colName = col_fix( name )
            self.col_order.append( colName )
            self.orig_order.append( name )
            
        for name in self.enum_map:        
            id_map[ name ] = id_num
            id_num += 1    
            colName = col_fix( name )
            self.col_order.append( colName )
            self.orig_order.append( name )
    
   


class TrackClinical:
    type_name = "trackClinical"
    DATA_FORM = None

    typeSet = { 
        'clinicalMatrix' : True, 
        'clinicalFeature' : True
    } 

    def __init__(self):
        self.members = {}

    def merge(self, **kw):
        for k in kw:
            if k in self.typeSet:
                self.members[k] = kw[k]
    
    def get_name( self ):
        return "%s" % ( self.members[ "clinicalMatrix" ].get_name() )

    def gen_sql_clinicalMatrix(self, id_table, features=None):
        CGData.log( "Writing Clinical %s SQL" % (self['name']))
        
        if features == None:
            self.feature_type_setup()

        table_name = self['name']
        clinical_table = 'clinical_' + table_name
        yield "drop table if exists %s;" % ( clinical_table )


        yield """
CREATE TABLE clinical_%s (
\tsampleID int,
\tsampleName ENUM ('%s')""" % ( table_name, "','".join(map(lambda s: sql_fix(s), sortedSamples(self.row_hash.keys()))) )

        for col in self.col_order:
            if ( self.enum_map.has_key( col ) ):
                yield ",\n\t`%s` ENUM( '%s' ) default NULL" % (col.strip(), "','".join( sql_fix(a) for a in sorted(self.enum_map[ col ].keys(), lambda x,y: self.enum_map[col][x]-self.enum_map[col][y]) ) )
            else:
                yield ",\n\t`%s` FLOAT default NULL" % (col.strip())
        yield """
    ) engine 'MyISAM';
    """

        for target in sortedSamples(self.row_hash.keys()):
            a = []
            for col in self.orig_order:
                val = self.row_hash[ target ][ self.col_list[ col ] ]
                if val is None or val == "null" or len(val) == 0 :
                    a.append("\\N")
                else:
                    a.append( "'" + sql_fix(val) + "'" )
            yield u"INSERT INTO %s VALUES ( %d, '%s', %s );\n" % ( clinical_table, id_table.get( table_name + ':sample_id', target ), sql_fix(target), u",".join(a) )


        yield "DELETE from colDb where clinicalTable = '%s';" % clinical_table

        yield "INSERT INTO colDb(name, shortLabel,longLabel,valField,clinicalTable,filterType,visibility,priority) VALUES( '%s', '%s', '%s', '%s', '%s', '%s', 'on',1);\n" % \
                ( 'sampleName', 'sample name', 'sample name', 'sampleName', clinical_table, 'coded' )

        i = 0;
        for name in self.col_order:
            shortLabel = name if name not in features or 'shortTitle' not in features[name] else features[name]['shortTitle'][0]
            longLabel = name if name not in features or 'longTitle' not in features[name] else features[name]['longTitle'][0]
            filter = 'coded' if self.enum_map.has_key(name) else 'minMax'
            visibility = ('on' if i < 10 else 'off') if name not in features or 'visibility' not in features[name] else features[name]['visibility'][0]
            priority = 1 if name not in features or 'priority' not in features[name] else float(features[name]['priority'][0])
            yield "INSERT INTO colDb(name, shortLabel,longLabel,valField,clinicalTable,filterType,visibility,priority) VALUES( '%s', '%s', '%s', '%s', '%s', '%s', '%s', %f);\n" % \
                    ( sql_fix(name), sql_fix(shortLabel), sql_fix(longLabel), sql_fix(name), "clinical_" + table_name, filter, visibility, priority)
            i += 1

    def gen_sql_clinicalTrack(self, id_table):
        CGData.log("ClincalTrack SQL " + self.get_name())

        features = self.members["clinicalFeature"].features
        matrix = self.members["clinicalMatrix"]

        # e.g. { 'HER2+': 'category', ...}
        explicit_types = dict((f, features[f]['valueType']) for f in features if 'valueType' in features[f])

        matrix.feature_type_setup(explicit_types)
        for a in features:
            if "stateOrder" in features[a]:

                enums = [x for x in csv.reader(features[a]["stateOrder"], skipinitialspace=True)][0]
                i = 0
                for e in matrix.enum_map[a]:
                    if e in enums:
                        matrix.enum_map[a][e] = enums.index(e)
                    else:
                        matrix.enum_map[a][e] = len(enums) + i
                        i += 1
        for a in matrix.gen_sql_heatmap(id_table, features=features):
            yield a

    


class TrackGenomic:
    type_name = "trackGenomic"

    DATA_FORM = None

    typeSet = {
        'clinicalMatrix' : True,
        'genomicMatrix' : True,
        'sampleMap' : True,
        'probeMap' : True,
        'aliasMap' : True
    }

    format = "bed 15"

    def __init__(self):
        self.members = {}

    def merge(self, **kw):
        for k in kw:
            if k in self.typeSet:
                self.members[k] = kw[k]
        
            
    def get_name( self ):
        return "%s" % ( self.members[ "genomicMatrix" ].get_name() )
    
    def get_type( self ):
        return 'trackGenomic'

    def scores(self, row):
        return "'%s'" % (','.join( str(a) for a in row ))

    def gen_sql(self, id_table):
        #scan the children
        # XXX Handling of sql for children is broken if the child may appear
        # as part of multiple merge objects, such as TrackGenomic and TrackClinical.
        # A disgusting workaround for clinicalMatrix is to prevent the TrackGenomic from calling
        # it for gen_sql.
        clinical = self.members.pop("clinicalMatrix")
        
        self.members["clinicalMatrix"] = clinical

        gmatrix = self.members[ 'genomicMatrix' ]
        pmap = self.members[ 'probeMap' ] # BUG: hard coded to only producing HG18 tables
        if pmap is None:
            CGData.error("Missing HG18 %s" % ( self.members[ 'probeMap'].get_name() ))
            return
        
        table_base = self.get_name()
        CGData.log("Writing Track %s" % (table_base))
        
        clinical_table_base =  self.members[ "clinicalMatrix" ].get_name()

        yield "DELETE from raDb where name = '%s';\n" % ("genomic_" + table_base)
        yield "INSERT into raDb( name, sampleTable, clinicalTable, columnTable, aliasTable, shortLabel, longLabel, expCount, dataType, platform, profile, security, priority, gain, groupName, wrangler, url, article_title, citation, author_list, wrangling_procedure) VALUES ( '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%d', '%s', '%s', '%s', '%s', %f, %f, '%s', %s, %s, %s, %s, %s, %s);\n" % \
            ( "genomic_" + table_base, "sample_" + table_base,
                "clinical_" + clinical_table_base, "colDb",
                "genomic_" + table_base + "_alias",
                sql_fix(gmatrix['shortTitle']),
                sql_fix(gmatrix['longTitle']),
                len(gmatrix.get_sample_list()),
                self.format,
                dataSubTypeMap[gmatrix.get_data_subtype()],
                'localDb',
                'public',
                float(gmatrix.get('priority', 1.0)),
                float(gmatrix.get('gain', 1.0)),
                sql_fix(gmatrix.get('groupTitle', 'Misc.')),
                "'%s'"%sql_fix(gmatrix['wrangler']) if 'wrangler' in gmatrix else '\N',
                "'%s'"%sql_fix(gmatrix['url']) if 'url' in gmatrix else '\N',
                "'%s'"%sql_fix(gmatrix['articleTitle']) if 'articleTitle' in gmatrix else '\N',
                "'%s'"%sql_fix(gmatrix['citation']) if 'citation' in gmatrix else '\N',
                "'%s'"%sql_fix(gmatrix['dataProducer']) if 'dataProducer' in gmatrix else '\N',
                "'%s'"%sql_fix(gmatrix['wrangling_procedure']) if 'wrangling_procedure' in gmatrix else '\N',
                )
        
        # write out the sample table
        yield "drop table if exists sample_%s;" % ( table_base )
        yield """
CREATE TABLE sample_%s (
    id           int,
    sampleName   varchar(255)
) engine 'MyISAM';
""" % ( table_base )

        from CGData.ClinicalMatrix import sortedSamples
        for sample in sortedSamples(gmatrix.get_sample_list()):
	    yield "INSERT INTO sample_%s VALUES( %d, '%s' );\n" % ( table_base, id_table.get( clinical_table_base + ':sample_id', sample), sql_fix(sample) )

        
        yield "drop table if exists genomic_%s_alias;" % ( table_base )
        yield """
CREATE TABLE genomic_%s_alias (
    name        varchar(255),
    alias         varchar(255)
) engine 'MyISAM';
""" % ( table_base )

        for aliasList in self.members['aliasMap'].get_probe_values():
            for alias in aliasList:
                yield "insert into genomic_%s_alias( name, alias ) values( '%s', '%s' );\n" % (table_base, sql_fix(alias.probe), sql_fix(alias.alias))

        # write out the BED table
        yield "drop table if exists %s;" % ( "genomic_" + table_base )
        yield CREATE_BED % ( "genomic_" + table_base + "_tmp")
        
        sample_ids = []
        samples = gmatrix.get_sample_list()

        # sort samples by sample_id, and retain the sort order for application to the genomic data, below
        tmp=sorted(zip(samples, range(len(samples))), cmp=lambda x,y: id_table.get(clinical_table_base + ':sample_id', x[0]) - id_table.get( clinical_table_base + ':sample_id', y[0]))
        samples, order = map(lambda t: list(t), zip(*tmp))

        for sample in samples:
            sample_ids.append( str( id_table.get( clinical_table_base + ':sample_id', sample ) ) )
        
        exp_ids = ','.join( sample_ids )
        missingProbeCount = 0
        for probe_name in gmatrix.get_probe_list():
            # get the genomic data and rearrange to match the sample_id order
            tmp = gmatrix.get_row( probe_name )
            row = map(lambda i: tmp[order[i]], range(len(tmp)))
            #pset = pmap.get_by_probe( probe_name )
            probe = None
            try:
                probe = pmap.get_by_probe( probe_name )
            except KeyError:
                pass
            if probe is not None:
                #for probe in pset:
                    istr = "insert into %s(chrom, chromStart, chromEnd, strand,  name, expCount, expIds, expScores) values ( '%s', '%s', '%s', '%s', '%s', '%s', '%s', %s );\n" % \
                            ( "genomic_%s_tmp" % (table_base), probe.chrom, probe.chrom_start, probe.chrom_end, probe.strand, sql_fix(probe_name), len(sample_ids), exp_ids, self.scores(row) )
                    yield istr
            else:
                missingProbeCount += 1
        yield "# sort file by chrom position\n"
        yield "create table genomic_%s like genomic_%s_tmp;\n" % (table_base, table_base)
        yield "insert into genomic_%s select * from genomic_%s_tmp order by chrom, chromStart;\n" % (table_base, table_base)
        yield "drop table genomic_%s_tmp;\n" % table_base
        CGData.log("%s Missing probes %d" % (table_base, missingProbeCount))

    def unload(self):
        for t in self.members:
            self.members[t].unload()

    


class BinaryTrackGenomic(TrackGenomic):
    format = 'bed 15b'
    def scores(self, row):
        return  "x'%s'" % (''.join( binascii.hexlify(struct.pack('f', a)) for a in row ))
