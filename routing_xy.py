# -*- coding: utf-8 -*-
import arcpy
import os
import json
import urllib
import random

class TaskRepository:

    def getSpatialReferenceCode(self,epsg):
        sr = arcpy.SpatialReference()
        sr.factoryCode = epsg
        sr.create()

        return sr.exportToString()

    def setWorkspace(self, epsg):
        sr = arcpy.SpatialReference()
        sr.factoryCode = epsg
        sr.create()

        # ENV Settings
        arcpy.env.overwriteOutput = 1
        arcpy.env.outputCoordinateSystem = sr

    def deleteWorkspace(self):
        arcpy.Delete_management(arcpy.env.scratchFolder)

    def createJSONObject(self, string):
        try:
            return json.loads(string)

        except (ValueError, KeyError, TypeError):
            arcpy.AddMessage('JSON format error')

    def replaceComma(self,value):
        return value.replace(",", ".").replace(' ', '').replace('(', '').replace(')', '')

    #doku:https://openrouteservice.org/documentation/#/reference/directions/directions
    def getDistanceRouteOpenRouteService(self, StartPoint, EndPoint,profile):
        url = 'http://192.9.200.2:8080/ors/routes?'
        coordinates = '{},{}|{},{}'.format(StartPoint[0],StartPoint[1],EndPoint[0],EndPoint[1])
        vars = {
            'api_key': '58d904a497c67e00015b45fc6d8eb085cd0d4b4ba8cda461c53cb8c8',
            'coordinates': coordinates,
            'profile': profile,
            'geometry': 'false',
            'units':'m'
        }

        resource = urllib.urlopen(url + urllib.urlencode(vars))
        #arcpy.AddMessage(url + urllib.urlencode(vars))
        json_url = json.loads(resource.read())
        result = []
        try:
            for row in json_url['routes']:
                # create the geojson polygon for testing the result
                result.append('{}'.format(row['summary']['distance']))
                result.append('{}'.format(row['summary']['duration']))
                return result
        except:
            result.append('error')
            result.append('error')
            return result

    def transformPoint(self,x, y, epsg_In, epsg_OUT):
        point = arcpy.PointGeometry(arcpy.Point(x, y), arcpy.SpatialReference(epsg_In)).projectAs(
            arcpy.SpatialReference(epsg_OUT))
        return point.centroid

    def getPointByFID(self,fid, searchfield, array):
        for row in array:
            if row['FID'] == fid:
                return row[searchfield]

def main():

    toolbox = TaskRepository()

    # user defined values
    input = arcpy.GetParameterAsText(0)

    # read the request json
    inputJSON = toolbox.createJSONObject(input)
    profiles_open_route = ['driving-car','foot-walking']
    profile_set_open_route = profiles_open_route[1]

    # get the epsg
    for e in inputJSON['options']:
        epsg_in = e['epsg']['input']
        profile = e['profile']
        try:
            epsg_out = e['epsg']['output']
            arcpy.AddMessage("output is epsg set, coordinates will retaurn in epsg {}".format(epsg_out))
        except KeyError:
            arcpy.AddMessage("no output epsg set, coordinates will retaurn in epsg {}".format(epsg_in))
            epsg_out = epsg_in

    #set the open route profile
    for x in profiles_open_route:
        if profile in x or profile == x:
            profile_set_open_route = x

    i=0
    result = []
    for x in inputJSON['coordinates']:
        i +=1
        ORG_ID = str(x["id"])
        ORG_Startpoint = [x["startpoint"]["x"],x["startpoint"]["y"]]
        ORG_Endpoint = [x["endpoint"]["x"],x["endpoint"]["y"]]
        Startpoint =[float(x["startpoint"]["x"].replace(',','.')),float(x["startpoint"]["y"].replace(',','.'))]
        Endpoint = [float(x["endpoint"]["x"].replace(',','.')),float(x["endpoint"]["y"].replace(',','.'))]
        if int(epsg_in)!= 4326:
            Startpoint = toolbox.transformPoint(Startpoint[0],Startpoint[1],int(epsg_in),4326)
            Startpoint = [Startpoint.X,Startpoint.Y]
            Endpoint = toolbox.transformPoint(Endpoint[0],Endpoint[1],int(epsg_in),4326)
            Endpoint = [Endpoint.X,Endpoint.Y]

        array_open_route = toolbox.getDistanceRouteOpenRouteService(Startpoint, Endpoint,profile_set_open_route)
        #transform back in origin epsg or if set in user choice epsg
        if epsg_in == epsg_out:
            Endpoint = ORG_Endpoint
        else:
            Startpoint = toolbox.transformPoint(Startpoint[0],Startpoint[1], 4326, int(epsg_out))
            Startpoint = [str(Startpoint.X), str(Startpoint.Y)]
            Endpoint = toolbox.transformPoint(Endpoint[0],Endpoint[1], 4326, int(epsg_out))
            Endpoint = [str(Endpoint.X), str(Endpoint.Y)]

        result.append({
            "x":str(ORG_Startpoint[0]),
            "y":str(ORG_Startpoint[1]),
            "id":str(ORG_ID),
            "values":[{
                "startpoint":[{
                    "x":str(Startpoint[0]),
                    "y":str(Startpoint[1])
                }],
                "endpoint":[{
                    "x":str(Endpoint[0]),
                    "y":str(Endpoint[1])
                }],
                "distance_open_route":[{
                    "value":str(array_open_route[0]),
                    "unit": "m"
                }],
                "duration_open_route":[{
                    "value":str(array_open_route[1]),
                    "unit":"s"
                }]
            }]
        })
    toolbox.deleteWorkspace()
    arcpy.SetParameterAsText(1,json.dumps(result))

if __name__ == '__main__': main()