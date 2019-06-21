# -*- coding: utf-8 -*-
import arcpy
import os
import json
import urllib
import random

#Object to Store the Bounding Box Variables
class Extent(object):
    minX = 1
    maxX = 1
    minY = 1
    maxY = 1

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

    # transform the pointlist into a point-shapefile
    def createShape(self, xy_json, epsg):
        # temp files
        temp_shapefile = os.path.join("in_memory", 'temp')
        inputjson = xy_json

        json_string = '['

        # transform into number format if comma seperated else return
        for row in inputjson:
            #lat lon is changed
            id_org = row['id']
            x_set = row['y']
            y_set = row['x']
            if int(epsg) != 4326:
                point_transform = self.transformPoint(float(row['x']),float(row['y']), int(epsg), 4326)
                arcpy.AddMessage(point_transform)
                x_set = point_transform.X
                y_set = point_transform.Y

            json_string += '{"org_id":"'+id_org+'","x":' + str(x_set) + ',"y":' + str(y_set) + ',"org_x":"'+str(row['org_x'])+'","org_y":"'+str(row['org_y'])+'","spatialReference" : {"wkid" : ' + str(4326) + '}},'

        json_string = json_string[:-1]
        json_string += ']'

        json_file = json.loads(json_string)

        sr = arcpy.SpatialReference()
        sr.factoryCode = 4326
        sr.create()

        # write the string to feature
        arcpy.CreateFeatureclass_management("in_memory", "temp", "POINT", "", "DISABLED", "DISABLED", sr.exportToString(), "", "0", "0","0")

        # add field to save the unformatted coordinates
        arcpy.AddField_management(temp_shapefile, "ORG_X", "TEXT")
        arcpy.AddField_management(temp_shapefile, "ORG_Y", "TEXT")
        arcpy.AddField_management(temp_shapefile, "ORG_ID", "TEXT")

        # insert rows
        cursor = arcpy.da.InsertCursor(temp_shapefile, ['SHAPE@XY', 'ORG_X', 'ORG_Y','ORG_ID'])
        for feature in json_file:
            xy = (feature['x'], feature['y'])
            cursor.insertRow([xy, feature['org_x'], feature['org_y'],feature['org_id']])

        # create the needed geometry to calculate the extent
        arcpy.AddField_management(temp_shapefile, "POINT_X", "DOUBLE")
        arcpy.AddField_management(temp_shapefile, "POINT_Y", "DOUBLE" )
        arcpy.CalculateField_management(temp_shapefile, "POINT_X", "!shape.extent.XMax!", "PYTHON_9.3")
        arcpy.CalculateField_management(temp_shapefile, "POINT_Y", "!shape.extent.YMax!", "PYTHON_9.3")
        return temp_shapefile

    def getConvexHullShapefile(self,shapefile,buffer):
        convex_hull = os.path.join("in_memory", 'convex_hull' + str(random.randint(1, 100)))
        # Process: Minimum Bounding Geometry
        arcpy.MinimumBoundingGeometry_management(shapefile, convex_hull, "CONVEX_HULL", "ALL", "",
                                                 "NO_MBG_FIELDS")

        if buffer:
            # Process: Buffer
            convex_hull_buffer = os.path.join("in_memory", 'convex_hull_buffer' + str(random.randint(1, 100)))
            arcpy.Buffer_analysis(convex_hull, convex_hull_buffer, buffer, "FULL",
                                  "ROUND", "NONE", "", "PLANAR")

            return convex_hull_buffer
        else:
            return convex_hull

    # Intersect Image and Polygon
    def Intersect(self, shape1, shape2):
        temp_shape_intersect = os.path.join("in_memory", 'temp_shape_intersection' + str(random.randint(1, 100)))
        # Intersect Image and Polygon
        arcpy.AddMessage('process Intersect Shapefile')
        arcpy.Intersect_analysis([shape1, shape2], temp_shape_intersect,
                                 "ALL", "", "POINT")

        return temp_shape_intersect

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

    #paramter
    coordinates = []

    #datadbase
    database = r'data.gdb'

    # read the request json
    inputJSON = toolbox.createJSONObject(input)
    profiles_open_route = ['driving-car','foot-walking']
    profile_set_open_route = profiles_open_route[1]

    # get the epsg
    for e in inputJSON['options']:
        poi = e['poi']
        profile = e['profile']
        epsg_in = e['epsg']['input']
        try:
            epsg_out = e['epsg']['output']
            arcpy.AddMessage("output is epsg set, coordinates will return in epsg {}".format(epsg_out))
        except KeyError:
            arcpy.AddMessage("no output epsg set, coordinates will return in epsg {}".format(epsg_in))
            epsg_out = epsg_in

    # the shapefile with the green spaces centroids
    #supported: green_areas, public_transport
    arcpy.AddMessage("poi {} is set".format(poi))
    green_points = '{}\{}'.format(database,poi)

    #set the open route profile
    for x in profiles_open_route:
        if profile in x or profile == x:
            profile_set_open_route = x


    # get the coordinates and transform if needed
    for c in inputJSON['coordinates']:
        id = str(c['id'])
        x = c['x']
        y = c['y']
        x_string = str(x)
        y_string = str(y)
        comma = ','
        x_set = x
        y_set = y

        if comma in x_string:
            x_set = toolbox.replaceComma(x_string)

        if comma in y_string:
            y_set = toolbox.replaceComma(y_string)

        coordinates.append({'id':id,'x': x_set, 'y': y_set,'org_x':c['x'],'org_y':c['y']})

    # set the workspace
    toolbox.setWorkspace(4326)
    temp_shapefile = toolbox.createShape(coordinates, epsg_in)

    #generate the intersected green_points shape to speed up performance
    green_points_interect = toolbox.Intersect(green_points,toolbox.getConvexHullShapefile(temp_shapefile,"3000 Meters"))

    #create the nearest table
    out_table = os.path.join("in_memory", "nearest_table")
    arcpy.AddMessage("calc distances")
    nearest_tabel = arcpy.GenerateNearTable_analysis(temp_shapefile, green_points_interect, out_table,"",
                                                     "NO_LOCATION", "NO_ANGLE", "ALL", "1", "PLANAR")

    array_poi = []
    cursor_poi = arcpy.da.SearchCursor(green_points_interect,['OBJECTID',"SHAPE@X","SHAPE@Y"])
    for row in cursor_poi:
        array_poi.append({
            'FID':row[0],
            'X':row[1],
            'Y':row[2]
        })


    array_points = []
    cursor_points = arcpy.da.SearchCursor(temp_shapefile, ['OID','ORG_X', 'ORG_Y',"POINT_X","POINT_Y",'ORG_ID'])
    for row in cursor_points:
        array_points.append({
            'FID': row[0],
            'ORG_X': row[1],
            'ORG_Y': row[2],
            'X': float(row[3]),
            'Y':float(row[4]),
            'ID':row[5]
        })

    #merge everything in one table to calc the distances
    merge_array = []
    cursor_table = arcpy.da.SearchCursor(nearest_tabel,['IN_FID','NEAR_FID'])
    for row in cursor_table:
        merge_array.append({
            'StartPointX': toolbox.getPointByFID(row[0],'X',array_points),
            'StartPointY': toolbox.getPointByFID(row[0],'Y',array_points),
            'EndPointX':toolbox.getPointByFID(row[1],'X',array_poi),
            'EndPointY':toolbox.getPointByFID(row[1],'Y',array_poi),
            'ORG_X':toolbox.getPointByFID(row[0],'ORG_X',array_points),
            'ORG_Y':toolbox.getPointByFID(row[0],'ORG_Y',array_points),
            'ID':toolbox.getPointByFID(row[0],'ID',array_points)
        })

    i = 0
    result = []
    for x in merge_array:
        i +=1
        #toolbox.getDistanceBing([StartPoint.Y,StartPoint.X], [EndPoint.Y,EndPoint.X],profile_set_google)
        array_open_route = toolbox.getDistanceRouteOpenRouteService([x['StartPointX'],x['StartPointY']], [x['EndPointX'],x['EndPointY']],profile_set_open_route)
        Endpoint = toolbox.transformPoint(float(x['EndPointX']), float(x['EndPointY']), 4326, int(epsg_out))
        Endpoint = [str(Endpoint.X), str(Endpoint.Y)]
        Start_key = ''
        #transform back in origin epsg or if set in user choice epsg
        if epsg_in != epsg_out:
            Startpoint = toolbox.transformPoint(float(x['StartPointX']), float(x['StartPointY']), 4326, int(epsg_out))
            Startpoint = [str(Startpoint.X), str(Startpoint.Y)]
            Start_key = '"startpoint":{"x":"'+Startpoint[0]+'","y":"'+Startpoint[1]+'"},'

        result.append({
            "x":str(x['ORG_X']),
            "y":str(x['ORG_Y']),
            "id":str(x['ID']),
            "values":[{
                "endpoint":[
                    {
                        "x":str(Endpoint[0]),
                        "y":str(Endpoint[1])
                    }],
                "distance_open_route":[
                    {
                        "value":str(array_open_route[0]),
                        "unit":"m"
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