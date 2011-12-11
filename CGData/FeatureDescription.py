
import CGData.BaseTable


class FeatureDescription(CGData.BaseTable.BaseTable):

    __format__ =  {
        "name" : "featureDescription",
        "type" : "type",
        "form" : "table",
        "columnOrder" : [
            "feature",
            "predicate",
            "value"
        ],
        "groupKey" : "feature",
        "secondaryKey" : "predicate"
    }
    
    def __init__(self):
        self._features = None
        super(FeatureDescription, self).__init__()


class NullClinicalFeature(FeatureDescription):
    def __init__(self):
        super(NullClinicalFeature, self).__init__()
        self['type'] = 'featureDescription'
        self['name'] = '__null__'
        self._features = {}
    def load(self):
        pass
