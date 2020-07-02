
from ..base.geocoder import GeocoderAbstract

import json
import urllib.request, urllib.parse, urllib.error

class GeocoderORS(GeocoderAbstract):

    API_URL = 'https://api.openrouteservice.org/geocode/search/structured'
    NAME = 'OpenRouteService'

    def __init__(self, parent):
        super(GeocoderORS, self).__init__(parent=parent)

    def createApiRequest(self, parameters):
        try:
            request = urllib.request.urlopen(self._buildRequestUrl(parameters))
            response = json.loads(request.read().decode())
            return response
        except urllib.error.HTTPError as error:
            if error.code == 403:
                return {'error': 'Invalid API Key'}
            else:
                return {'error': error.msg}

    def _buildRequestUrl(self, request_params):
        return self.API_URL + '?api_key=' + str(self.api_key)\
            + '&address={address}&locality={locality}&postalcode={postalcode}'.format(**request_params)

