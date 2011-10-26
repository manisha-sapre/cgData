import unittest
import os

import subprocess
import shutil
import MySQLdb
import MySQLSandbox

class TestCase(unittest.TestCase):
    """Test sample ordering in output tables"""
    tolerance = 0.001 # floating point tolerance

    @classmethod
    def setUpClass(cls):
        try:
            shutil.rmtree('out')
        except:
            pass
        cls.sandbox = MySQLSandbox.Sandbox()
        db = MySQLdb.connect(read_default_file=cls.sandbox.defaults)
        cls.c = db.cursor()
        # create raDb and hg18
        cls.c.execute("""
create database hg18;
use hg18;

CREATE TABLE raDb (
    name varchar(255),  # Table name for genomic data
    downSampleTable varchar(255),       # Down-sampled table
    sampleTable varchar(255),   # Sample table
    clinicalTable varchar(255), # Clinical table
    columnTable varchar(255),   # Column table
    shortLabel varchar(255),    # Short label
    longLabel varchar(255),     # Long label
    expCount int unsigned,      # Number of samples
    groupName varchar(255),     # Group name
    microscope varchar(255),    # hgMicroscope on/off flag
    aliasTable varchar(255),    # Probe to gene mapping
    dataType varchar(255),      # data type (bed 15)
    platform varchar(255),      # Expression, SNP, etc.
    security varchar(255),      # Security setting (public, private)
    profile varchar(255),       # Database profile
    PRIMARY KEY(name)
);""")
        while cls.c.nextset() is not None: pass

        cmd = '../scripts/compileCancerData.py data_numeric_enum; cat out/* | mysql --defaults-file=%s hg18;' % cls.sandbox.defaults
        f = open('test.log', 'a')
        p = subprocess.Popen(cmd, shell=True, stdout=f, stderr=f)
        p.communicate()
        f.close()
        if p.returncode != 0:
            raise subprocess.CalledProcessError(p.returncode, cmd)

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.shutdown()

    def test_clinical(self):
        """Test enum order in the clinical table"""
        self.c.execute("""select sampleName, `HER2+` from clinical_test order by `HER2+`, sampleName""")
        rows = self.c.fetchall()
        self.assertEqual(len(rows), 6)          # six samples
        self.assertEqual(rows[0], ( 'sample1', '0' ) ) # sample name is sample1
        self.assertEqual(rows[1], ( 'sample2', '0' ) )
        self.assertEqual(rows[2], ( 'sample4', '0' ) )
        self.assertEqual(rows[3], ( 'sample3', '1' ) )
        self.assertEqual(rows[4], ( 'sample5', '1' ) )
        self.assertEqual(rows[5], ( 'sample6', '1' ) )

def main():
    sys.argv = sys.argv[:1]
    unittest.main()

if __name__ == '__main__':
    main()
